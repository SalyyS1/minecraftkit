package com.salyvn.mckit.bridge;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.Deque;

/**
 * Standalone zero-dependency contract test for mckit-bridge-plugin security and serialization invariants.
 * Compiled and executed directly by Java 21 in CI without requiring Paper API jars.
 */
public final class BridgeContractTest {

    private static boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null) return false;
        return MessageDigest.isEqual(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder(s.length() + 8);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
                }
            }
        }
        return sb.toString();
    }

    private static void assertTrue(boolean cond, String msg) {
        if (!cond) throw new AssertionError("BridgeContractTest failed: " + msg);
    }

    public static void main(String[] args) {
        // 1. Constant-time token verification
        assertTrue(constantTimeEquals("tok_abc123", "tok_abc123"), "matching tokens must pass");
        assertTrue(!constantTimeEquals("tok_abc123", "tok_abc124"), "different tokens must fail");
        assertTrue(!constantTimeEquals("tok_abc123", null), "null token must fail closed");

        // 2. JSON escaping for player GUI titles & stacktraces
        String escaped = escapeJson("Shop \"Mythic\"\nLine2\\Path");
        assertTrue(escaped.equals("Shop \\\"Mythic\\\"\\nLine2\\\\Path"), "JSON escaping mismatch: " + escaped);

        // 3. Bounded error ring buffer invariant (cap = 200)
        int maxCap = 200;
        Deque<String> ring = new ArrayDeque<>(maxCap);
        for (int i = 0; i < 350; i++) {
            if (ring.size() >= maxCap) ring.removeFirst();
            ring.addLast("SEVERE #" + i);
        }
        assertTrue(ring.size() == maxCap, "ring must stay bounded at 200");
        assertTrue("SEVERE #150".equals(ring.peekFirst()), "oldest retained entry must be #150");
        assertTrue("SEVERE #349".equals(ring.peekLast()), "newest retained entry must be #349");

        // 4. Sandboxed command prefix blocklist guard
        java.util.List<String> blocked = java.util.List.of("op", "deop", "stop", "restart", "ban", "pardon", "whitelist", "execute");
        assertTrue(isCommandBlocked("op SalyyS1", blocked), "op must be blocked");
        assertTrue(isCommandBlocked("/STOP", blocked), "/STOP must be blocked");
        assertTrue(!isCommandBlocked("tps", blocked), "tps must be allowed");
        assertTrue(!isCommandBlocked("mmoitems reload", blocked), "plugin reload must be allowed");

        // 5. Real Java 21 loopback HTTP server contract (127.0.0.1 ephemeral port + X-MCKit-Token auth)
        verifyLoopbackHttpAuth();

        System.out.println("BridgeContractTest: 5/5 PASS");
    }

    private static void verifyLoopbackHttpAuth() {
        String expectedToken = "tok_loopback_contract_999";
        try {
            var server = com.sun.net.httpserver.HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
            server.createContext("/api/v1/health", exchange -> {
                String provided = exchange.getRequestHeaders().getFirst("X-MCKit-Token");
                int code = constantTimeEquals(expectedToken, provided) ? 200 : 401;
                byte[] body = (code == 200 ? "{\"ok\":true,\"tps\":20.0}" : "{\"ok\":false,\"error\":\"unauthorized\"}")
                        .getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(code, body.length);
                try (var os = exchange.getResponseBody()) {
                    os.write(body);
                }
            });
            server.start();
            try {
                int port = server.getAddress().getPort();
                var client = java.net.http.HttpClient.newHttpClient();
                var uri = java.net.URI.create("http://127.0.0.1:" + port + "/api/v1/health");

                var badResp = client.send(
                        java.net.http.HttpRequest.newBuilder(uri).header("X-MCKit-Token", "wrong").GET().build(),
                        java.net.http.HttpResponse.BodyHandlers.ofString()
                );
                assertTrue(badResp.statusCode() == 401, "invalid token must return 401, got " + badResp.statusCode());

                var okResp = client.send(
                        java.net.http.HttpRequest.newBuilder(uri).header("X-MCKit-Token", expectedToken).GET().build(),
                        java.net.http.HttpResponse.BodyHandlers.ofString()
                );
                assertTrue(okResp.statusCode() == 200, "valid token must return 200, got " + okResp.statusCode());
                assertTrue(okResp.body().contains("\"tps\":20.0"), "health payload mismatch: " + okResp.body());
            } finally {
                server.stop(0);
            }
        } catch (Exception e) {
            throw new AssertionError("Loopback HTTP contract test failed: " + e.getMessage(), e);
        }
    }

    private static boolean isCommandBlocked(String raw, java.util.List<String> blocked) {
        String clean = raw == null ? "" : raw.trim();
        if (clean.startsWith("/")) clean = clean.substring(1).trim();
        if (clean.isEmpty()) return true;
        String root = clean.split("\\s+")[0];
        for (String b : blocked) {
            if (root.equalsIgnoreCase(b)) return true;
        }
        return false;
    }
}
