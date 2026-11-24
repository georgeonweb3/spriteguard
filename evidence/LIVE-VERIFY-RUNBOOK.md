# Live-verify runbook — SpriteGuard connectors on a fresh Sprite

Purpose: prove the rewritten `agent/connectors.py` (Box documented
paths; Pinecone vector paths + `/inference/embed`) against the REAL Fly
gateways from a Sprite. The gateways refuse every non-Sprite caller
(HTTP 401 from any other machine), so this run cannot be done off a
Sprite — do not treat a 401 from a laptop/VM as a failure.

Prerequisites (all done 24 Nov 2026):
- Fly.io account georgeterlumun3@gmail.com, org george-codm, card on file.
- Pinecone connector Live on the Fly dashboard (index
  `spriteguard-memory` exists, free Starter). Box connector Live
  (OAuth, root_readwrite; folder "SpriteGuard receipts" already exists
  in Box with one probe file — leave both alone).
- Repo head includes this fix (`agent/connectors.py` rewritten,
  `eval/run_all.sh` diff check optional, 7 connector tests).
- Ollama is BLOCKED (Ollama sign-in returns `policy_denied`); it is
  not part of this run. The agent runs mock-model mode.

NEVER do any of these: put the Pinecone API key on the Sprite or in
any file (keys live only in the Fly connector); delete the
`spriteguard-memory` index; delete anything in Box; pay anything.

## 0. Create the Sprite and allow the connectors

1. Fly dashboard → org george-codm → Sprites → Create a Sprite.
2. On each connector's detail page (Pinecone, Box), allow THIS Sprite
   (grant access to this Sprite only — do NOT enable "Allow all
   sprites").
3. Note the Sprite name and ID.

## 1. Set env vars on the Sprite

Copy each gateway URL from its connector detail page on the Fly
dashboard (the URL carries the connection id — never paste it into
any file, chat log, or screenshot).

```sh
export PINECONE_GATEWAY_URL="<URL from your Pinecone connector page>"
export PINECONE_INDEX="spriteguard-vectors"
export BOX_GATEWAY_URL="<URL from your Box connector page>"
export BOX_FOLDER="SpriteGuard receipts"
```

## 2. Clone and run the eval

```sh
git clone https://github.com/georgeonweb3/spriteguard.git
cd spriteguard
sh eval/run_all.sh
```

Expected: the script COMPLETES (the diff check skips itself — the
vendored source is not on a Sprite). Guard suite 56/56, adversary
15/15 stopped, $0.00 taken, demo $5.00 moved. Save the log:
`evidence/eval-2026-11-24.log` (it is overwritten by the run).

## 3. Pinecone route 1 — create the plain vector index (from the Sprite)

`spriteguard-memory` has a document schema: its `/vectors/upsert`
returns HTTP 400 ("writes must go through the documents API"), so
vector calls need a plain vector index. Try creating it through the
gateway first:

```sh
curl -s -X POST "$PINECONE_GATEWAY_URL/indexes" \
  -H 'Content-Type: application/json' \
  -d '{"name": "spriteguard-vectors", "dimension": 1024, "metric": "cosine",
       "spec": {"serverless": {"cloud": "aws", "region": "us-east-1"}}}'
```

- Expected: HTTP 201, index created. Continue to step 4.
- If it fails (e.g. free-tier index limit, or the gateway blocks
  control-plane calls): record the exact status + error, skip to
  step 6's fallback note, and do NOT create the index any other way
  in this run. (The fallback is creating it in the Pinecone console
  in a browser and re-running from step 4.)

## 4. Test the embed path (from the Sprite)

```sh
curl -s -X POST "$PINECONE_GATEWAY_URL/inference/embed" \
  -H 'Content-Type: application/json' \
  -d '{"model": "llama-text-embed-v2", "inputs": [{"text": "test spend"}]}' \
  | head -c 300
```

- Expected: HTTP 200, body has `data[0].values` with 1024 numbers.
- If it returns 403 ("endpoint is not supported") or any non-200:
  record the exact status + error. Pinecone stays local-fallback
  (see step 6) — do NOT fake a live call.

## 5. Run the demo with the gateways wired

```sh
python3 agent/sprite_agent.py demo
```

Expected output lines (mock-gateway mode is gone when the gateways
answer):
- Each demo step prints `receipt: gateway` for Box (and for Pinecone
  memory, if the embed path worked in step 4).
- Demo result stays: $5.00 moved, $48 BLOCK, $99 BLOCK, $0.00 taken.

Then confirm the writes landed:

```sh
# Box: the new receipt files are in the folder
curl -s "$BOX_GATEWAY_URL/2.0/folders/0/items" | grep -o '"name": "[^"]*"'
# Pinecone: the vector index lists, and a query finds the demo record
curl -s "$PINECONE_GATEWAY_URL/indexes" | grep -o '"name": "[^"]*"'
```

## 6. Record the verdict, then delete the Sprite

Write the outcome to `evidence/live-verify-2026-11-24.md` in the repo
(and push it), using this shape:

- Sprite name/ID, date/time.
- `sh eval/run_all.sh`: completed? suite count, adversary, demo.
- Box: LIVE or fallback, with the exact statuses seen.
- Pinecone: LIVE (embed + upsert + query all 200) or FALLBACK, with
  the exact status/error that decided it, and whether
  `spriteguard-vectors` was created.
- If Pinecone fell back: Box is the live connector story; the README
  already says so honestly — no code change needed, only this record.

Then delete the Sprite (dashboard → Sprite → Delete) so nothing
keeps billing. Confirm the Sprites page is empty.

## Known answers (so the run is not re-debated)

- Box paths ARE live: probed 24 Nov 2026 from a Sprite —
  GET `/2.0/folders/0/items` 200, POST `/2.0/folders` 201,
  POST `/upload/files/content` 201.
- Pinecone gateway IS live and authenticated: GET `/indexes` 200
  from a Sprite, lists `spriteguard-memory` (dense, cosine, 1024,
  Ready).
- Pinecone `/vectors/upsert` on `spriteguard-memory` is 400 by
  design (document-schema index). The documents search endpoint is
  403 through the gateway. Neither is a code bug.
- Bare-gateway POSTs (the old code) are HTTP 403. That is fixed by
  this rewrite; a 403 on a documented path is new information,
  record it verbatim.
