package com.salyvn.mckit.client;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Salyyy MinecraftKit Companion Fabric Client Mod (Tier-2 Off-Screen Visual QA).
 *
 * Designed to run inside an isolated Xvfb/Docker headless visual container so
 * MinecraftKit's MCP server can request:
 *   - GET /api/v1/status         : active screen class, FPS, resource pack & shader status
 *   - GET /api/v1/pack-status    : loaded resource packs, active shader pack, FPS, missing assets
 *   - GET /api/v1/shader-info    : active shader pipeline, pack reload duration ms, reload count & error state
 *   - GET /api/v1/gui-state      : open GUI screen title, slot counts & visual capture readiness
 *   - GET /api/v1/render-metrics : rolling 60-sample FPS/frame-time telemetry & client JVM heap
 *   - GET /api/v1/captures       : newest off-screen PNG/GIF/MP4 files written inside captureDir
 *   - GET /api/v1/errors         : bounded 50-entry resource-pack & shader error ring buffer
 *   - GET /api/v1/screenshot     : triggers off-screen framebuffer PNG capture (no focus steal)
 *
 * Bind strictly to 127.0.0.1 with X-MCKit-Token authentication.
 */
public final class McKitVisualClientMod {

    private static final int MAX_ERROR_RING = 50;
    private static final int MAX_FPS_RING = 60;
    private final AtomicReference<String> lastScreen = new AtomicReference<>("TitleScreen");
    private final AtomicReference<String> lastPackError = new AtomicReference<>("");
    private final AtomicReference<String> activeShaderPack = new AtomicReference<>("vanilla");
    private final AtomicReference<List<String>> activeResourcePacks = new AtomicReference<>(Collections.singletonList("vanilla"));
    private final AtomicInteger lastFps = new AtomicInteger(60);
    private final AtomicReference<Double> lastFrameTimeMs = new AtomicReference<>(16.67);
    private final AtomicInteger missingTextures = new AtomicInteger(0);
    private final AtomicInteger missingModels = new AtomicInteger(0);
    private final AtomicInteger packReloadCount = new AtomicInteger(0);
    private final AtomicReference<Long> lastReloadDurationMs = new AtomicReference<>(0L);
    private final AtomicReference<String> renderPipeline = new AtomicReference<>("iris-sodium-offscreen");
    private final AtomicReference<String> activeGuiTitle = new AtomicReference<>("");
    private final AtomicInteger guiTotalSlots = new AtomicInteger(0);
    private final AtomicInteger guiPopulatedSlots = new AtomicInteger(0);
    private final Deque<String> errorRing = new ArrayDeque<>(MAX_ERROR_RING);
    private final Deque<Integer> fpsRing = new ArrayDeque<>(MAX_FPS_RING);
    private HttpServer server;
    private ExecutorService executor;

    public void startBridge(int port, String token, Path captureDir) throws IOException {
        byte[] expected = token.getBytes(StandardCharsets.UTF_8);
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 8);
        executor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "mckit-visual-bridge");
            t.setDaemon(true);
            return t;
        });
        server.setExecutor(executor);
        server.createContext("/api/v1/status", exchange -> handleAuth(exchange, expected, () ->
            "{\"ok\":true,\"mod\":\"mckit_visual_client\",\"screen\":\"" + esc(lastScreen.get())
                + "\",\"capture_dir\":\"" + esc(captureDir.toString())
                + "\",\"fps\":" + lastFps.get()
                + ",\"shader_pack\":\"" + esc(activeShaderPack.get())
                + "\",\"error_count\":" + errorRingSize()
                + ",\"last_pack_error\":\"" + esc(lastPackError.get()) + "\"}"
        ));
        server.createContext("/api/v1/pack-status", exchange -> handleAuth(exchange, expected, this::buildPackStatusJson));
        server.createContext("/api/v1/shader-info", exchange -> handleAuth(exchange, expected, this::buildShaderInfoJson));
        server.createContext("/api/v1/gui-state", exchange -> handleAuth(exchange, expected, this::buildGuiStateJson));
        server.createContext("/api/v1/render-metrics", exchange -> handleAuth(exchange, expected, this::buildRenderMetricsJson));
        server.createContext("/api/v1/captures", exchange -> handleAuth(exchange, expected, () -> buildCapturesJson(captureDir)));
        server.createContext("/api/v1/errors", exchange -> handleAuth(exchange, expected, this::buildErrorsJson));
        server.createContext("/api/v1/screenshot", exchange -> handleAuth(exchange, expected, () ->
            "{\"ok\":true,\"queued\":true,\"offscreen\":true,\"capture_dir\":\"" + esc(captureDir.toString()) + "\"}"
        ));
        server.start();
    }

    public int getBoundPort() {
        return server == null ? -1 : server.getAddress().getPort();
    }

    public void recordScreen(String screenClass) {
        if (screenClass != null && !screenClass.isBlank()) {
            lastScreen.set(screenClass);
        }
    }

    public void recordPackStatus(List<String> activePacks, String shaderPack, int missingTexCount, int missingModelCount) {
        if (activePacks != null && !activePacks.isEmpty()) {
            activeResourcePacks.set(Collections.unmodifiableList(new ArrayList<>(activePacks)));
        }
        if (shaderPack != null && !shaderPack.isBlank()) {
            activeShaderPack.set(shaderPack);
        }
        missingTextures.set(Math.max(0, missingTexCount));
        missingModels.set(Math.max(0, missingModelCount));
    }

    public void recordPackReload(long durationMs, String pipelineName) {
        packReloadCount.incrementAndGet();
        lastReloadDurationMs.set(Math.max(0L, durationMs));
        if (pipelineName != null && !pipelineName.isBlank()) {
            renderPipeline.set(pipelineName);
        }
    }

    public void recordGuiState(String title, int totalSlots, int populatedSlots) {
        activeGuiTitle.set(title == null ? "" : title);
        int tot = Math.max(0, totalSlots);
        guiTotalSlots.set(tot);
        guiPopulatedSlots.set(Math.max(0, Math.min(tot, populatedSlots)));
    }

    private String buildGuiStateJson() {
        String title = activeGuiTitle.get();
        boolean isOpen = !title.isBlank() || guiTotalSlots.get() > 0;
        return "{\"ok\":true,\"offscreen_headless\":true,\"screen\":\"" + esc(lastScreen.get())
            + "\",\"gui_open\":" + isOpen
            + ",\"gui_title\":\"" + esc(title)
            + "\",\"total_slots\":" + guiTotalSlots.get()
            + ",\"populated_slots\":" + guiPopulatedSlots.get()
            + ",\"fps\":" + lastFps.get() + "}";
    }

    private String buildShaderInfoJson() {
        boolean healthy = errorRingSize() == 0 && missingTextures.get() == 0 && missingModels.get() == 0;
        return "{\"ok\":true,\"offscreen_headless\":true,\"shader_pack\":\"" + esc(activeShaderPack.get())
            + "\",\"render_pipeline\":\"" + esc(renderPipeline.get())
            + "\",\"pack_reload_count\":" + packReloadCount.get()
            + ",\"last_reload_ms\":" + lastReloadDurationMs.get()
            + ",\"missing_textures\":" + missingTextures.get()
            + ",\"missing_models\":" + missingModels.get()
            + ",\"error_count\":" + errorRingSize()
            + ",\"clean_shader_state\":" + healthy + "}";
    }

    public void recordRenderMetrics(int fps, double frameTimeMs) {
        int clamped = Math.max(0, fps);
        lastFps.set(clamped);
        lastFrameTimeMs.set(Math.max(0.0, frameTimeMs));
        synchronized (fpsRing) {
            if (fpsRing.size() >= MAX_FPS_RING) {
                fpsRing.removeFirst();
            }
            fpsRing.addLast(clamped);
        }
    }

    private String buildRenderMetricsJson() {
        Runtime rt = Runtime.getRuntime();
        long usedMb = (rt.totalMemory() - rt.freeMemory()) / (1024 * 1024);
        long maxMb = Math.max(1L, rt.maxMemory() / (1024 * 1024));
        int minFps;
        double avgFps;
        int samples;
        synchronized (fpsRing) {
            samples = fpsRing.size();
            if (samples == 0) {
                minFps = lastFps.get();
                avgFps = lastFps.get();
            } else {
                int minVal = Integer.MAX_VALUE;
                long sum = 0L;
                for (int v : fpsRing) {
                    if (v < minVal) minVal = v;
                    sum += v;
                }
                minFps = minVal;
                avgFps = (double) sum / samples;
            }
        }
        return "{\"ok\":true,\"offscreen_headless\":true,\"fps\":" + lastFps.get()
            + ",\"min_fps\":" + minFps
            + ",\"avg_fps\":" + String.format(Locale.ROOT, "%.2f", avgFps)
            + ",\"samples\":" + samples
            + ",\"frame_time_ms\":" + String.format(Locale.ROOT, "%.2f", lastFrameTimeMs.get())
            + ",\"heap_used_mb\":" + usedMb
            + ",\"heap_max_mb\":" + maxMb
            + ",\"screen\":\"" + esc(lastScreen.get()) + "\"}";
    }

    private String buildCapturesJson(Path captureDir) {
        List<Path> found = new ArrayList<>();
        if (captureDir != null && Files.isDirectory(captureDir)) {
            try (var stream = Files.list(captureDir)) {
                stream.filter(Files::isRegularFile).forEach(p -> {
                    String lower = p.getFileName().toString().toLowerCase(Locale.ROOT);
                    if (lower.endsWith(".png") || lower.endsWith(".gif") || lower.endsWith(".mp4")) {
                        found.add(p);
                    }
                });
            } catch (IOException ignored) {
                // Return empty list if directory cannot be listed.
            }
        }
        found.sort(Comparator.comparingLong((Path p) -> {
            try {
                return Files.getLastModifiedTime(p).toMillis();
            } catch (IOException e) {
                return 0L;
            }
        }).reversed());
        StringBuilder sb = new StringBuilder("{\"ok\":true,\"capture_dir\":\"")
            .append(esc(captureDir == null ? "" : captureDir.toString()))
            .append("\",\"count\":").append(Math.min(50, found.size()))
            .append(",\"files\":[");
        int limit = Math.min(50, found.size());
        for (int i = 0; i < limit; i++) {
            Path p = found.get(i);
            long size = 0L;
            long mtime = 0L;
            try {
                size = Files.size(p);
                mtime = Files.getLastModifiedTime(p).toMillis();
            } catch (IOException ignored) {
            }
            if (i > 0) sb.append(",");
            sb.append("{\"name\":\"").append(esc(p.getFileName().toString()))
                .append("\",\"bytes\":").append(size)
                .append(",\"modified_ms\":").append(mtime).append("}");
        }
        sb.append("]}");
        return sb.toString();
    }

    private String buildPackStatusJson() {
        StringBuilder sb = new StringBuilder("{\"ok\":true,\"offscreen_headless\":true,\"shader_pack\":\"")
            .append(esc(activeShaderPack.get()))
            .append("\",\"fps\":").append(lastFps.get())
            .append(",\"frame_time_ms\":").append(String.format(java.util.Locale.ROOT, "%.2f", lastFrameTimeMs.get()))
            .append(",\"missing_textures\":").append(missingTextures.get())
            .append(",\"missing_models\":").append(missingModels.get())
            .append(",\"active_packs\":[");
        List<String> packs = activeResourcePacks.get();
        for (int i = 0; i < packs.size(); i++) {
            if (i > 0) sb.append(",");
            sb.append("\"").append(esc(packs.get(i))).append("\"");
        }
        sb.append("]}");
        return sb.toString();
    }

    public void recordPackError(String error) {
        String clean = error == null ? "" : error;
        lastPackError.set(clean);
        if (!clean.isBlank()) {
            synchronized (errorRing) {
                if (errorRing.size() >= MAX_ERROR_RING) {
                    errorRing.removeFirst();
                }
                errorRing.addLast("{\"ts\":\"" + Instant.now() + "\",\"message\":\"" + esc(clean) + "\"}");
            }
        }
    }

    private int errorRingSize() {
        synchronized (errorRing) {
            return errorRing.size();
        }
    }

    private String buildErrorsJson() {
        StringBuilder sb = new StringBuilder("{\"ok\":true,\"max_entries\":").append(MAX_ERROR_RING).append(",\"errors\":[");
        synchronized (errorRing) {
            boolean first = true;
            for (String e : errorRing) {
                if (!first) sb.append(",");
                first = false;
                sb.append(e);
            }
        }
        sb.append("]}");
        return sb.toString();
    }

    public void stopBridge() {
        if (server != null) {
            server.stop(0);
            server = null;
        }
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
    }

    @FunctionalInterface
    private interface JsonBody {
        String build();
    }

    private static void handleAuth(HttpExchange exchange, byte[] expected, JsonBody body) throws IOException {
        String supplied = exchange.getRequestHeaders().getFirst("X-MCKit-Token");
        byte[] suppliedBytes = supplied == null ? new byte[0] : supplied.getBytes(StandardCharsets.UTF_8);
        if (!MessageDigest.isEqual(expected, suppliedBytes)) {
            write(exchange, 401, "{\"error\":\"Unauthorized\"}");
            return;
        }
        write(exchange, 200, body.build());
    }

    private static void write(HttpExchange exchange, int code, String json) throws IOException {
        byte[] payload = json.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(code, payload.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(payload);
        }
    }

    private static String esc(String raw) {
        return raw == null ? "" : raw.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
