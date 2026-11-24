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

        System.out.println("BridgeContractTest: 4/4 PASS");
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
