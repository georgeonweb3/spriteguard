"""Sprites gateway clients for SpriteGuard.

Everything here talks to Fly.io Sprites *connectors* through the gateway,
never with a key on the Sprite. The Sprites dashboard shows each
connector's gateway URL with your connection id filled in; paste that URL
into the env var. No API key, token, or secret is ever stored on the
Sprite, in this repo, or in the ledger.

Verified facts these clients rely on (see README "Sources"):
- Ollama connector: the gateway adds your Ollama key after checking which
  Sprite is calling. The Sprite only sees a gateway URL and a connection
  id. Chat path: POST {OLLAMA_GATEWAY_URL}/v1/chat/completions with an
  OpenAI-compatible body. (Ollama, "Fly.io Sprites", 13 Oct 2026.)
- Pinecone connector: reads, writes and queries vectors in a Pinecone
  index by name, and generates embeddings with Pinecone's hosted models.
  (Fly.io changelog, "Another batch of Sprites connectors".)
- Box connector: manages files in a Box account, including downloading
  those files to your Sprite. (Fly.io community, "More Sprites Connectors:
  Nebius, Box, and Nscale".)

What is NOT verified yet: the exact Pinecone and Box gateway URL shapes
(the dashboard shows them at setup time). Those two clients therefore
POST the vendor's public REST-shaped JSON to the dashboard-provided URL
and treat any non-200 as "connector unavailable", falling back to the
local store and logging the mode. The guard, the ledger, and the Ollama
chat call do not depend on them. See README "What is real and what is
not".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

TIMEOUT = 20


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


def pinecone_query(text, top_k=3):
    """Find similar past spends/attacks in Pinecone memory.

    Returns {"mode": "gateway"|"mock", "matches": [...], "error": ...}.
    Gateway mode sends the text to the Pinecone connector and asks for
    Pinecone-hosted embeddings + a query (integrated inference). Mock
    mode returns no matches and the caller uses the local memory file.
    """
    url = os.environ.get("PINECONE_GATEWAY_URL", "").rstrip("/")
    index = os.environ.get("PINECONE_INDEX", "spriteguard-memory")
    if not url:
        return {"mode": "mock", "matches": [], "error": "PINECONE_GATEWAY_URL not set"}
    status, body, err = _post_json(
        url,
        {"index": index, "inputs": {"text": text}, "topK": top_k},
    )
    if err or status != 200 or not body:
        return {"mode": "mock", "matches": [], "error": err or f"HTTP {status}"}
    matches = body.get("matches") or body.get("results") or []
    return {"mode": "gateway", "matches": matches, "error": None}


def pinecone_upsert(record_id, text, metadata):
    """Store one decision in Pinecone memory. Returns (mode, error)."""
    url = os.environ.get("PINECONE_GATEWAY_URL", "").rstrip("/")
    index = os.environ.get("PINECONE_INDEX", "spriteguard-memory")
    if not url:
        return "mock", "PINECONE_GATEWAY_URL not set"
    status, _body, err = _post_json(
        url,
        {"index": index, "id": record_id, "inputs": {"text": text}, "metadata": metadata},
    )
    if err or status != 200:
        return "mock", err or f"HTTP {status}"
    return "gateway", None


def box_upload(filename, content, folder=None):
    """File one receipt in Box. Returns (mode, error).

    The Box connector manages files in a Box account from the Sprite.
    The gateway URL comes from the dashboard connector page. Content
    is a JSON receipt; nothing secret is in it (amounts, verdicts,
    timestamps, no keys).
    """
    url = os.environ.get("BOX_GATEWAY_URL", "").rstrip("/")
    folder = folder or os.environ.get("BOX_FOLDER", "SpriteGuard receipts")
    if not url:
        return "mock", "BOX_GATEWAY_URL not set"
    status, _body, err = _post_json(
        url,
        {"folder": folder, "filename": filename, "content": content},
    )
    if err or status != 200:
        return "mock", err or f"HTTP {status}"
    return "gateway", None
