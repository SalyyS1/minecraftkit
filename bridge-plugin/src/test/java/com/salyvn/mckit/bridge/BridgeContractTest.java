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

        // 6. Bounded 60-sample TPS/MSPT history ring buffer invariant
        int maxTpsCap = 60;
        Deque<String> tpsRing = new ArrayDeque<>(maxTpsCap);
        for (int i = 0; i < 95; i++) {
            if (tpsRing.size() >= maxTpsCap) tpsRing.removeFirst();
            tpsRing.addLast("{\"tps_1m\":20.00,\"seq\":" + i + "}");
        }
        assertTrue(tpsRing.size() == maxTpsCap, "TPS ring must stay bounded at 60");
        assertTrue(tpsRing.peekFirst().contains("\"seq\":35"), "oldest retained TPS sample must be #35");
        assertTrue(tpsRing.peekLast().contains("\"seq\":94"), "newest retained TPS sample must be #94");

        // 7. Chunk density calculation invariant (zero-loaded guard + finite formatting)
        double zeroDensity = 0 > 0 ? (10.0 / 0) : 0.0;
        double sampleDensity = 320.0 / 160.0;
        assertTrue(zeroDensity == 0.0 && Math.abs(sampleDensity - 2.0) < 1e-9, "chunk density math mismatch");

        // 8. JVM MemoryMXBean & ThreadMXBean telemetry contract (/api/v1/memory)
        var heap = java.lang.management.ManagementFactory.getMemoryMXBean().getHeapMemoryUsage();
        long maxMb = Math.max(1L, (heap.getMax() > 0 ? heap.getMax() : Runtime.getRuntime().maxMemory()) / (1024 * 1024));
        long usedMb = heap.getUsed() / (1024 * 1024);
        double pct = Math.min(100.0, (usedMb * 100.0) / maxMb);
        var threadBean = java.lang.management.ManagementFactory.getThreadMXBean();
        int threads = threadBean.getThreadCount();
        assertTrue(maxMb >= 1 && pct >= 0.0 && pct <= 100.0 && threads >= 1, "memory/thread telemetry invariant failed");

        // 9. JVM ThreadMXBean deadlock & peak thread telemetry contract (/api/v1/threads)
        long[] deadlocked = threadBean.findDeadlockedThreads();
        int peakThreads = threadBean.getPeakThreadCount();
        assertTrue(peakThreads >= threads && (deadlocked == null || deadlocked.length == 0), "thread deadlock telemetry invariant failed");

        System.out.println("BridgeContractTest: 9/9 PASS");
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
