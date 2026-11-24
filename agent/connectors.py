"""Sprites gateway clients for SpriteGuard.

Everything here talks to Fly.io Sprites *connectors* through the gateway,
never with a key on the Sprite. The Sprites dashboard shows each
connector's gateway URL with your connection id filled in; paste that URL
into the env var. No API key, token, or secret is ever stored on the
Sprite, in this repo, or in the ledger.

Verified facts these clients rely on (see README "Sources" and
"Proof log"):
- Ollama connector: the gateway adds your Ollama key after checking which
  Sprite is calling. The Sprite only sees a gateway URL and a connection
  id. Chat path: POST {OLLAMA_GATEWAY_URL}/v1/chat/completions with an
  OpenAI-compatible body. (Ollama, "Fly.io Sprites", 13 Oct 2026.)
- Pinecone connector: the gateway is live and authenticated from a
  Sprite: GET {PINECONE_GATEWAY_URL}/indexes returns 200 and lists the
  indexes. (Sprite probe, 24 Nov 2026.) The gateway proxies the
  documented vector paths, /indexes/{name}/query and
  /indexes/{name}/vectors/upsert, and the inference path
  /inference/embed. (Fly.io connector page, "Target an index by name".)
- Box connector: FULLY LIVE from a Sprite, proven by direct probe
  24 Nov 2026: GET {BOX_GATEWAY_URL}/2.0/folders/0/items -> 200,
  POST {BOX_GATEWAY_URL}/2.0/folders -> 201 (created the
  "SpriteGuard receipts" folder), POST
  {BOX_GATEWAY_URL}/upload/files/content -> 201 (uploaded a receipt).
  (Sprite probe, 24 Nov 2026.)

Two limits, stated plainly:
- The index `spriteguard-memory` has a document schema (integrated
  inference, llama-text-embed-v2). Its /vectors/upsert returns HTTP 400
  "writes must go through the documents API", and the documents search
  endpoint returns HTTP 403 "endpoint is not supported by the Pinecone
  connector" through the gateway. Vector-style calls therefore target a
  plain vector index, `spriteguard-vectors` by default (PINECONE_INDEX),
  which the live-verify runbook creates first. `spriteguard-memory`
  stays as the documented index; it is never deleted.
- The gateway only answers a real Sprite. The same URLs return
  HTTP 401 "authentication failed" from any other machine, so the
  connector calls cannot be verified off-Sprite; the runbook in
  evidence/LIVE-VERIFY-RUNBOOK.md is the verification path.

Any non-200 still falls back to the local store and logs `mock`. The
guard, the ledger, and the Ollama chat call do not depend on them.
See README "What is real and what is not".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

TIMEOUT = 20

# Default index for vector-style calls. NOT spriteguard-memory: that
# index has a document schema and the gateway refuses vector writes to
# it (HTTP 400). A plain vector index (1024 dims, cosine) is created by
# the live-verify runbook; see evidence/LIVE-VERIFY-RUNBOOK.md.
DEFAULT_PINECONE_INDEX = "spriteguard-vectors"
PINECONE_EMBED_MODEL = "llama-text-embed-v2"


def _post_json(url, body, headers=None):
    """POST JSON, return (status, parsed_json_or_None, error_or_None)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw), None
            except json.JSONDecodeError:
                return resp.status, {"raw": raw}, None
    except urllib.error.HTTPError as e:
        return e.code, None, f"HTTP {e.code}"
    except Exception as e:  # network down, DNS, timeout: gateway unreachable
        return 0, None, str(e)[:160]


def _get_json(url):
    """GET JSON, return (status, parsed_json_or_None, error_or_None)."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw), None
            except json.JSONDecodeError:
                return resp.status, {"raw": raw}, None
    except urllib.error.HTTPError as e:
        return e.code, None, f"HTTP {e.code}"
    except Exception as e:
        return 0, None, str(e)[:160]


def _post_multipart(url, fields):
    """POST multipart/form-data.

    fields: list of (name, filename_or_None, content_type, bytes).
    Returns (status, parsed_json_or_None, error_or_None).
    """
    boundary = "----spriteguard-boundary-7d2e4a"
    parts = []
    for name, filename, ctype, data in fields:
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename is not None:
            head += f'; filename="{filename}"'
        head += f"\r\nContent-Type: {ctype}\r\n\r\n"
        parts.append(head.encode("utf-8") + data + b"\r\n")
    body = b"".join(parts) + f"--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw), None
            except json.JSONDecodeError:
                return resp.status, {"raw": raw}, None
    except urllib.error.HTTPError as e:
        return e.code, None, f"HTTP {e.code}"
    except Exception as e:
        return 0, None, str(e)[:160]


def ollama_chat(messages, model=None):
    """Ask the model through the Sprites Ollama gateway.

    Returns {"mode": "gateway"|"mock", "text": str, "error": str|None}.
    Mock mode returns a fixed, clearly-labelled refusal to invent a
    model answer: when there is no gateway, the agent does NOT pretend
    a model spoke. The deterministic guard still decides every spend.
    """
    url = os.environ.get("OLLAMA_GATEWAY_URL", "").rstrip("/")
    model = model or os.environ.get("OLLAMA_MODEL", "glm-5.3")
    if not url:
        return {"mode": "mock", "text": "", "error": "OLLAMA_GATEWAY_URL not set"}
    status, body, err = _post_json(
        f"{url}/v1/chat/completions",
        {"model": model, "messages": messages, "temperature": 0.2},
    )
    if err or status != 200 or not body:
        return {"mode": "mock", "text": "", "error": err or f"HTTP {status}"}
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {"mode": "mock", "text": "", "error": "unexpected gateway reply shape"}
    return {"mode": "gateway", "text": text, "error": None}


def _pinecone_embed(text):
    """Embed one text through the gateway's Pinecone inference path.

    Returns (vector_or_None, error_or_None). The gateway path is
    POST {PINECONE_GATEWAY_URL}/inference/embed; it is unproven until
    the live-Sprite run confirms it — a failure here falls back to
    local memory, it is never faked.
    """
    url = os.environ.get("PINECONE_GATEWAY_URL", "").rstrip("/")
    if not url:
        return None, "PINECONE_GATEWAY_URL not set"
    status, body, err = _post_json(
        f"{url}/inference/embed",
        {"model": PINECONE_EMBED_MODEL, "inputs": [{"text": text}]},
    )
    if err or status != 200 or not body:
        return None, err or f"HTTP {status}"
    try:
        return body["data"][0]["values"], None
    except (KeyError, IndexError, TypeError):
        return None, "unexpected embed reply shape"


def pinecone_query(text, top_k=3):
    """Find similar past spends/attacks in Pinecone memory.

    Returns {"mode": "gateway"|"mock", "matches": [...], "error": ...}.
    Gateway mode embeds the text through the gateway, then queries
    the vector index at {gateway}/indexes/{index}/query. Mock mode
    returns no matches and the caller uses the local memory file.
    """
    url = os.environ.get("PINECONE_GATEWAY_URL", "").rstrip("/")
    index = os.environ.get("PINECONE_INDEX", DEFAULT_PINECONE_INDEX)
    if not url:
        return {"mode": "mock", "matches": [], "error": "PINECONE_GATEWAY_URL not set"}
    vector, err = _pinecone_embed(text)
    if err:
        return {"mode": "mock", "matches": [], "error": err}
    status, body, err = _post_json(
        f"{url}/indexes/{index}/query",
        {"vector": vector, "topK": top_k, "includeMetadata": True},
    )
    if err or status != 200 or not body:
        return {"mode": "mock", "matches": [], "error": err or f"HTTP {status}"}
    matches = body.get("matches") or body.get("results") or []
    return {"mode": "gateway", "matches": matches, "error": None}


def pinecone_upsert(record_id, text, metadata):
    """Store one decision in Pinecone memory. Returns (mode, error).

    Gateway mode embeds the text through the gateway, then upserts
    the vector at {gateway}/indexes/{index}/vectors/upsert.
    """
    url = os.environ.get("PINECONE_GATEWAY_URL", "").rstrip("/")
    index = os.environ.get("PINECONE_INDEX", DEFAULT_PINECONE_INDEX)
    if not url:
        return "mock", "PINECONE_GATEWAY_URL not set"
    vector, err = _pinecone_embed(text)
    if err:
        return "mock", err
    status, _body, err = _post_json(
        f"{url}/indexes/{index}/vectors/upsert",
        {"vectors": [{"id": record_id, "values": vector, "metadata": metadata}]},
    )
    if err or status != 200:
        return "mock", err or f"HTTP {status}"
    return "gateway", None


def _box_folder_id(folder_name):
    """Find a folder by name under the Box root, creating it if absent.

    Returns (folder_id_or_None, error_or_None). Uses the Box paths
    proven live from a Sprite: GET /2.0/folders/0/items, then
    POST /2.0/folders with {"name": ..., "parent": {"id": "0"}}.
    """
    url = os.environ.get("BOX_GATEWAY_URL", "").rstrip("/")
    status, body, err = _get_json(f"{url}/2.0/folders/0/items")
    if err or status != 200 or not body:
        return None, err or f"HTTP {status}"
    for entry in body.get("entries") or []:
        if entry.get("type") == "folder" and entry.get("name") == folder_name:
            return entry.get("id"), None
    status, body, err = _post_json(
        f"{url}/2.0/folders",
        {"name": folder_name, "parent": {"id": "0"}},
    )
    if err or status != 201 or not body:
        return None, err or f"HTTP {status}"
    return body.get("id"), None


def box_upload(filename, content, folder=None):
    """File one receipt in Box. Returns (mode, error).

    Uploads through the Box gateway paths proven live from a Sprite:
    the receipt folder is found (or created) under the Box root, then
    the file is uploaded with a multipart POST to
    {BOX_GATEWAY_URL}/upload/files/content. Content is a JSON receipt;
    nothing secret is in it (amounts, verdicts, timestamps, no keys).
    """
    url = os.environ.get("BOX_GATEWAY_URL", "").rstrip("/")
    folder = folder or os.environ.get("BOX_FOLDER", "SpriteGuard receipts")
    if not url:
        return "mock", "BOX_GATEWAY_URL not set"
    folder_id, err = _box_folder_id(folder)
    if err:
        return "mock", err
    if isinstance(content, str):
        content = content.encode("utf-8")
    status, _body, err = _post_multipart(
        f"{url}/upload/files/content",
        [
            (
                "attributes",
                None,
                "application/json",
                json.dumps(
                    {"name": filename, "parent": {"id": folder_id}}
                ).encode("utf-8"),
            ),
            ("file", filename, "application/json", content),
        ],
    )
    if err or status != 201:
        return "mock", err or f"HTTP {status}"
    return "gateway", None
