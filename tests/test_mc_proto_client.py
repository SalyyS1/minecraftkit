from __future__ import annotations

import socket
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import mc_proto_client  # noqa: E402


class McProtoClientTests(unittest.TestCase):
    def test_varint_and_compressed_packet_roundtrip(self) -> None:
        for val in (0, 1, 127, 128, 255, 769, 25565, 2097151, -1):
            enc = mc_proto_client.encode_varint(val)
            dec, end = mc_proto_client.decode_varint(enc, 0)
            self.assertEqual(dec, val)
            self.assertEqual(end, len(enc))

        u = mc_proto_client.offline_player_uuid("MCKitProtoBot")
        self.assertEqual(u.version, 3)

    def test_loopback_offline_login_with_zlib_compression_reaches_configuration(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        saw_ack = []

        def handle() -> None:
            try:
                conn, _ = srv.accept()
                with conn:
                    # 1. Read Handshake (0x00)
                    pid1, _ = mc_proto_client.read_packet(conn)
                    assert pid1 == 0x00
                    # 2. Read LoginStart (0x00)
                    pid2, p2 = mc_proto_client.read_packet(conn)
                    assert pid2 == 0x00
                    uname, pos = mc_proto_client.decode_mc_string(p2, 0)
                    u_bytes = p2[pos : pos + 16]
                    # 3. Send Set Compression (0x03) with threshold=16
                    conn.sendall(mc_proto_client.frame_packet(0x03, mc_proto_client.encode_varint(16)))
                    # 4. Send compressed Login Success (0x02): UUID + username + 0 properties
                    success_payload = u_bytes + mc_proto_client.encode_mc_string(uname) + mc_proto_client.encode_varint(0)
                    conn.sendall(mc_proto_client.frame_packet(0x02, success_payload, compression_threshold=16))
                    # 5. Expect compressed Login Acknowledged (0x03)
                    pid_ack, _ = mc_proto_client.read_packet(conn, compression_threshold=16)
                    saw_ack.append(pid_ack)
            finally:
                srv.close()

        t = threading.Thread(target=handle, daemon=True)
        t.start()
        res = mc_proto_client.probe_offline_login_handshake(
            "127.0.0.1",
            port,
            username="MCKitProtoBot",
            protocol_version=769,
            timeout_seconds=3.0,
        )
        t.join(timeout=3.0)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["phase_reached"], "configuration")
        self.assertEqual(res["compression_threshold"], 16)
        self.assertEqual(saw_ack, [0x03])

    def test_mcp_export_stage_yaml_redacts_secrets(self) -> None:
        import json
        from mcp_server import MinecraftKitMcpServer

        srv = MinecraftKitMcpServer(root=ROOT)
        raw = srv.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "mc_bot_export_stage_yaml",
                "arguments": {
                    "name": "AuthMe Shop QA",
                    "host": "play.salyvn.net",
                    "stages": [
                        {"name": "Login", "action": "command", "command": "/login TopSecret99"},
                        {"name": "Open shop", "action": "command", "command": "/shop"},
                    ],
                },
            },
        }))
        assert raw is not None
        body = json.loads(json.loads(raw)["result"]["content"][0]["text"])
        self.assertNotIn("TopSecret99", body["yaml"])
        self.assertIn("[REDACTED_PASSWORD]", body["yaml"])
        self.assertIn("screen_lock_free: true", body["yaml"])

    def test_loopback_full_play_phase_command_dispatch_and_redaction(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        received_cmds: list[str] = []

        def handle() -> None:
            try:
                conn, _ = srv.accept()
                with conn:
                    # Handshake + LoginStart
                    mc_proto_client.read_packet(conn)
                    _, p2 = mc_proto_client.read_packet(conn)
                    uname, pos = mc_proto_client.decode_mc_string(p2, 0)
                    u_bytes = p2[pos : pos + 16]
                    # SetCompression (threshold=16) + LoginSuccess
                    conn.sendall(mc_proto_client.frame_packet(0x03, mc_proto_client.encode_varint(16)))
                    conn.sendall(mc_proto_client.frame_packet(
                        0x02,
                        u_bytes + mc_proto_client.encode_mc_string(uname) + mc_proto_client.encode_varint(0),
                        compression_threshold=16,
                    ))
                    # Read LoginAcknowledged (0x03)
                    pid_ack, _ = mc_proto_client.read_packet(conn, compression_threshold=16)
                    assert pid_ack == 0x03
                    # Configuration: send KeepAlive (0x04), expect 0x04
                    conn.sendall(mc_proto_client.frame_packet(0x04, b"\x00\x00\x00\x00\x00\x00\x00\x2a", compression_threshold=16))
                    pid_ka, _ = mc_proto_client.read_packet(conn, compression_threshold=16)
                    assert pid_ka == 0x04
                    # Configuration: send FinishConfiguration (0x03), expect Acknowledge (0x03)
                    conn.sendall(mc_proto_client.frame_packet(0x03, b"", compression_threshold=16))
                    pid_fin, _ = mc_proto_client.read_packet(conn, compression_threshold=16)
                    assert pid_fin == 0x03
                    # Play: read 2 ChatCommand (0x04) packets
                    for _ in range(2):
                        pid_c, payload_c = mc_proto_client.read_packet(conn, compression_threshold=16)
                        assert pid_c == 0x04
                        cmd_txt, _ = mc_proto_client.decode_mc_string(payload_c, 0)
                        received_cmds.append(cmd_txt)
                    # Send SystemChat reply (0x6C)
                    conn.sendall(mc_proto_client.frame_packet(
                        0x6C,
                        mc_proto_client.encode_mc_string("[AuthMe] Welcome MCKitPlayBot!"),
                        compression_threshold=16,
                    ))
            finally:
                srv.close()

        t = threading.Thread(target=handle, daemon=True)
        t.start()
        res = mc_proto_client.run_offline_play_probe(
            "127.0.0.1",
            port,
            username="MCKitPlayBot",
            commands=["/login SecretPass42", "/tps"],
            timeout_seconds=3.0,
        )
        t.join(timeout=3.0)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["phase_reached"], "play")
        self.assertEqual(received_cmds, ["login SecretPass42", "tps"])
        self.assertEqual(res["commands_sent"], ["/login [REDACTED_PASSWORD]", "/tps"])
        self.assertTrue(any("Welcome MCKitPlayBot" in m for m in res["chat_messages"]))


if __name__ == "__main__":
    unittest.main()
