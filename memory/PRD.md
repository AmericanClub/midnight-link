# Midnight Link — Product Requirements & Progress
_(formerly "MidGate" — rebranded 2026-08)_

## Implemented — Rebrand + Full Retro Redesign → "Midnight Link" (2026-08)
- **Goal (user):** rename brand MidGate → **Midnight Link**, adopt the amber/orange palette from the user's logo (a black witch-on-broom silhouette over an amber full moon), migrate public domain to **midnightlink.link**, and restyle the ENTIRE app (marketing + dashboard) to a **retro pixel-art / arcade neobrutalist** theme (modeled on build-automator.emergent.cloud) — keep both light & dark mode.
- **Design system (cascades to all pages):** `index.css` retokenized — light = warm cream + amber primary (`38 100% 50%`), dark = deep midnight-navy + glowing amber; `--nb-border`/`--nb-shadow` ink vars drive thick borders + hard offset shadows (sharp corners). Fonts: **Press Start 2P** (`.font-pixel`, headings/logo) + **Space Grotesk** (`.font-display`/body) + JetBrains Mono. Core shadcn primitives restyled neobrutalist (button, card, input, textarea, badge, dialog, tabs, switch, select, dropdown) so every page inherits the look. `Logo.jsx` uses the witch-moon `/logo.png` + pixel wordmark (`onDark` prop for dark panels).
- **Rebrand text:** frontend + backend "MidGate"→"Midnight Link", `midgate.co/.io`→`midnightlink.link`, `support@`/`noreply@` updated, receipt PDF, wallet top-up description, auth/team emails, redirect interstitial, analytics CSV. Functional identifiers renamed for consistency: webhook HTTP headers `X-MidGate-*`→`X-MidnightLink-*` (webhooks.py + partner_pay.py) and DNS verify token `midgate-verify`→`midnightlink-verify` (+ `DOMAIN_VERIFY_PREFIX`, `EDGE_HOST` defaults). **PRESERVED (unchanged):** visitor-hash salt `midgate-salt` (utils.py), logger names `midgate.*`, `ADMIN_EMAIL`/`ADMIN_PASSWORD` env (admin login stays **admin@midgate.co / Admin123!**), `LEGACY_ADMIN_EMAILS`. `.env` `CORS_ORIGINS` now also includes `https://midnightlink.link` + `www`. Existing admin DB display name updated to "Midnight Link Admin".
- **Landing redesigned:** pixel hero + "risk-engine" console card w/ floating chips, flow strip, Protection Stats bars (arcade "player stats" homage), features bento, night-panel CTA, retro footer. AuthShell, PublicNav, DashboardLayout, Pricing, Admin Console all retro.
- **Enhancements (user: "kerjakan semua"):** (1) **404 "GAME OVER"** page (respawn/dashboard buttons, witch-moon); (2) **Neobrutalist Sonner toasts** (thick border + hard shadow + uppercase title, via `[data-sonner-toast]` CSS); (3) **Pixel loading skeleton** (`.nb-skeleton` stepped shimmer); (4) **Arcade click sound** (Web Audio blip via `SoundContext` global click listener) + **SoundToggle** (data-testid `sound-toggle-btn`) in PublicNav/DashboardLayout/AuthShell, persisted in localStorage `ml-sound`.
- **Tested:** Backend regression **15/15 PASS** (health, admin login, links/wallet/admin endpoints, webhook header renamed to X-MidnightLink-Signature, DNS token renamed). Frontend automated test **PASS** (landing/CTAs, theme toggle, auth + error toast, admin console, 404 GAME OVER, public pages, no "MidGate" visible, logo loads). Verified via screenshots in light + dark.
- **Operator note:** domain `midnightlink.link` is added to CORS but not yet live; when deploying, set deployment env (`FRONTEND_URL`, optionally `ADMIN_EMAIL`) and point Mayar webhook to the new domain.


## Implemented — Payment (wallet top-up) master switch (2026-06)
- **Goal (user):** be able to turn the wallet top-up payment system OFF from Admin until cheaper payment gateways are approved (Mayar fee ~5%/txn). Scope: **only Wallet top-up** (customer billing) — partner "midnight" `/api/pay` charges are NOT affected.
- **Backend:** setting stored in `db.platform_settings` `_id="payments"` `{topup_enabled, topup_disabled_message}` via `wallet.get_payment_settings()/set_payment_settings()`. Default enabled; default message "Pembayaran sedang tidak tersedia untuk sementara. Silakan coba lagi nanti.". `wallet.topup` now returns **503 + message** when disabled (before any Mayar call). `wallet.summary` returns `topup_enabled` + `topup_disabled_message`. Admin `GET/PUT /api/admin/payment-settings` (require_admin).
- **Frontend:** Admin Console → Wallets top card `PaymentSwitchCard` (data-testid `payment-switch-card`, `payment-topup-toggle`, `payment-status-badge`, `payment-message-input`, `payment-message-save`). BillingPage reads `topup_enabled` from wallet summary → disables the wallet Top-up button + plan "Top up RpX" CTAs and shows an amber banner (data-testid `topup-disabled-banner`) with the message; `openTopup()` guards with an info toast.
- **Verified (self-test):** curl — default enabled; disable persists (updated_by admin); customer summary reflects flag+message; customer topup → 503+message; re-enable; RBAC 403 for non-admin. Screenshots — admin toggle card renders (Disabled badge, Off switch, message input), billing banner + disabled button render. NOT yet user-confirmed in production (redeploy required).

## Implemented — Login lockout self-healing + admin recovery (2026-06)
- **Problem:** brute-force lockout (`auth.py`, 5 fails / 15 min, per `ip:email` in `db.login_attempts`) only reset the counter on a SUCCESSFUL login. After the first lockout `count` stayed ≥5, so once the window expired a single wrong password re-locked for another 15 min → felt like a permanent lockout ("Too many attempts. Try again later.").
- **Fix (`auth.py::_check_lockout`):** when the lock window has elapsed, the attempt doc is deleted → user gets a fresh set of 5 attempts (no one-strike re-lock). The 429 now returns a remaining-time message ("Please try again in about N minute(s).") + `Retry-After` header.
- **Admin recovery (`server.py::seed_admin`):** on every startup/redeploy, all `login_attempts` for the admin email are cleared (`delete_many` on `:{ADMIN_EMAIL}$`), and the admin password is (already) reset to `ADMIN_PASSWORD`. So a redeploy always unlocks + repins the admin login — operator can never be permanently locked out.
- **Prod note:** `ADMIN_EMAIL`/`ADMIN_PASSWORD` come from deployment env (defaults `admin@midgate.io` / weak). Production admin is `admin@midgate.co` per user. Redeploy = admin unlocked + password reset to the env value.
- Verified in preview via curl: 6th attempt → 429 with minutes; expiring `locked_until` → next attempt self-heals (401, counter reset to 1, not 429); simulated admin lock cleared after backend restart; admin login still 200. Auth pattern confirmed with integration_expert. NOT yet user-confirmed in production (redeploy required).


## Implemented — Iteration 18: MidGate as Payment Gateway API for first-party app "midnight" (2026-06)
- **Goal:** midnight (operator's own app) lets its members top up via QRIS → MidGate creates the Mayar payment, confirms it, and notifies midnight via signed webhook → midnight credits its own member. First-party only (no third-party aggregation).
- **Backend `backend/app/domains/partner_pay.py`:**
  - Partner-facing `/api/pay` (auth: Partner API Key via `Authorization: Bearer` or `X-Partner-Key`): `POST /charges` (create, idempotent by unique `(partner_id, reference_id)`, min Rp10.000 / max Rp10.000.000) → returns `{charge_id, checkout_url (Mayar hosted QRIS), status, expires_at}`; `GET /charges/{id}` (re-verifies with Mayar). Short customer name/mobile are sanitized/defaulted before hitting Mayar (avoids 502).
  - Correlation via `extraData.charge_id` + Mayar `paymentLinkId`. `_settle` re-verifies with Mayar (reuses `wallet._verify_paid`) and atomically claims paid transition (no double-delivery).
  - **Signed webhook to midnight** `_deliver_charge_paid`: `event: charge.paid`, header `X-MidGate-Signature: t=<unix>,v1=<hmac_sha256(secret, "t."+rawbody)>` (reuses `webhooks.sign`), 3 retries, SSRF-guarded, delivery logged in `partner_webhook_deliveries`.
  - Shared Mayar webhook `/api/wallet/mayar/webhook` now routes unmatched events to `partner_pay.handle_mayar_event` (re-verifies before crediting — spoof-safe).
  - Admin `/api/admin/partners` (require_admin): list (+stats), create (api_key `mgpay_live_…` + secret `mgwhsec_…` shown once), detail (charges + deliveries), PATCH webhook_url/active, rotate-key, rotate-secret, resend paid webhook, delete (cascade).
- **Frontend Admin Console → "Payment Partners"** (`AdminConsole.jsx`): list view with summary stats (partners / total charges / total collected) + New partner dialog (credentials-once reveal + copy). Clicking a partner opens a **full-width detail view** (not a modal) with stats + **Tabs: Charges | Deliveries | Settings**. Charges tab has status filter chips (All/Paid/Pending/Expired) + a **Customer column (name + email)** + reference/customer search (matches reference_id OR customer name/email/mobile, re.escape'd) + **server-side pagination** + resend. Deliveries tab has success/failed filter + pagination. Settings tab has webhook edit, rotate key/secret, activate/deactivate, delete. Backend adds paginated `GET /{id}/charges?status=&q=&page=&limit=` and `GET /{id}/deliveries?status=&page=&limit=` (detail endpoint now returns partner + stats only). Redesigned (2026-06) so it scales when data grows. Testids: partner-detail, partner-back, tab-charges/deliveries/settings, filter-*, charge-search, pager-prev/next, partner-hook-edit/save, partner-rotate-key, partner-toggle-active, partner-delete, partner-resend-*.
- **Design note:** Mayar's dynamic-QRIS endpoint returns only `{url, amount}` (no id/reference) → cannot correlate → NOT used. Invoice-based charge is used (reliable correlation + status + webhook). Mayar hosted checkout has no X-Frame-Options → midnight can embed it inline (iframe) / popup / redirect.
- **Tested:** iteration_18.json — Payment Partners REDESIGN regression PASS: backend 24/24 pytest (`backend/tests/test_iteration_18_partners_redesign.py`) + frontend 100% (list → New partner credentials-once → full-width detail (verified NOT a modal) → back → tabs Charges/Deliveries/Settings → filter chips → reference search → server-side pagination with 18 seeded charges (15+3, page 1 of 2) → rotate key/secret → toggle active → delete → list empty). iteration_17.json — backend 19/19 + frontend 100% for the original partner API. Real payment completion not auto-testable (needs real money); paid→signed-webhook→delivery path pre-verified manually. QA seed data cleaned up (partners=0). NOT yet user-confirmed in production (redeploy required).
- **Operator TODO before midnight can use it:** (1) redeploy midgate.co (feature is preview-only now); (2) Admin → Payment Partners → create "midnight" with midnight's public webhook URL, copy key+secret into midnight env; (3) Mayar dashboard → set Url Webhook = `https://midgate.co/api/wallet/mayar/webhook`.

## Implemented — Iteration 17: REAL Mayar payments + Credit Wallet (2026-06) 
- **Mayar.id payment gateway (PRODUCTION, real)** — replaces the old MOCKED QRIS billing. Client `backend/app/mayar.py` (base `https://api.mayar.id/hl/v1`, `Authorization: Bearer <key>`): `create_invoice`, `get_invoice` (status), `list_transactions`, `register_webhook`. Verified live: invoice create returns `data.link` (hosted checkout, e.g. `https://midgate.myr.id/invoices/...`), `extraData.order_id` echoed for correlation; paid status string is `"paid"`. Secrets in `backend/.env`: `MAYAR_API_KEY`, `MAYAR_WEBHOOK_TOKEN`, `MAYAR_BASE_URL` (never expose).
- **Credit Wallet (approved model)** — `backend/app/domains/wallet.py`, per-workspace, **1 credit = Rp1**, hybrid: top up via Mayar → spend credits on plans. Credits never expire. Immutable `wallet_ledger` (topup/spend/refund/adjustment), atomic `$inc` balance. Endpoints `/api/wallet/*`: `summary`, `ledger`, `topup` (min Rp10.000), `topup/{order_id}` (poll), `purchase-plan` (deduct + activate 30d; guards insufficient=402 & already-on-plan=400), `mayar/webhook` (public), `admin/adjust` (platform-admin manual refund/debit).
- **Security (critical): crediting is only server-side-verified.** `_verify_paid` always re-queries Mayar (`get_invoice` status in {paid,settled,success} + transactions fallback). A webhook (even with the correct token) on an UNPAID invoice does NOT credit. Idempotent single-credit claim via `find_one_and_update`. Preview relies on polling (webhook URL points to production); production must set webhook URL in Mayar dashboard → `https://midgate.co/api/wallet/mayar/webhook`.
- **Mock payments DISABLED** (`ALLOW_MOCK_PAYMENTS=false`): `/api/billing/checkout` and `/api/billing/invoices/{id}/simulate-payment` → 403 (resolves SEC-003).
- **Frontend** `frontend/src/pages/BillingPage.jsx` redesigned: wallet-card (balance in credits ≈ Rp), Top-up dialog (quick chips, opens Mayar checkout in new tab, auto-polls + return-from-Mayar `?topup=` detection), credit-based plan CTAs ("Top up RpX" when short, "Activate — N credits" when funded), Transaction history ledger. Testids: wallet-card, wallet-balance, wallet-topup-btn, topup-dialog, topup-amount-input, topup-quick-*, topup-submit-btn, billing-cta-*, ledger-card.
- Tested: testing_agent iteration_16.json — backend 12/12 pytest PASS + frontend all critical flows PASS (1 overlay bug fixed). Added API guard for re-purchasing current plan (verified curl 400, no double-charge). NOTE: real payment *completion* not auto-tested (needs real money via production Mayar QRIS) — user to validate a live top-up after redeploy.
- **Admin Console → Wallets** (`GET /api/admin/wallets` list + totals, `GET /api/admin/wallets/{id}` detail, `POST /api/admin/wallets/{id}/adjust`): platform-admin section showing per-workspace credit balance + Mayar top-up totals (wallet-holders sorted by balance, workspace search), a View dialog with the full credit ledger + top-up history, and an Adjust dialog to manually Credit/Refund or Deduct credits (logged to the immutable ledger, negative-balance guarded). Nav `admin-nav-wallets`. Testids: admin-wallets-section, wallet-row-*, wallet-view-*, wallet-adjust-*, wallet-adjust-dialog/mode-credit/mode-debit/amount/reason/submit, wallet-detail-dialog. Verified via curl (list/detail/adjust/validation) + screenshots (list, adjust, detail).
- **DEFERRED (per user):** Website A / IVR payment-hub (third-party payment facilitation) — wait until Mayar is live & stable AND user gets written Mayar approval (Mayar is a Merchant-of-Record; aggregating third-party merchant payments likely violates ToS). Bonus-on-topup: not enabled yet.


## Implemented — Iteration 16: Midtrans merchant-readiness (contact + legal notice) (2026-08-03)
- **Business contact (Midtrans requirement)**: added clickable WhatsApp **+62 851-1121-9661** (wa.me/6285111219661) + email on the Contact page (Email/WhatsApp cards) and in the Landing footer.
- **Legal Notice / operator identity**: privacy-safe public identity chosen by user — "MidGate — operated from Siak, Indonesia" (NO personal name, NO street address; full KYC goes privately to Midtrans). Applied to Terms/Privacy/Refund intros, LegalLayout footer (with email + WhatsApp), and Landing footer.
- **Digital service delivery clause** added to Terms §1 (access provisioned automatically & immediately after payment; no physical shipment) — satisfies Midtrans delivery/fulfillment expectation for digital services.
- Assessment vs Midtrans T&C template: MET — Terms, Privacy, Refund, product/service description, Pricing, business contact (email+WhatsApp), copyright, digital delivery, acceptable-use (anti phishing/malware). Remaining is off-site KYC (KTP/NPWP/bank) submitted directly to Midtrans.
- Verified via screenshots (Contact cards, Terms intro shows Siak + delivery clause). Text/content changes; structural components previously tested in iteration_15.


## Implemented — Iteration 15: Payment-gateway readiness + security hardening + branding (2026-08-03)
- **Legal pages** (`LegalLayout.jsx` + `TermsPage/PrivacyPage/RefundPage`): /terms, /privacy, /refund with professional content (sole-proprietor / Indonesia, contact support@midgate.co, 7-day refund). Linked in Landing footer (Terms/Privacy/Refund/Contact/Pricing) + register legal note. `.legal-prose` styling in index.css.
- **Branding**: favicon.svg (indigo shield-M) + tab title "MidGate — Every Click. Protected." + description/OG meta in public/index.html (was "Emergent | Fullstack App").
- **Security hardening** (from security_audit): (1) SEC-001 CORS — server.py now uses an explicit origin allowlist (CORS_ORIGINS in .env), credentials disabled if wildcard; only trusted origins echoed. NOTE: preview ingress still injects `ACAO: *` at the edge (infra, not app) — production must verify edge CORS. (2) SEC-002 webhook SSRF — `url_safety.validate_public_url` resolves DNS and rejects private/loopback/link-local/reserved targets; used at webhook create + re-checked before each delivery. (3) Public contact form rate-limited 5/min/IP → 429. (4) Search inputs `re.escape`'d (links.py, admin.py) to prevent ReDoS. SEC-003 (mock simulate-payment) intentionally left MOCKED until real gateway integration.
- **Pricing**: subtitle made payment-method-agnostic ("Start free and upgrade whenever you're ready — secure payments, cancel anytime."). Prices lowered — Starter 149k→99k, Pro 499k→299k, Business 1.499M→999k (source of truth: billing.py PLANS; frontend fetches /billing/plans).
- Tested: testing_agent iteration_15.json 100% pass (18/18 backend pytest + all frontend: legal pages, footer/register links, favicon/title, CORS, webhook SSRF, contact rate-limit, search regressions, auth regression). Pricing verified via screenshot.


## Implemented — Iteration 14: Blocked-click count + preset semantics fix (2026-08-02)
- **Blocked count in Smart Links list**: `links.py::list_links` now aggregates `analytics_events` per returned link → adds `blocked_count` + `challenged_count`. `LinksPage.jsx` shows "N clicks · M blocked" (red) when blocked_count>0 (testid `link-blocked-{alias}`). So a link that rejects lots of traffic no longer looks empty at 0 clicks.
- **Preset semantics fix** (`security.py::evaluate_request` tail): the automatic risk-based decision (`default_decision`) now only applies for `strict` (and legacy `custom`) presets. For `off`/`moderate`, when no explicit custom rule matches, traffic is ALLOWED — only the explicit block toggles (bots/Tor/etc.) apply. This makes preset behavior match its description ("moderate = block bots & Tor; allow normal traffic"). Previously off/moderate links still auto-blocked proxy/datacenter/high-risk IPs via the risk engine. Link `Gn2XuS` switched to `moderate` per user request.
- Verified: curl (Gn2XuS moderate: Chrome→302, bot→403; HP14cx strict: Chrome→403; /api/links blocked_count=3) + testing_agent iteration_14.json 100% pass (backend+frontend, blocked indicator renders, no regression).


## Implemented — Iteration 13: Recent Clicks transparency (2026-08-02)
- **Problem**: a visitor shown as "Human" (UA-based) was blocked because they were on a proxy and the link used the `strict` preset (blocks proxy/VPN/datacenter). The Recent Clicks table gave no indication the click was blocked or why → user confusion ("human should be accessible").
- **Fix (display + data)**: Link Detail → Recent clicks table (`LinkDetail.jsx`) now has two new columns: **Signals** (amber badges VPN / Proxy / Tor / Datacenter, or "Clean") and **Result** (Allowed=green / Blocked=red / Challenge=amber) with the block reason(s) shown beneath the badge + as tooltip. Clarifies that Type (Human/Bot, from UA) is independent of IP reputation, so a Human on a proxy is correctly Blocked. Backend `redirect.py::_record` now also stores `is_vpn` and `intel_source` on each click event.
- Blocking logic itself unchanged (correct behavior). Tested: testing_agent iteration_13.json frontend 100% pass (columns, Human+Blocked+reason row, flag-vpn/flag-dc badges, result-block badge, no regression). Note: blocked clicks still don't increment link `click_count` (list shows "0 clicks") — candidate future enhancement to show "N blocked".


## Implemented — Iteration 12: proxycheck.io IP Intelligence (2026-08-02)
- **Provider integration** (`backend/app/ip_intel.py`): proxycheck.io v2 API (flags `vpn=1&asn=1&risk=1`) for accurate VPN/Proxy/Tor detection + 0-100 risk + ASN/provider/country. API key entered by platform admin, **Fernet-encrypted at rest** (`IPINTEL_SECRET` in backend/.env) in `db.platform_settings` (_id="proxycheck"), never returned plaintext (masked). Per-IP 24h in-memory cache to protect free-tier quota (1K/day). **Fails open** (disabled/unconfigured/error → available:false, traffic never blocked by outage). Skips private/invalid IPs.
- **Admin endpoints** (`admin.py`, all `require_admin`): GET `/api/admin/ip-intel` (status+masked key+session stats+last test), PUT (save key / toggle enabled), POST `/ip-intel/test` (real verify call), DELETE `/ip-intel/key`.
- **Pipeline enrichment** (`security.py::enrich_signals` awaited in `evaluate_request`): overlays proxycheck `is_proxy`/`is_vpn`/`asn`/`provider`/`intel_risk` onto offline signals; `compute_risk` adds +30 (risk≥66) / +15 (risk≥33). Powers per-link block_proxy_vpn accurately.
- **Admin UI** (`AdminConsole.jsx` → new `Integrations` section, nav `admin-nav-integrations`): proxycheck.io card with status badge (Active/Disabled/Not configured), masked key, key input (password) to set/replace, enable toggle, Test connection, Remove key, and a session usage-stats card.
- Tested: backend curl (CRUD + RBAC 403 + real API: 8.8.8.8→US/Google, Tor→is_proxy/risk=100) + testing_agent iteration_12.json frontend 100% pass (nav/render, Active badge, test-connection success, toggle, RBAC redirect). User's real proxycheck.io key is configured + enabled. No open bugs.


## Implemented — Iteration 11: Admin Console validation + nav polish (2026-08-02)
- **Dedicated Admin Console** (`/admin`, `frontend/pages/AdminConsole.jsx` + `components/AdminRoute.jsx`): platform-admin-only workspace (Overview stats, Users, Workspaces, Revenue, Security events, Global Blocklist, Support tickets, API usage). `AdminRoute` redirects non-admins to `/app`, unauthenticated to `/login`. Backend `/api/admin/*` all gated by `require_admin` (403 for non-admin).
- **Suspension logic**: user `suspended:true` blocks login (auth.py 403); workspace `suspended:true` blocks link redirect (redirect.py). Admin PATCH `/api/admin/users/{id}` and `/api/admin/workspaces/{id}`. Self-modify (400) + last-admin demotion guards in place. Added `invalidate_suspended_workspaces()` (redirect.py) called on workspace PATCH so suspension takes effect immediately (previously up to 30s TTL lag).
- **Nav polish**: added **Contact** link to public navbar (`PublicNav.jsx`, → `/contact`, SPA `<Link>` for route links, `<a>` kept for hash anchors) and a **"Back to home"** link on all auth pages (`AuthShell.jsx`, → `/`). i18n keys `nav.contact`, `nav.backHome` (EN/ID).
- Tested: testing_agent iteration_11.json — backend 23/23 pytest pass, frontend all critical flows pass (Contact link, back-home link, Admin Console RBAC/redirect, user+workspace suspension). No open bugs.

## Product
**MidGate** — SaaS gateway between visitors and destinations. Tagline: *Every Click. Protected.*
Smart Links, Dynamic QR, Traffic Analytics, Visitor Intelligence, Traffic Protection, Bot/Proxy/VPN/Tor detection, Security Rules, Custom Domains, Developer API, Webhooks, Team Workspaces, Billing (QRIS), Admin.

## Implemented — Iteration 9: Webhook Docs + Notification Center (2026-08-02)
- **Webhook Docs** (`frontend/components/WebhookDocs.jsx` on Developers page): event list, request headers, an example JSON payload, and copyable signature-verification snippets for Node.js (Express raw body) and PHP, in tabs. Documents the `X-MidGate-Signature: t=<ts>,v1=<hmac_sha256(secret, "ts.body")>` scheme + 2xx-ack/3× retry policy. Static, no backend.
- **Notification Center** (`backend/app/domains/notifications.py` + `frontend/components/NotificationBell.jsx`): workspace-scoped shared feed with a header bell + unread badge (polls unread-count every 30s), panel with mark-read / mark-all-read / dismiss. Endpoints under `/api/notifications`. Producers: blocked traffic (throttled 1/hr per link via EventBus `link.clicked`), failed webhook delivery (throttled 30m per webhook), member joined (team accept), custom domain verified. Feed capped at 200 per workspace (auto-pruned).
- Tested: backend 6/6 pytest + frontend e2e, 100% pass (iteration_9.json). No open bugs.


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
