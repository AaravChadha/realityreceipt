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

## Deploy

The deployed app is one Render web service. The API serves the built web app at `/` and every route under `/api` (task 2.7.1), so the page and the API share one HTTPS address. `render.yaml` at the repo root describes the service. The quick tunnel above stays as the backup.

### Create the service (once)

1. In the Render Dashboard, create a new Blueprint, connect the GitHub repo `AaravChadha/realityreceipt`, and pick the `main` branch. Render reads `render.yaml` from the repo root.
2. Render asks for each variable marked `sync: false`. Enter `XAI_API_KEY` and `XAI_MODEL`, the same values as in your `api/.env`. They live only in the service's environment settings on Render. Never put them in `render.yaml`, a commit or a PR.
3. Create it. The first deploy runs the build and start commands below.

What `render.yaml` sets:

| Setting | Value |
|---|---|
| Runtime and plan | `python`, `free`, region `virginia` |
| Build | `node --version && pip install -r api/requirements.txt && npm --prefix web ci && npm --prefix web run build` |
| Start | `uvicorn` on `app.main:app`, with `--app-dir api --host 0.0.0.0 --port $PORT` (the exact line is `startCommand` in `render.yaml`) |
| Health check | `/api/health` |
| Python | `PYTHON_VERSION` `3.12.14`, the version CI runs. Render's default for new services is 3.14.3. |
| Deploys | `autoDeployTrigger: checksPass`: a commit to `main` deploys only after its `ci` check passes. |
| Secrets | `XAI_API_KEY`, `XAI_MODEL`, entered in the Dashboard (`sync: false`) |

Notes on those commands:
- **Start:** this is Render's own FastAPI pattern: `pip install` at build time, then `uvicorn` called directly. `api/.venv` is gitignored and never exists on Render, so the start command does not use `api/.venv/bin/uvicorn`.
- **Port:** Render says "Every Render web service must bind to a port on host `0.0.0.0`", and `PORT` defaults to `10000`.
- **Node:** Render's native runtimes come with `node` and `npm`. Vite 8 needs Node `^20.19.0` or `>=22.12.0`. The build's first step prints the Node version. If it is older than that, the build fails at `npm --prefix web ci` with an engine error. Render documents `NODE_VERSION` for pinning Node, but its docs do not say whether that applies to a Python service.
- **xAI key:** Render has no `api/.env` file. The Grok client (task 3.7) must read `XAI_API_KEY` and `XAI_MODEL` from the process environment, for example `load_dotenv()` followed by `os.getenv(...)`, not from the file alone.

Check: the service's own address, `https://<service>.onrender.com/api/health`, prints `{"ok":true}`, and `https://<service>.onrender.com/` shows the entry page. The Dashboard shows the exact `onrender.com` address; it is `realityreceipt.onrender.com` only if that name was free.

### Point the .tech domain at it

A CNAME record cannot sit on a domain's root, so the app lives at `www.<name>.tech`, and the root redirects there.

1. Claim the domain through MLH's free .tech offer. Open the DNS settings for it at the .tech registrar.
2. In Render, open the service's **Settings**, go to **Custom Domains**, and add `www.<name>.tech`. Render says that when you add a www subdomain, it "automatically adds the corresponding root domain and redirects it to the www subdomain".
3. At the registrar, add these records:

   | Type | Host | Value |
   |---|---|---|
   | `CNAME` | `www` | the service's `onrender.com` address, e.g. `realityreceipt.onrender.com` |
   | `A` | `@` (the root) | `216.24.57.1`, Render's load balancer. Use an `ALIAS` or `ANAME` record pointing at the `onrender.com` address instead, if the registrar offers one. |

   Then delete any `AAAA` records on the domain. Render says to "Remove any `AAAA` records from your domain while configuring DNS."
4. Back in Render, click **Verify** next to the domain. When verification succeeds, Render issues the TLS certificate. If it fails, wait a few minutes for DNS to update and try again.

A Hobby workspace includes 2 custom domains; each one beyond that is $0.25 a month.

Check (task 2.11.1's acceptance, by hand): a phone on mobile data, not Wi-Fi, opens `https://www.<name>.tech/`, and `https://www.<name>.tech/api/health` prints `{"ok":true}`.

### Keep it awake during judging

Render "spins down a Free web service that goes 15 minutes without receiving any inbound traffic". It starts again on the next request, which "takes about one minute". Pick one of these:

- **A paid instance type for judging (surest).** Before judging, open the service's **Settings** and change its instance type to a paid one. Render says: "To remove the Free instance limitations described below, you can upgrade your service to any paid compute plan." Change it back to Free afterwards.
- **Stay free, and keep requests coming.** Set up an uptime monitor to request `https://www.<name>.tech/api/health` every 5 to 10 minutes. Render counts inbound HTTP requests as activity. One service running all month fits within the "750 Free instance hours" each workspace gets per month. If a workspace uses them all, Render "suspends all of your Free web services until the start of the next month".

Either way, 10 minutes before judges arrive, open `https://www.<name>.tech/api/health` and wait for `{"ok":true}`.

### When the deploy does not work

- **The build log shows `vite: not found`, or `tsc` is missing.** `npm ci` skipped the dev dependencies, which it does when `NODE_ENV=production` is set. Remove that variable from the service's environment.
- **`/api/health` works but `/` returns 404.** `web/dist/index.html` was not built. The API serves the web app only when that file exists at start-up. Check the `npm --prefix web run build` step in the build log.
- **Scans fail with a missing-key error.** `XAI_API_KEY` or `XAI_MODEL` is not set in the service's environment settings, or the Grok client reads only `api/.env` (see the note under "Create the service").
- **The first request after a quiet spell takes about a minute.** The free service spun down. See "Keep it awake during judging".

Sources, read 2026-09-26: https://render.com/docs/blueprint-spec, https://render.com/docs/python-version, https://render.com/docs/node-version, https://render.com/docs/native-runtimes, https://render.com/docs/web-services, https://render.com/docs/deploy-fastapi, https://render.com/docs/free, https://render.com/docs/custom-domains, https://render.com/docs/configure-other-dns
