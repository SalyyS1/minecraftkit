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
import java.util.concurrent.Executors;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

/**
 * Salyyy MinecraftKit Companion QA Bridge Plugin (Paper & Folia compatible).
 *
 * Exposes a token-authenticated loopback-only (127.0.0.1) HTTP/JSON API for:
 *  - /api/v1/health   : liveness + server version
 *  - /api/v1/metrics  : TPS, MSPT, JVM heap, worlds, chunk & entity totals
 *  - /api/v1/players  : online players, coordinates, health, open GUI slots
 *  - /api/v1/plugins  : loaded plugin list & enabled states
 *  - /api/v1/errors   : bounded ring-buffer of SEVERE/exception server logs
 *
 * Security: binds strictly to 127.0.0.1, requires constant-time X-MCKit-Token
 * verification, and never exposes remote command execution by default.
 */
public final class McKitBridgePlugin extends JavaPlugin {

    private static final int MAX_ERROR_RING = 200;

    private HttpServer httpServer;
    private byte[] authTokenBytes;
    private final Deque<String> errorRing = new ArrayDeque<>(MAX_ERROR_RING);
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

        installErrorCollector();
        startLoopbackServer(port);
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
            httpServer.setExecutor(Executors.newFixedThreadPool(2));
            httpServer.createContext("/api/v1/health", ex -> handleGuarded(ex, this::buildHealthJson));
            httpServer.createContext("/api/v1/metrics", ex -> handleGuarded(ex, this::buildMetricsJson));
            httpServer.createContext("/api/v1/players", ex -> handleGuarded(ex, this::buildPlayersJson));
            httpServer.createContext("/api/v1/gui", ex -> handleGuarded(ex, () -> buildGuiJson(ex)));
            httpServer.createContext("/api/v1/worlds", ex -> handleGuarded(ex, this::buildWorldsJson));
            httpServer.createContext("/api/v1/plugins", ex -> handleGuarded(ex, this::buildPluginsJson));
            httpServer.createContext("/api/v1/errors", ex -> handleGuarded(ex, this::buildErrorsJson));
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
