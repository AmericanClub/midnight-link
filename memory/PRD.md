# MidGate — Product Requirements & Progress

## Product
**MidGate** — SaaS gateway between visitors and destinations. Tagline: *Every Click. Protected.*
Smart Links, Dynamic QR, Traffic Analytics, Visitor Intelligence, Traffic Protection, Bot/Proxy/VPN/Tor detection, Security Rules, Custom Domains, Developer API, Webhooks, Team Workspaces, Billing (QRIS), Admin.

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
