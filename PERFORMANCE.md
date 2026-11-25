# Pixora Performance Baseline & Optimizations

## Measured Production Baseline (`https://pixora18.vercel.app`)

Measured via `httpx` (3 runs each, cold -> warm) and Playwright Chromium:

| Endpoint / Asset | Status | Size (B) | Times (ms) | Notes |
| --- | --- | --- | --- | --- |
| `/` | 200 | 21,108 | 1100.7, 597.4, 619.1 | Redirects to `/login` |
| `/login` | 200 | 21,108 | 513.5, 287.0, 285.9 | 11 requests, 520,622 B, LCP 1,104 ms |
| `/games` | 200 | 21,108 | 817.4, 561.9, 594.5 | Redirects to `/login` when unauthenticated |
| `/leaderboard` | 200 | 84,427 | 3487.8, 3405.0, 3366.1 | N+1 `GameScore.player` queries |
| `/play/2048` | 200 | 44,603 | 2040.8, 2042.1, 2124.4 | 14 requests, 371,537 B, LCP 2,548 ms |
| `/api/leaderboard/2048` | 200 | 940 | 2265.8, 2278.2, 2335.5 | Cross-region DB round-trips |
| `/static/Games/Images/2048.webp` | 200 | 15,640 | 93.2, 102.7, 168.4 | `cache-control: public, max-age=0, must-revalidate` |
| `/public/games/stonepapersissors/index.html` | 200 | 8,156 | 430.8, 105.6, 72.5 | Static bundle |

## Ranked Bottlenecks

1. **N+1 DB queries on `/leaderboard`** (279 SQL queries locally, 3,405 ms warm in prod).
2. **Cross-region serverless-to-DB latency** (Vercel default `iad1` vs Neon Postgres `ap-southeast-1`, plus missing `NullPool` / `connect_timeout`).
3. **Cold start overhead** (`api/index.py` running `db.create_all()`, `seed_catalog()`, and `seed_admin()` even on Postgres).
4. **Uncached static assets** (`cache-control: public, max-age=0, must-revalidate`).
5. **Health check DB query** (`/health` queried `GameScore` count on every liveness probe).

## Implemented Fixes & Local Before/After

- `vercel.json`: Pinned `regions` to `["sin1"]` (matching Neon `ap-southeast-1`) and added `Cache-Control: public, max-age=31536000, immutable` for `/static/(.*)` and `/public/(.*)`.
- `app/database.py`: Configured `NullPool`, `pool_pre_ping=True`, and `connect_timeout=5` for serverless/pooled Postgres.
- `api/index.py`: Skipped `db.create_all()`, `seed_catalog()`, and `seed_admin()` on serverless Postgres cold boots.
- `app/routers/hub.py`: Added `joinedload(GameScore.player)` to `render_hub_view` and made `/health` zero-DB (with `/health/deep` for DB + Redis checks).
- `gateway.py`: Added `Server-Timing: app;dur=...` middleware.
- `templates/Games/login.html`: Replaced unmeasured marketing claims (`0ms COLD START`, `100% EDGE STREAMED`) with honest labels.

| Route (Local SQLite) | Before (Queries / Time) | After (Queries / Time) |
| --- | --- | --- |
| `/leaderboard` | 279 queries / 2059.7 ms | 73 queries / 91.2 ms |
| `/api/leaderboard/2048` | 7 queries / 3.8 ms | 7 queries / 5.3 ms |
| `/play/2048` | 3 queries / 11.5 ms | 3 queries / 11.4 ms |
| `/health` | 1 query / 2.2 ms | 0 queries / 1.7 ms |

