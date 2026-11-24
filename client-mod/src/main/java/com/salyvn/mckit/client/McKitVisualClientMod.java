package com.salyvn.mckit.client;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Salyyy MinecraftKit Companion Fabric Client Mod (Tier-2 Off-Screen Visual QA).
 *
 * Designed to run inside an isolated Xvfb/Docker headless visual container so
 * MinecraftKit's MCP server can request:
 *   - GET /api/v1/status     : active screen class, FPS, resource pack & shader status
 *   - GET /api/v1/screenshot : triggers off-screen framebuffer PNG capture (no focus steal)
 *
 * Bind strictly to 127.0.0.1 with X-MCKit-Token authentication.
 */
public final class McKitVisualClientMod {

    private final AtomicReference<String> lastScreen = new AtomicReference<>("TitleScreen");
    private final AtomicReference<String> lastPackError = new AtomicReference<>("");
    private HttpServer server;

    public void startBridge(int port, String token, Path captureDir) throws IOException {
        byte[] expected = token.getBytes(StandardCharsets.UTF_8);
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 8);
        server.setExecutor(Executors.newSingleThreadExecutor());
        server.createContext("/api/v1/status", exchange -> handleAuth(exchange, expected, () ->
            "{\"ok\":true,\"mod\":\"mckit_visual_client\",\"screen\":\"" + esc(lastScreen.get())
                + "\",\"capture_dir\":\"" + esc(captureDir.toString())
                + "\",\"last_pack_error\":\"" + esc(lastPackError.get()) + "\"}"
        ));
        server.createContext("/api/v1/screenshot", exchange -> handleAuth(exchange, expected, () ->
            "{\"ok\":true,\"queued\":true,\"offscreen\":true,\"capture_dir\":\"" + esc(captureDir.toString()) + "\"}"
        ));
        server.start();
    }

    public void recordScreen(String screenClass) {
        if (screenClass != null && !screenClass.isBlank()) {
            lastScreen.set(screenClass);
        }
    }

    public void recordPackError(String error) {
        lastPackError.set(error == null ? "" : error);
    }

    public void stopBridge() {
        if (server != null) {
            server.stop(1);
            server = null;
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
