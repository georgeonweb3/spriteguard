"""Local memory fallback for SpriteGuard.

Used ONLY when the Sprites Pinecone gateway is not configured or
unreachable. Same interface the agent uses for Pinecone: store a
decision, find similar past decisions by keyword overlap. This is
plain keyword matching, not embeddings -- it is labelled "mock" in
every output so a local run is never presented as a Pinecone run.

On a live Sprite with the Pinecone connector configured, this file is
never touched: memory lives in the Pinecone index named by
PINECONE_INDEX (default: spriteguard-memory).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_STOP = set("a an the to of for on in is it and or pay payment please".split())


def _words(text):
    return set(w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if w not in _STOP)


class LocalMemory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records = []
        if self.path.exists():
            try:
                self.records = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self.records = []

    def _save(self):
        self.path.write_text(json.dumps(self.records, indent=2))

    def upsert(self, record_id, text, metadata):
        self.records = [r for r in self.records if r.get("id") != record_id]
        self.records.append({"id": record_id, "text": text, **metadata})
        self._save()

    def query(self, text, top_k=3):
        hay = _words(text)
        scored = []
        for r in self.records:
            overlap = len(hay & _words(r.get("text", "")))
            if overlap:
                scored.append((overlap, r))
        scored.sort(key=lambda t: -t[0])
        return [r for _s, r in scored[:top_k]]
