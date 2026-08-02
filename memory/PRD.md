# MidGate — Product Requirements & Progress

## Product
**MidGate** — SaaS gateway between visitors and destinations. Tagline: *Every Click. Protected.*
Smart Links, Dynamic QR, Traffic Analytics, Visitor Intelligence, Traffic Protection, Bot/Proxy/VPN/Tor detection, Security Rules, Custom Domains, Developer API, Webhooks, Team Workspaces, Billing (QRIS), Admin.

## Implemented — Iteration 8: Team Invitations + Branded Preview + Webhook Retry (2026-08-02)
- **Team Invitations** (`backend/app/domains/team.py`): owner/admin invite members by email with role (admin/member/billing_manager) using opaque `secrets.token_urlsafe` tokens (14-day TTL). Public lookup, authenticated accept (invited email must match signed-in account → prevents privilege escalation), idempotent accept, revoke. Member management: change role & remove with owner-protection guards; all mutations RBAC-gated (owner/admin, else 403). UI: `pages/TeamPage.jsx` + `pages/AcceptInvitePage.jsx` (public route `/accept-invite`), `nav-team`. Post-auth redirect via `localStorage 'midgate_invite'` in Login/Register. Invite emails via ConsoleEmailProvider; accept link/token returned to inviter for demo.
- **Branded Link Preview**: when a workspace has a verified PRIMARY custom domain (`workspace.primary_domain` surfaced in `/auth/me`), Smart Link & QR lists display + copy `https://{domain}/{alias}` (helper `brandedShortUrl` in `lib/api.js`). QR still encodes the functional short URL.
- **Webhook Manual Retry**: `deliver()` persists the payload `data`; `POST /api/webhooks/{id}/deliveries/{delivery_id}/retry` re-delivers as a new record. UI: retry button (`delivery-retry-{id}`) on failed rows in the deliveries dialog.
- Tested: backend 11/11 pytest + frontend e2e, 100% pass (iteration_8.json). No open bugs. Credentials: teammate@example.com / Teammate123!.


## Implemented — Iteration 7: Webhooks + Custom Domains (2026-08-02)
- **Webhooks** (`backend/app/domains/webhooks.py`): per-workspace endpoints receive HMAC-SHA256 signed JSON for events `click.recorded`/`click.blocked`/`click.challenged`. Signature header `X-MidGate-Signature: t=<ts>,v1=<hmac(secret, ts.body)>`. Delivery with 3-attempt retry (0/2/5s), persisted delivery log, test-ping, enable/disable, rotate-secret (secret shown once). Wired to the EventBus `link.clicked` at startup (fire-and-forget, never blocks redirect). URL SSRF-guarded via `url_safety.validate_destination`. UI: Webhooks card on Developers page (`components/WebhooksSection.jsx`).
- **Custom Domains** (`backend/app/domains/custom_domains.py`): bring-your-own-domain with REAL DNS TXT verification (dnspython), CNAME + TXT setup instructions, set-primary (guarded until verified), owner/admin-only RBAC. `workspace.primary_domain` surfaced in `/auth/me`. Config `EDGE_HOST`, `DOMAIN_VERIFY_PREFIX`. UI: `pages/DomainsPage.jsx` + `nav-domains` (owner/admin). NOTE: serving live traffic on a custom domain needs DNS pointed to MidGate's edge (infra step outside preview); verification + management are fully functional.
- Tested: backend 18/18 pytest + frontend e2e, 100% pass (iteration_7.json). No open bugs.


## Implemented — Iteration 5: Protection Presets + Country Geo (2026-08-02)
- **Protection Presets** (one-click security): `off` (log only), `moderate` (block bots + Tor), `strict` (block bots, Tor, datacenter, proxy/VPN). Defined server-side in `security.py` (`PROTECTION_PRESETS` + `PRESET_META`), exposed via `GET /api/security/presets`. Selectable at link creation (`LinkCreate.protection_preset`) and switchable on the link detail page. `GET/PATCH /api/links/{id}/protection` carry a `preset` field; manual toggle changes auto-switch preset to `custom`. Legacy links infer preset (`off` if disabled, else `custom`).
- **Country Geo Detection** (free, offline, no API key): `geoip2fast` bundled DB resolves real visitor country. `app/geoip.py` (`country_of`, warmed at startup); `security.build_signals` fills country from IP when CDN header is absent/Unknown, so per-link `block_countries`/`allow_countries` now apply to real traffic. Verified: 114.4.5.6→ID, 8.8.8.8→US, 1.1.1.1→AU.
- Tested: backend 16/16 pytest + frontend e2e, 100% pass (iteration_5.json). No open bugs.


## Platform / Architecture (adapted)
Original spec asked for Go + Next.js + PostgreSQL + Redis monorepo. The Emergent preview only runs **React + FastAPI + MongoDB** live, so — per user approval (option A) — MidGate is built as a genuinely working app on that stack while keeping the spec's architecture principles:
- Modular monolith: `backend/app/domains/{auth,workspace,links,analytics,redirect,billing}` with handler→service→repository separation and cross-domain access via exported service functions.
- Provider abstractions in `backend/app/providers.py`: `EventBus` (InMemory), `AnalyticsStore` (Mongo, ClickHouse-ready), `EmailProvider` (Console/Mailpit-ready), `IPIntelProvider`, `PaymentProvider` (Mock QRIS). No SDK types leak into business logic.
- Redirect logic isolated in its own module + cache layer + health endpoint (mirrors separate Redirect Service).
- Tenant scoping: every resource carries `workspace_id`; repositories filter by it; cross-tenant access returns 404.

## Personas
- **End user / marketer** — creates and shares smart links, watches analytics.
- **Workspace owner/admin** — manages workspace, team (future), billing (future).
- **Platform admin** — `admin@midgate.io` (admin dashboard is a future milestone).

## Core requirements (static, from spec)
Full spec covers 38 sections / 10 milestones (auth, tenancy, links, QR, analytics, protection, billing/QRIS, developer API, webhooks, domains, admin, privacy, security, observability, CI/CD).

## Implemented — MidGate Protect Pro (2026-08-02)
- **Threat intelligence** (`app/intel.py`): live Tor exit-node list (1,400+ nodes, refreshed on startup + admin button), curated datacenter/hosting CIDR detection, UA classification (search/social/monitoring/automation/headless), in-memory rate limiter. Behind IPIntelProvider abstraction (paid provider swappable later).
- **IP allow/block lists** (workspace-level, CIDR) + **admin global blocklist**. `evaluate_request` pipeline: allowlist → blocklist(+global) → per-link protection → rules → risk thresholds.
- **Per-link Protection** (`/links/{id}/protection`): toggles for block bots/Tor/datacenter/proxy-VPN, block countries (applied only when geo resolved), rate limit, and configurable block action (Safe fallback / block page 403 / 404 / custom redirect). UI on Link detail.
- **Public Blocker API** (`/api/v1|v2/blocker?apikey&ip&ua&url&reff`) returning allow/block JSON; hashed API keys (shown once), per-key rate limit + usage. Developers page with API key mgmt + integration snippets (cURL/PHP/Node/Cloudflare Worker).
- **Admin panel** (admin-only, `/app/admin`): overview stats + feeds refresh, security events, users, workspaces, global blocklist, API usage. Nav gated by role.
- Rules now score is_tor/is_datacenter/is_proxy/is_headless. Tested: backend 19/19 pytest, frontend all UI flows (iteration_4.json). No open bugs. Legal boundary: anti-bot/anti-abuse only (no cloaking).

## Implemented — Billing quota/receipts/roles (2026-08-02)
- **Plan Limit Enforcement**: `enforce_quota` blocks creating links (limit 10 on Free) / QR (limit 3) beyond plan with a 403 "upgrade" message; `can_record_event` stops storing analytics past the monthly limit (redirect still 302s — safe degradation). Billing page shows a Usage card with used/limit bars (red at capacity).
- **Invoice Receipts**: reportlab-generated PDF receipt at `/api/billing/invoices/{id}/receipt.pdf` (paid only); a receipt email is sent on activation (console/MOCKED). Receipt download button on paid invoices.
- **Billing Roles**: all `/api/billing/*` management endpoints require role owner/admin/billing_manager (`get_billing_workspace`); non-billing members get 403. Sidebar Billing item hidden for non-billing roles; page shows a restricted card. Register response now carries workspace role. Tested: backend 9/9 pytest; frontend verified.

## Implemented — Billing page (2026-08-02)
- **Billing** (`/app/billing`): current plan card, plan grid (Free→Enterprise), in-dashboard QRIS checkout flow (create invoice → show QRIS QR → server-side activation → workspace plan updated), invoice history. Backend `billing.py`: `/checkout`, `/subscription`, `/invoices`, `/invoices/{id}/simulate-payment` (idempotent, represents a signed provider webhook). Payment confirmation is server-side only. **MOCKED**: no real QRIS gateway — a "simulate payment" button stands in for the provider webhook. Public Pricing CTA routes logged-in users to Billing.

## Implemented — Iteration 2 (2026-08-02)
- **Dynamic QR Codes** (`/app/qr`): create/edit QR whose destination changes without reprint (encodes MidGate short URL); color/dot/corner/logo/ECC styling with live preview; PNG/SVG export; version history on destination change; pause/resume/delete; stats reuse link detail. Backend `qr.py` (stored in links collection, is_qr flag); links list excludes QR.
- **Traffic Protection** (`/app/protection`): real 0–100 risk scoring on every click + configurable rules (field/operator/value → allow/challenge/block/log_only, priority-ordered) enforced in the redirect (bot → 403 block, challenge interstitial with HMAC mg_ch token → 302); rule simulator. Backend `security.py`.
- **Analytics Filters**: date range (7/30/90/all), previous-period comparison with deltas, and per-link CSV export. Backend `analytics.py` (range filter, compare, `export.csv` resolving workspace from link + membership check).
- Tested: backend 12/12 new-feature pytest, frontend all flows (iteration_2.json). No open bugs.

## Implemented — Preview #1 (2026-08-02)Milestones 1–3 (foundation, auth, basic workspace) + a working core loop (5 Smart Links, 6 Redirect, basic 7 Analytics) + UI:
- **Auth (email/password)**: register, login, logout, /me, refresh, forgot/reset password. bcrypt hashing, JWT httpOnly cookies, brute-force lockout (5/15min, XFF-aware behind ingress). Admin seeded.
- **Workspace**: default workspace per user, workspace switcher, X-Workspace-Id scoping, cross-tenant 404.
- **Smart Links**: CRUD, custom/auto alias (unique), pause/resume/delete, search, click counter. URL safety (only http/https; blocks javascript/data/file/blob; blocks private/loopback/link-local/metadata IPs; SSRF guard).
- **Redirect service**: `GET /api/r/{alias}` → 302 (302/307/308 supported), in-memory cache + Mongo fallback, expiry & click-limit & pause handling with fallback, publishes async click event (never blocks redirect). Health at `/api/redirect/health`.
- **Analytics**: per-link + workspace overview — total clicks, unique visitors (rotating daily visitor hash, no raw IP stored), bot vs human, timeseries, country/device/browser/referrer breakdowns, recent clicks.
- **Billing (prepared only)**: `GET /api/billing/plans` (Free→Enterprise) + PaymentProvider abstraction. No real gateway.
- **UI**: landing (bento hero), pricing, login/register/forgot/reset, dashboard Overview, Smart Links list + create dialog, Link detail w/ charts, Protection preview, Settings. Light default + dark mode, EN/ID i18n, responsive. Design system per `/app/design_guidelines.json` (indigo primary, Outfit/IBM Plex Sans/JetBrains Mono).

### Test status
Backend 25/26 pytest (fixed the 1 brute-force issue; re-verified via curl). Frontend 7/7 critical E2E flows pass.

### Known limitations / MOCKED
- Email = console log (reset links appear in backend logs), not real email.
- Payments MOCKED (no QRIS gateway).
- Country = "Unknown" without a geo header (no IP-geo provider wired).
- Email verification not implemented (deferred per user).

## Backlog (prioritized)
- **P0 next**: Email verification; Dynamic QR (Milestone 6); richer analytics (date range, filters, CSV export).
- **P1**: Traffic Protection rules + risk scoring + challenge (Turnstile); Security Rule Builder; Team invitations & roles.
- **P1**: Billing + QRIS real provider; usage limits enforcement per plan.
- **P2**: Developer API keys + OpenAPI + SDKs; Webhooks; Custom Domains; Admin dashboard; Notification Center; Global search; Plugins; AI insights; White label.

## Next tasks (say "Continue to Milestone 2" style to proceed)
1. Email verification + resend + login notification.
2. Dynamic QR codes (types, customization, export).
3. Traffic Protection MVP (risk score + rules + block/challenge).
