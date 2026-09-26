# Runbook: run the app and open it on a phone

This starts three things, each in its own terminal:
- the API on port 8000;
- the web dev server on port 5173, which forwards `/api/...` to the API with the `/api` prefix removed;
- a Cloudflare quick tunnel, which gives the dev server a public HTTPS address on `trycloudflare.com` that a phone can open from any network.

Run every command from the root of the checkout or worktree you are testing.

## Once per machine or worktree

- Set up the worktree as in AGENTS.md "Team workflow" step 2. That creates `api/.venv` with the pinned requirements and runs `npm --prefix web ci`.
- Install `cloudflared`: on macOS, `brew install cloudflared`. Then check that `cloudflared --version` prints a version. No Cloudflare account is needed for a quick tunnel.

## Start it

**Terminal 1, the API:**

```
api/.venv/bin/uvicorn app.main:app --app-dir api --port 8000
```

Check: `curl http://localhost:8000/health` prints `{"ok":true}`.

**Terminal 2, the web dev server:**

```
npm --prefix web run dev
```

Check: `curl http://localhost:5173/api/health` prints `{"ok":true}`. This goes through the dev server's proxy to the API, which is the same path the phone uses.

**Terminal 3, the tunnel:**

```
cloudflared tunnel --url http://localhost:5173
```

It prints an address ending in `.trycloudflare.com`. Open that `https://` address in the phone's browser. The address is new every time the tunnel starts.

## The phone check (Phase 2 exit)

On the phone, type a refrigerator on the entry form and submit it. The receipt should appear with no "Sample data, not a real quote" banner. That banner means the API returned the sample fixture instead of a real quote.

This check needs the rest of Phase 2 on `main`, at least tasks 2.6 to 2.9. Before they land, the phone shows only what is built so far.

## When it does not work

- **The phone says the host is not allowed.** `web/vite.config.ts` must keep `.trycloudflare.com` in `server.allowedHosts`.
- **The page loads but API calls fail.** Terminal 2 logs a proxy error. The API is not running on port 8000: start terminal 1 first.
- **The tunnel will not start.** Cloudflare's quick tunnels "are currently not supported if a config.yaml configuration file is present in the .cloudflared directory". Move `~/.cloudflared/config.yaml` aside while demoing.
- **Requests fail under load, or live updates do not arrive.** Quick tunnels have "a hard limit on the number of concurrent requests" (200 at a time, then HTTP 429) and "do not support Server-Sent Events (SSE)". Cloudflare also says: "We don't guarantee any SLA or uptime of TryCloudflare." If the tunnel drops, restart terminal 3 and open the new address. Source: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/

## Stop it

Press Ctrl+C in each terminal. The tunnel address stops working as soon as terminal 3 stops.
