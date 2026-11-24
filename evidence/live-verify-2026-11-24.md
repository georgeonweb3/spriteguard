# Live verification — SpriteGuard connectors on a fresh Sprite — 2026-11-24

Runbook: `evidence/LIVE-VERIFY-RUNBOOK.md`. Repo head: commit `5c73692e`
("Connectors live: Box documented paths, Pinecone vector paths + embed,
run_all.sh portable").

## Sprite

- Name: `web-terminal`
- ID: `sprite-1002d3af-b13d-4a29-b19b-b927af184576`
- Org: `george-codm` (Fly.io account `georgeterlumun3@gmail.com`)
- Created: 24 Nov 2026, about 19:35 UTC (20:35 WAT); run 19:37-19:40 UTC.
- Google pre-sign-in confirmed first at myaccount.google.com as George CODM
  (`georgeterlumun3@gmail.com`).
- Connector access (both connectors, checked on their Fly dashboard detail
  pages): Name Prefix `web-terminal`, "Allow all sprites" NOT enabled
  (unchecked), Authorized Sprites (1): `web-terminal`, Live. No change was
  needed — the prefix grant already allowed only this Sprite.
- Env vars set on the Sprite from the connector detail pages (gateway URLs
  are not recorded here): `PINECONE_GATEWAY_URL`,
  `PINECONE_INDEX="spriteguard-vectors"`, `BOX_GATEWAY_URL`,
  `BOX_FOLDER="SpriteGuard receipts"`.
- Ollama was NOT part of this run (blocked); the agent ran in mock-model mode.
- No Pinecone API key was put on the Sprite or in any file. Nothing in Box
  was deleted. Nothing was paid.

## `sh eval/run_all.sh`

- Completed, exit 0. Log: `evidence/eval-2026-11-24.log` (overwritten by the run).
- Guard suite: 56/56 tests OK (0.550s).
- Adversary: 15/15 attacks stopped, $0.00 taken, controls 2/2 allowed.
- Demo in the eval: $5.00 moved, $48 refused, $5 bill paid, $99 hijack $0.00.

## Box: LIVE

- Demo printed `receipt: gateway` on all 3 steps (3/3 in the standalone demo
  run, and in the eval demo run).
- `GET /2.0/folders/0/items` — HTTP 200. Root lists one folder,
  "SpriteGuard receipts" (id `440773899785`).
- `GET /2.0/folders/440773899785/items` — HTTP 200, `total_count` 7:
  the pre-existing `spriteguard-probe.json` (left alone) plus 6 new receipt
  files written by this run:
  - Eval demo: `20261124T193711Z-pay_api-3232.json`,
    `20261124T193715Z-pay_api-2933.json`, `20261124T193718Z-pay_api-1395.json`
  - Standalone demo: `20261124T193836Z-pay_api-7862.json`,
    `20261124T193839Z-pay_api-0366.json`, `20261124T193841Z-pay_api-6162.json`
- Box writes landed in the live Box folder. Box is the live connector story.

## Pinecone: FALLBACK

- Gateway is live and authenticated: `GET /indexes` — HTTP 200, lists only
  `spriteguard-memory` (dense, cosine, 1024, Ready). No other index listed.
- Create index, `POST /indexes` with name `spriteguard-vectors`, dimension
  1024, metric cosine, serverless aws us-east-1 — HTTP 403, exact body:
  `{"error":"endpoint is not supported by the Pinecone connector"}`.
  `spriteguard-vectors` was NOT created.
- Embed, `POST /inference/embed` with model `llama-text-embed-v2`, inputs
  `[{"text": "test spend"}]` — HTTP 403, exact body:
  `{"error":"endpoint is not supported by the Pinecone connector"}`.
  No `data[0].values`, no 1024-number vector.
- Pinecone memory therefore stayed on local fallback (the connector code
  falls back to the local store on any non-200 embed and never fakes a live
  call). No live embed, upsert or query was recorded.
- The index was NOT created any other way in this run, per the runbook.
  The `spriteguard-memory` index was not touched or deleted.
- Fallback note: Box is the live connector story; the README already says
  so honestly — no code change needed, only this record.

## Standalone demo: `python3 agent/sprite_agent.py demo`

- Completed, exit 0. Each step printed `receipt: gateway` (Box).
- Result: $5.00 moved, $48 BLOCK, $99 BLOCK, $0.00 taken.
- Note: the standalone run started with "Spent today: $5.00" because demo
  state persisted from the eval demo run in the same Sprite; the per-run
  result was still $5.00 moved, $48 BLOCK, $99 BLOCK, $0.00 taken.

## Cleanup

- Sprite `web-terminal` (`sprite-1002d3af-b13d-4a29-b19b-b927af184576`) was
  deleted after this record was pushed; the Fly Sprites page for org
  `george-codm` was confirmed empty afterwards, so nothing keeps billing.
