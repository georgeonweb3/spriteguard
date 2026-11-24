"""Tests for agent/connectors.py against a local stub gateway.

The stub mimics the Fly.io Sprites gateway paths proven live from a
Sprite on 24 Nov 2026 (Box /2.0/* and /upload/files/content; Pinecone
/inference/embed, /indexes/{name}/query, /indexes/{name}/vectors/upsert).
No real network, no keys, stdlib only. Run: python3 -m unittest discover -s agent/tests
"""

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import connectors

BOX_FOLDER_ID = "440773899785"
EMBED_VECTOR = [0.1] * 4


class StubHandler(BaseHTTPRequestHandler):
    """Minimal gateway stub. Class attrs drive per-test behaviour."""

    protocol_version = "HTTP/1.1"
    # When True, every request answers 403 (gateway rejecting the call).
    fail_all = False
    # When True, the root folder listing has no receipts folder.
    folder_missing = False
    # Recorded requests: list of (method, path, body_bytes).
    seen = []

    def log_message(self, *args):  # keep test output clean
        pass

    def _send(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _handle(self, method):
        body = self._read_body()
        StubHandler.seen.append((method, self.path, body))
        if StubHandler.fail_all:
            return self._send(403, {"error": "endpoint is not supported"})
        if method == "GET" and self.path == "/2.0/folders/0/items":
            entries = []
            if not StubHandler.folder_missing:
                entries.append(
                    {"type": "folder", "id": BOX_FOLDER_ID, "name": "SpriteGuard receipts"}
                )
            return self._send(200, {"entries": entries})
        if method == "POST" and self.path == "/2.0/folders":
            return self._send(201, {"id": BOX_FOLDER_ID, "name": "SpriteGuard receipts"})
        if method == "POST" and self.path == "/upload/files/content":
            # Multipart body must carry the attributes JSON + file part.
            assert b"SpriteGuard receipts" not in body  # folder name is in attributes id, not text
            assert b'"name": "r1.json"' in body or b'name": "r1.json' in body
            assert b"BLOCK" in body
            return self._send(201, {"entries": [{"id": "111", "name": "r1.json"}]})
        if method == "POST" and self.path == "/inference/embed":
            return self._send(200, {"data": [{"values": EMBED_VECTOR}]})
        if method == "POST" and self.path == "/indexes/spriteguard-vectors/query":
            payload = json.loads(body)
            assert payload["vector"] == EMBED_VECTOR
            assert payload["topK"] == 3
            return self._send(200, {"matches": [{"id": "r0", "score": 0.9, "metadata": {}}]})
        if method == "POST" and self.path == "/indexes/spriteguard-vectors/vectors/upsert":
            payload = json.loads(body)
            assert payload["vectors"][0]["values"] == EMBED_VECTOR
            return self._send(200, {})
        return self._send(404, {"error": "not found"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


class ConnectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        StubHandler.fail_all = False
        StubHandler.folder_missing = False
        StubHandler.seen = []
        os.environ["BOX_GATEWAY_URL"] = self.base
        os.environ["PINECONE_GATEWAY_URL"] = self.base
        os.environ["PINECONE_INDEX"] = "spriteguard-vectors"

    def tearDown(self):
        for key in ("BOX_GATEWAY_URL", "PINECONE_GATEWAY_URL", "PINECONE_INDEX"):
            os.environ.pop(key, None)

    def test_box_upload_uses_existing_folder(self):
        mode, err = connectors.box_upload("r1.json", '{"verdict": "BLOCK"}')
        self.assertEqual(mode, "gateway", err)
        paths = [(m, p) for m, p, _ in StubHandler.seen]
        self.assertIn(("GET", "/2.0/folders/0/items"), paths)
        self.assertIn(("POST", "/upload/files/content"), paths)
        # No folder creation when the folder already exists.
        self.assertNotIn(("POST", "/2.0/folders"), paths)

    def test_box_upload_creates_missing_folder(self):
        StubHandler.folder_missing = True
        mode, err = connectors.box_upload("r1.json", '{"verdict": "BLOCK"}')
        self.assertEqual(mode, "gateway", err)
        paths = [(m, p) for m, p, _ in StubHandler.seen]
        self.assertIn(("POST", "/2.0/folders"), paths)
        self.assertIn(("POST", "/upload/files/content"), paths)

    def test_box_upload_falls_back_on_gateway_403(self):
        StubHandler.fail_all = True
        mode, err = connectors.box_upload("r1.json", '{"verdict": "BLOCK"}')
        self.assertEqual(mode, "mock")
        self.assertIn("403", err)

    def test_pinecone_query_embeds_then_queries(self):
        result = connectors.pinecone_query("hijack attempt", top_k=3)
        self.assertEqual(result["mode"], "gateway", result["error"])
        self.assertEqual(len(result["matches"]), 1)
        paths = [(m, p) for m, p, _ in StubHandler.seen]
        self.assertIn(("POST", "/inference/embed"), paths)
        self.assertIn(("POST", "/indexes/spriteguard-vectors/query"), paths)

    def test_pinecone_upsert_embeds_then_upserts(self):
        mode, err = connectors.pinecone_upsert("r1", "dock order", {"verdict": "BLOCK"})
        self.assertEqual(mode, "gateway", err)
        paths = [(m, p) for m, p, _ in StubHandler.seen]
        self.assertIn(("POST", "/inference/embed"), paths)
        self.assertIn(("POST", "/indexes/spriteguard-vectors/vectors/upsert"), paths)

    def test_pinecone_falls_back_on_gateway_403(self):
        StubHandler.fail_all = True
        result = connectors.pinecone_query("hijack attempt")
        self.assertEqual(result["mode"], "mock")
        self.assertIn("403", result["error"])
        mode, err = connectors.pinecone_upsert("r1", "dock order", {})
        self.assertEqual(mode, "mock")
        self.assertIn("403", err)

    def test_missing_env_is_mock(self):
        os.environ.pop("BOX_GATEWAY_URL")
        os.environ.pop("PINECONE_GATEWAY_URL")
        mode, err = connectors.box_upload("r1.json", "{}")
        self.assertEqual(mode, "mock")
        result = connectors.pinecone_query("x")
        self.assertEqual(result["mode"], "mock")


if __name__ == "__main__":
    unittest.main()
