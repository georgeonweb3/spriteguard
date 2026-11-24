# Running SpriteGuard on a Fly.io Sprite

SpriteGuard is built for a Sprite: a hardware-isolated Linux computer
that checkpoints itself, so the ledger and the memory survive restarts.
There is no `fly.toml` and no Dockerfile in this repo because a Sprite
is not a Fly Machine app — it is a Linux box you copy code onto. Do not
invent a deploy manifest; follow the dashboard steps below.

## 0. What you need

- A Fly.io account (the hackathon requires one). Sign up at fly.io.
  The free plan covers this: $5 of usage a month, up to 3 Sprites.
- No card is needed for the free plan's Sprite allowance as published
  24 Nov 2026; if Fly asks for one at sign-up, that is George's step,
  not a build step. Nothing in this repo pays anything.
- One Sprite, created in the Fly.io dashboard under Sprites.

## 1. Create the Sprite

Dashboard → Sprites → create a Sprite. It ships with Claude Code,
Codex, Gemini CLI, Antigravity, Cursor, Pi and Grok already installed.
Copy this repo onto it (git clone, or upload the folder):

```sh
git clone https://github.com/georgeonweb3/spriteguard.git
cd spriteguard
python3 agent/sprite_agent.py demo
```

The demo needs nothing else: Python 3.12 standard library only, no
pip installs, no keys, no wallet. If the demo prints the $48 BLOCK,
the $5 ALLOW and the $99 BLOCK, the Sprite is ready.

## 2. Add the three connectors (dashboard, not code)

Dashboard → Sprites → Connectors. Add one of each, then allow **this
Sprite** to use each of them (new connectors block every Sprite until
you allow one — if your first gateway call fails, check the allow list
before pasting any key anywhere):

1. **Ollama** — the brain. The gateway adds your Ollama key after it
   checks which Sprite is calling. The Sprite only ever sees a gateway
   URL and a connection id. The dashboard connector page shows the curl
   with your connection id filled in; copy that URL.
2. **Pinecone** — the memory. Reads, writes and queries vectors in a
   Pinecone index by name, and generates embeddings with Pinecone's
   hosted models. Create the index `spriteguard-memory` (or set
   `PINECONE_INDEX` to your index name).
3. **Box** — the receipts vault. Manages files in a Box account from
   the Sprite. Every verdict, including every refusal, is filed there
   as a JSON receipt.

Keys are never accessible to the Sprite and never live on it. That is
the point of the gateway, and it is also why the agent can hold a
spend guard at all: a stolen Sprite still holds no key worth stealing.

## 3. Set the env vars on the Sprite

```sh
export OLLAMA_GATEWAY_URL="https://api.sprites.dev/v1/gateway/ollama/<your-connection-id>"
export OLLAMA_MODEL="glm-5.3"
export PINECONE_GATEWAY_URL="<URL from your Pinecone connector page>"
export PINECONE_INDEX="spriteguard-memory"
export BOX_GATEWAY_URL="<URL from your Box connector page>"
export BOX_FOLDER="SpriteGuard receipts"
```

Optional policy overrides (defaults: $25 per spend, $100 per day):

```sh
export SPRITEGUARD_POLICY='{"per_tx_cap_cents": 2500, "daily_limit_cents": 10000}'
```

## 4. Run it

```sh
# One proposal, judged on the spot:
echo '{"tool":"pay_api","args":{"amount_usd":5,"recipient":"vendor.example"}}' \
  | python3 agent/sprite_agent.py propose

# Or serve it (localhost only) for other tools on the Sprite to call:
python3 agent/sprite_agent.py serve --port 8080
# GET  /         -> today's spend, memory size, receipt count
# POST /propose -> {"tool": ..., "args": {...}, "task": "..."}
```

## 5. Prove it on the Sprite

```sh
sh eval/run_all.sh
```

This runs the vendored 49-test Aegis suite, the 15-attack adversary
eval, and the demo, and writes `evidence/eval-2026-11-24.log`. The
numbers in the README are the output of that script, run 24 Nov 2026.
Re-run it on the Sprite; the guard and the eval do not need the
gateway, so they pass identically there.

## What is NOT done yet

- The agent has not run on a live Sprite in this session: there is no
  Fly.io account attached to this build, and Sprite creation needs the
  owner's sign-in. The code is Sprite-ready and verified locally in
  mock-gateway mode; the first live-Sprite run (steps 1–4 above) is a
  15-minute job for the account owner.
- Pinecone and Box gateway payloads are written to the vendors' public
  REST shapes and fall back to local files on any non-200. They are
  flagged unverified until the first live-Sprite run confirms the exact
  gateway URL shapes from the dashboard connector pages. The Ollama
  chat path is verified against Ollama's published Sprites post.
