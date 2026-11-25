package com.salyvn.mckit.bridge;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.Base64;
import java.util.Deque;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

/**
 * Salyyy MinecraftKit Companion QA Bridge Plugin (Paper & Folia compatible).
 *
 * Exposes a token-authenticated loopback-only (127.0.0.1) HTTP/JSON API for:
 *  - /api/v1/health      : liveness + server version
 *  - /api/v1/metrics     : TPS, MSPT, JVM heap, worlds, chunk & entity totals
 *  - /api/v1/tps-history : 60-sample rolling TPS/MSPT sparkline ring buffer
 *  - /api/v1/entities    : per-world entity totals & top entity types (lag diagnosis)
 *  - /api/v1/players     : online players, coordinates, health, open GUI slots
 *  - /api/v1/plugins     : loaded plugin list & enabled states
 *  - /api/v1/errors      : bounded ring-buffer of SEVERE/exception server logs
 *
 * Security: binds strictly to 127.0.0.1, requires constant-time X-MCKit-Token
 * verification, and never exposes remote command execution by default.
 */
public final class McKitBridgePlugin extends JavaPlugin {

    private static final int MAX_ERROR_RING = 200;
    private static final int MAX_TPS_HISTORY = 60;

    private HttpServer httpServer;
    private ExecutorService httpExecutor;
    private byte[] authTokenBytes;
    private boolean allowRemoteCommands;
    private java.util.List<String> blockedCommandPrefixes = java.util.List.of("op", "deop", "stop", "restart", "ban", "pardon", "whitelist", "execute");
    private final Deque<String> errorRing = new ArrayDeque<>(MAX_ERROR_RING);
    private final Deque<String> tpsHistoryRing = new ArrayDeque<>(MAX_TPS_HISTORY);
    private Handler julErrorHandler;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        int port = getConfig().getInt("port", 25590);
        String configuredToken = getConfig().getString("token", "");
        if (configuredToken == null || configuredToken.isBlank()) {
            byte[] randomBytes = new byte[24];
            new SecureRandom().nextBytes(randomBytes);
            configuredToken = Base64.getUrlEncoder().withoutPadding().encodeToString(randomBytes);
            getConfig().set("token", configuredToken);
            saveConfig();
            getLogger().info("[MCKitBridge] Generated new loopback auth token in plugins/MCKitBridge/config.yml");
        }
        this.authTokenBytes = configuredToken.getBytes(StandardCharsets.UTF_8);
        this.allowRemoteCommands = getConfig().getBoolean("allow-remote-commands", false);
        java.util.List<String> cfgBlocked = getConfig().getStringList("blocked-command-prefixes");
        if (cfgBlocked != null && !cfgBlocked.isEmpty()) {
            this.blockedCommandPrefixes = cfgBlocked;
        }

        installErrorCollector();
        startTpsSampler();
        startLoopbackServer(port);
    }

    private void startTpsSampler() {
        Bukkit.getGlobalRegionScheduler().runAtFixedRate(this, task -> {
            double[] tps = Bukkit.getTPS();
            double mspt = Bukkit.getAverageTickTime();
            String sample = "{\"ts\":\"" + Instant.now() + "\",\"tps_1m\":"
                + String.format(java.util.Locale.ROOT, "%.2f", tps.length > 0 ? tps[0] : 20.0)
                + ",\"mspt\":" + String.format(java.util.Locale.ROOT, "%.2f", mspt)
                + ",\"players\":" + Bukkit.getOnlinePlayers().size() + "}";
            synchronized (tpsHistoryRing) {
                if (tpsHistoryRing.size() >= MAX_TPS_HISTORY) {
                    tpsHistoryRing.removeFirst();
                }
                tpsHistoryRing.addLast(sample);
            }
        }, 20L, 20L);
    }

    @Override
    public void onDisable() {
        if (julErrorHandler != null) {
            Logger.getLogger("").removeHandler(julErrorHandler);
            julErrorHandler = null;
        }
        if (httpServer != null) {
            httpServer.stop(1);
            httpServer = null;
        }
        if (httpExecutor != null) {
            httpExecutor.shutdownNow();
            httpExecutor = null;
        }
    }

    private void installErrorCollector() {
        this.julErrorHandler = new Handler() {
            @Override
            public void publish(LogRecord record) {
                if (record == null || record.getLevel().intValue() < Level.SEVERE.intValue()) {
                    return;
                }
                StringBuilder entry = new StringBuilder();
                entry.append("{\"ts\":\"").append(Instant.ofEpochMilli(record.getMillis())).append("\"")
                    .append(",\"logger\":\"").append(esc(record.getLoggerName())).append("\"")
                    .append(",\"message\":\"").append(esc(record.getMessage())).append("\"");
                if (record.getThrown() != null) {
                    entry.append(",\"exception\":\"")
                        .append(esc(record.getThrown().getClass().getName() + ": " + record.getThrown().getMessage()))
                        .append("\"");
                }
                entry.append("}");
                synchronized (errorRing) {
                    if (errorRing.size() >= MAX_ERROR_RING) {
                        errorRing.removeFirst();
                    }
                    errorRing.addLast(entry.toString());
                }
            }

            @Override
            public void flush() {}

            @Override
            public void close() {}
        };
        Logger.getLogger("").addHandler(julErrorHandler);
    }

    private void startLoopbackServer(int port) {
        try {
            // Strictly loopback 127.0.0.1 so test telemetry is never exposed to the public internet.
            httpServer = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 16);
            httpExecutor = Executors.newFixedThreadPool(2, r -> {
                Thread t = new Thread(r, "mckit-bridge-http");
                t.setDaemon(true);
                return t;
            });
            httpServer.setExecutor(httpExecutor);
            httpServer.createContext("/api/v1/health", ex -> handleGuarded(ex, this::buildHealthJson));
            httpServer.createContext("/api/v1/metrics", ex -> handleGuarded(ex, this::buildMetricsJson));
            httpServer.createContext("/api/v1/tps-history", ex -> handleGuarded(ex, this::buildTpsHistoryJson));
            httpServer.createContext("/api/v1/entities", ex -> handleGuarded(ex, this::buildEntitiesJson));
            httpServer.createContext("/api/v1/chunks", ex -> handleGuarded(ex, this::buildChunksJson));
            httpServer.createContext("/api/v1/memory", ex -> handleGuarded(ex, this::buildMemoryJson));
            httpServer.createContext("/api/v1/threads", ex -> handleGuarded(ex, this::buildThreadsJson));
            httpServer.createContext("/api/v1/players", ex -> handleGuarded(ex, this::buildPlayersJson));
            httpServer.createContext("/api/v1/gui", ex -> handleGuarded(ex, () -> buildGuiJson(ex)));
            httpServer.createContext("/api/v1/worlds", ex -> handleGuarded(ex, this::buildWorldsJson));
            httpServer.createContext("/api/v1/plugins", ex -> handleGuarded(ex, this::buildPluginsJson));
            httpServer.createContext("/api/v1/errors", ex -> handleGuarded(ex, this::buildErrorsJson));
            httpServer.createContext("/api/v1/command", this::handleCommandDispatch);
            httpServer.start();
            getLogger().info("[MCKitBridge] Listening on http://127.0.0.1:" + port + "/api/v1/* (Folia-safe)");
        } catch (IOException ex) {
            getLogger().severe("[MCKitBridge] Failed to bind loopback HTTP server on port " + port + ": " + ex.getMessage());
        }
    }

    @FunctionalInterface
    private interface JsonSupplier {
        String get();
    }

    private void handleGuarded(HttpExchange exchange, JsonSupplier supplier) throws IOException {
        if (!"GET".equalsIgnoreCase(exchange.getRequestMethod())) {
            writeJson(exchange, 405, "{\"error\":\"Method Not Allowed\"}");
            return;
        }
        String supplied = exchange.getRequestHeaders().getFirst("X-MCKit-Token");
        byte[] suppliedBytes = supplied == null ? new byte[0] : supplied.getBytes(StandardCharsets.UTF_8);
        if (!MessageDigest.isEqual(authTokenBytes, suppliedBytes)) {
            writeJson(exchange, 401, "{\"error\":\"Unauthorized: missing or invalid X-MCKit-Token\"}");
            return;
        }
        try {
            writeJson(exchange, 200, supplier.get());
        } catch (Exception err) {
            writeJson(exchange, 500, "{\"error\":\"" + esc(err.getClass().getSimpleName() + ": " + err.getMessage()) + "\"}");
        }
    }

    private void handleCommandDispatch(HttpExchange exchange) throws IOException {
        if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
            writeJson(exchange, 405, "{\"error\":\"Method Not Allowed (use POST)\"}");
            return;
        }
        String supplied = exchange.getRequestHeaders().getFirst("X-MCKit-Token");
        byte[] suppliedBytes = supplied == null ? new byte[0] : supplied.getBytes(StandardCharsets.UTF_8);
        if (!MessageDigest.isEqual(authTokenBytes, suppliedBytes)) {
            writeJson(exchange, 401, "{\"error\":\"Unauthorized: missing or invalid X-MCKit-Token\"}");
            return;
        }
        if (!allowRemoteCommands) {
            writeJson(exchange, 403, "{\"error\":\"Remote command dispatch is disabled (set allow-remote-commands: true in config.yml)\"}");
            return;
        }
        String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8).trim();
        String cmd = extractJsonField(body, "command").trim();
        if (cmd.startsWith("/")) cmd = cmd.substring(1).trim();
        if (cmd.isEmpty() || cmd.length() > 256 || cmd.contains("\n") || cmd.contains("\r")) {
            writeJson(exchange, 400, "{\"error\":\"Invalid command payload\"}");
            return;
        }
        String rootWord = cmd.split("\\s+")[0].toLowerCase(java.util.Locale.ROOT);
        for (String blocked : blockedCommandPrefixes) {
            if (rootWord.equalsIgnoreCase(blocked)) {
                writeJson(exchange, 403, "{\"error\":\"Command prefix blocked by safety policy: " + esc(rootWord) + "\"}");
                return;
            }
        }
        final String finalCmd = cmd;
        Bukkit.getGlobalRegionScheduler().execute(this, () -> Bukkit.dispatchCommand(Bukkit.getConsoleSender(), finalCmd));
        writeJson(exchange, 202, "{\"ok\":true,\"queued\":true,\"command\":\"" + esc(finalCmd) + "\"}");
    }

    private static String extractJsonField(String json, String key) {
        String needle = "\"" + key + "\"";
        int k = json.indexOf(needle);
        if (k < 0) return "";
        int colon = json.indexOf(':', k + needle.length());
        if (colon < 0) return "";
        int q1 = json.indexOf('"', colon + 1);
        if (q1 < 0) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = q1 + 1; i < json.length(); i++) {
            char c = json.charAt(i);
            if (c == '\\' && i + 1 < json.length()) {
                sb.append(json.charAt(++i));
            } else if (c == '"') {
                break;
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    private void writeJson(HttpExchange exchange, int code, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(code, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }

    private String buildHealthJson() {
        return "{\"ok\":true,\"plugin\":\"MCKitBridge\",\"server\":\"" + esc(Bukkit.getName())
            + "\",\"version\":\"" + esc(Bukkit.getVersion())
            + "\",\"minecraft_version\":\"" + esc(Bukkit.getMinecraftVersion()) + "\"}";
    }

    private String buildMetricsJson() {
        Runtime rt = Runtime.getRuntime();
        long usedMb = (rt.totalMemory() - rt.freeMemory()) / (1024 * 1024);
        long maxMb = rt.maxMemory() / (1024 * 1024);
        double[] tps = Bukkit.getTPS();
        double mspt = Bukkit.getAverageTickTime();
        int loadedChunks = 0;
        for (World world : Bukkit.getWorlds()) {
            loadedChunks += world.getLoadedChunks().length;
        }
        return "{"
            + "\"tps_1m\":" + String.format("%.2f", tps.length > 0 ? tps[0] : 20.0) + ","
            + "\"tps_5m\":" + String.format("%.2f", tps.length > 1 ? tps[1] : 20.0) + ","
            + "\"tps_15m\":" + String.format("%.2f", tps.length > 2 ? tps[2] : 20.0) + ","
            + "\"mspt\":" + String.format("%.2f", mspt) + ","
            + "\"heap_used_mb\":" + usedMb + ","
            + "\"heap_max_mb\":" + maxMb + ","
            + "\"online_players\":" + Bukkit.getOnlinePlayers().size() + ","
            + "\"loaded_chunks\":" + loadedChunks
            + "}";
    }

    private String buildTpsHistoryJson() {
        StringBuilder sb = new StringBuilder("{\"max_samples\":").append(MAX_TPS_HISTORY).append(",\"samples\":[");
        synchronized (tpsHistoryRing) {
            boolean first = true;
            for (String s : tpsHistoryRing) {
                if (!first) sb.append(",");
                first = false;
                sb.append(s);
            }
        }
        sb.append("]}");
        return sb.toString();
    }

    private String buildChunksJson() {
        StringBuilder sb = new StringBuilder("{\"worlds\":[");
        boolean first = true;
        int totalLoaded = 0;
        int totalForceLoaded = 0;
        for (World world : Bukkit.getWorlds()) {
            if (!first) sb.append(",");
            first = false;
            int loaded = world.getLoadedChunks().length;
            int forced = world.getForceLoadedChunks().size();
            int entities = world.getEntityCount();
            double density = loaded > 0 ? ((double) entities / loaded) : 0.0;
            totalLoaded += loaded;
            totalForceLoaded += forced;
            sb.append("{\"world\":\"").append(esc(world.getName()))
                .append("\",\"loaded_chunks\":").append(loaded)
                .append(",\"force_loaded_chunks\":").append(forced)
                .append(",\"entity_count\":").append(entities)
                .append(",\"entities_per_chunk\":").append(String.format("%.2f", density))
                .append("}");
        }
        sb.append("],\"total_loaded_chunks\":").append(totalLoaded)
            .append(",\"total_force_loaded_chunks\":").append(totalForceLoaded).append("}");
        return sb.toString();
    }

    private String buildMemoryJson() {
        var memBean = java.lang.management.ManagementFactory.getMemoryMXBean();
        var heap = memBean.getHeapMemoryUsage();
        var nonHeap = memBean.getNonHeapMemoryUsage();
        long heapUsedMb = heap.getUsed() / (1024 * 1024);
        long heapCommittedMb = heap.getCommitted() / (1024 * 1024);
        long heapMaxMb = Math.max(1L, (heap.getMax() > 0 ? heap.getMax() : Runtime.getRuntime().maxMemory()) / (1024 * 1024));
        long nonHeapUsedMb = Math.max(0L, nonHeap.getUsed()) / (1024 * 1024);
        double pressurePct = Math.min(100.0, (heapUsedMb * 100.0) / heapMaxMb);
        long gcCount = 0L;
        long gcTimeMs = 0L;
        for (var gc : java.lang.management.ManagementFactory.getGarbageCollectorMXBeans()) {
            long c = gc.getCollectionCount();
            long t = gc.getCollectionTime();
            if (c > 0) gcCount += c;
            if (t > 0) gcTimeMs += t;
        }
        var threadBean = java.lang.management.ManagementFactory.getThreadMXBean();
        return "{"
            + "\"heap_used_mb\":" + heapUsedMb + ","
            + "\"heap_committed_mb\":" + heapCommittedMb + ","
            + "\"heap_max_mb\":" + heapMaxMb + ","
            + "\"heap_pressure_pct\":" + String.format("%.2f", pressurePct) + ","
            + "\"non_heap_used_mb\":" + nonHeapUsedMb + ","
            + "\"gc_count\":" + gcCount + ","
            + "\"gc_time_ms\":" + gcTimeMs + ","
            + "\"thread_count\":" + threadBean.getThreadCount() + ","
            + "\"daemon_threads\":" + threadBean.getDaemonThreadCount()
            + "}";
    }

    private String buildThreadsJson() {
        var threadBean = java.lang.management.ManagementFactory.getThreadMXBean();
        long[] deadlocked = threadBean.findDeadlockedThreads();
        StringBuilder dl = new StringBuilder("[");
        if (deadlocked != null) {
            for (int i = 0; i < deadlocked.length; i++) {
                if (i > 0) dl.append(",");
                dl.append(deadlocked[i]);
            }
        }
        dl.append("]");
        StringBuilder top = new StringBuilder("[");
        var infos = threadBean.getThreadInfo(threadBean.getAllThreadIds(), 0);
        int added = 0;
        if (infos != null) {
            for (var info : infos) {
                if (info == null) continue;
                if (added >= 12) break;
                if (added > 0) top.append(",");
                top.append("{\"name\":\"").append(esc(info.getThreadName()))
                    .append("\",\"state\":\"").append(esc(String.valueOf(info.getThreadState())))
                    .append("\"}");
                added++;
            }
        }
        top.append("]");
        return "{"
            + "\"thread_count\":" + threadBean.getThreadCount() + ","
            + "\"daemon_threads\":" + threadBean.getDaemonThreadCount() + ","
            + "\"peak_threads\":" + threadBean.getPeakThreadCount() + ","
            + "\"deadlock_detected\":" + (deadlocked != null && deadlocked.length > 0) + ","
            + "\"deadlocked_thread_ids\":" + dl + ","
            + "\"sample_threads\":" + top
            + "}";
    }

    private String buildEntitiesJson() {
        StringBuilder sb = new StringBuilder("{\"worlds\":[");
        boolean firstWorld = true;
        for (World w : Bukkit.getWorlds()) {
            if (!firstWorld) sb.append(",");
            firstWorld = false;
            java.util.Map<String, Integer> counts = new java.util.HashMap<>();
            int total = 0;
            for (org.bukkit.entity.Entity ent : w.getEntities()) {
                total++;
                counts.merge(ent.getType().name(), 1, Integer::sum);
            }
            java.util.List<java.util.Map.Entry<String, Integer>> top = new java.util.ArrayList<>(counts.entrySet());
            top.sort((a, b) -> Integer.compare(b.getValue(), a.getValue()));
            int limit = Math.min(10, top.size());
            sb.append("{\"world\":\"").append(esc(w.getName())).append("\",\"total\":").append(total).append(",\"top_types\":[");
            for (int i = 0; i < limit; i++) {
                if (i > 0) sb.append(",");
                sb.append("{\"type\":\"").append(esc(top.get(i).getKey())).append("\",\"count\":").append(top.get(i).getValue()).append("}");
            }
            sb.append("]}");
        }
        sb.append("]}");
        return sb.toString();
    }

    private String buildPlayersJson() {
        StringBuilder sb = new StringBuilder("{\"players\":[");
        boolean first = true;
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (!first) sb.append(",");
            first = false;
            InventoryView view = p.getOpenInventory();
            int nonEmptySlots = 0;
            if (view != null && view.getTopInventory() != null) {
                for (ItemStack item : view.getTopInventory().getContents()) {
                    if (item != null && !item.getType().isAir()) {
                        nonEmptySlots++;
                    }
                }
            }
            sb.append("{")
                .append("\"name\":\"").append(esc(p.getName())).append("\",")
                .append("\"uuid\":\"").append(p.getUniqueId()).append("\",")
                .append("\"world\":\"").append(esc(p.getWorld().getName())).append("\",")
                .append("\"x\":").append(String.format("%.2f", p.getLocation().getX())).append(",")
                .append("\"y\":").append(String.format("%.2f", p.getLocation().getY())).append(",")
                .append("\"z\":").append(String.format("%.2f", p.getLocation().getZ())).append(",")
                .append("\"health\":").append(String.format("%.1f", p.getHealth())).append(",")
                .append("\"food\":").append(p.getFoodLevel()).append(",")
                .append("\"open_gui_populated_slots\":").append(nonEmptySlots)
                .append("}");
        }
        sb.append("]}");
        return sb.toString();
    }

    private String buildGuiJson(HttpExchange exchange) {
        String query = exchange.getRequestURI().getQuery();
        String targetName = null;
        if (query != null) {
            for (String part : query.split("&")) {
                if (part.startsWith("player=")) {
                    targetName = part.substring("player=".length());
                }
            }
        }
        Player target = targetName == null ? null : Bukkit.getPlayerExact(targetName);
        if (target == null) {
            return "{\"found\":false,\"slots\":[]}";
        }
        InventoryView view = target.getOpenInventory();
        StringBuilder sb = new StringBuilder("{\"found\":true,\"player\":\"").append(esc(target.getName())).append("\",\"slots\":[");
        if (view != null && view.getTopInventory() != null) {
            ItemStack[] contents = view.getTopInventory().getContents();
            boolean first = true;
            for (int i = 0; i < contents.length; i++) {
                ItemStack item = contents[i];
                if (item == null || item.getType().isAir()) continue;
                if (!first) sb.append(",");
                first = false;
                int enchCount = item.getEnchantments().size();
                sb.append("{\"slot\":").append(i)
                    .append(",\"material\":\"").append(esc(item.getType().name()))
                    .append("\",\"amount\":").append(item.getAmount())
                    .append(",\"enchantments\":").append(enchCount).append("}");
            }
        }
        sb.append("]}");
        return sb.toString();
    }

    private String buildWorldsJson() {
        StringBuilder sb = new StringBuilder("{\"worlds\":[");
        boolean first = true;
        for (World w : Bukkit.getWorlds()) {
            if (!first) sb.append(",");
            first = false;
            sb.append("{\"name\":\"").append(esc(w.getName()))
                .append("\",\"loaded_chunks\":").append(w.getLoadedChunks().length)
                .append(",\"players\":").append(w.getPlayers().size())
                .append(",\"entities\":").append(w.getEntityCount()).append("}");
        }
        sb.append("]}");
        return sb.toString();
    }

    private String buildPluginsJson() {
        StringBuilder sb = new StringBuilder("{\"plugins\":[");
        Plugin[] plugins = Bukkit.getPluginManager().getPlugins();
        for (int i = 0; i < plugins.length; i++) {
            if (i > 0) sb.append(",");
            Plugin pl = plugins[i];
            sb.append("{\"name\":\"").append(esc(pl.getName()))
                .append("\",\"version\":\"").append(esc(pl.getPluginMeta().getVersion()))
                .append("\",\"enabled\":").append(pl.isEnabled()).append("}");
        }
        sb.append("]}");
        return sb.toString();
    }

    private String buildErrorsJson() {
        StringBuilder sb = new StringBuilder("{\"errors\":[");
        synchronized (errorRing) {
            boolean first = true;
            for (String item : errorRing) {
                if (!first) sb.append(",");
                first = false;
                sb.append(item);
            }
        }
        sb.append("]}");
        return sb.toString();
    }

    private static String esc(String raw) {
        if (raw == null) return "";
        return raw.replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t");
    }
}
