import React from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ShieldCheck,
  Link2,
  QrCode,
  BarChart3,
  Bot,
  Globe,
  ArrowRight,
  Lock,
  Gauge,
  Users,
  Zap,
  Sparkles,
  Terminal,
  MousePointerClick,
} from "lucide-react";
import PublicNav from "@/components/PublicNav";
import Logo from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/context/I18nContext";

const CTA_MOON =
  "https://images.unsplash.com/photo-1509185402190-f3e3de0edf71?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxNzV8MHwxfHNlYXJjaHwzfHxtaWRuaWdodCUyMG1vb258ZW58MHx8fGJsYWNrfDE3ODYxNTM4MDZ8MA&ixlib=rb-4.1.0&q=85";

const features = [
  { icon: Link2, title: "Smart Links", desc: "Branded short links with device, country, and A/B routing.", span: "md:col-span-7", tags: ["Routing", "A/B"] },
  { icon: ShieldCheck, title: "Traffic Protection", desc: "Real-time risk scoring on every click. Allow, challenge, or block.", span: "md:col-span-5", tags: ["Risk", "Rules"] },
  { icon: Bot, title: "Bot Detection", desc: "Classify crawlers, automation, proxy, VPN, Tor and hosting IPs.", span: "md:col-span-5", tags: ["Bots", "Tor"] },
  { icon: BarChart3, title: "Traffic Analytics", desc: "Clicks, unique visitors, geography, devices and referrers in real time.", span: "md:col-span-7", tags: ["Realtime", "Geo"] },
  { icon: QrCode, title: "Dynamic QR Codes", desc: "Editable QR destinations that never require a reprint.", span: "md:col-span-6", tags: ["Editable"] },
  { icon: Globe, title: "Custom Domains", desc: "Serve links from your own branded domains with managed SSL.", span: "md:col-span-6", tags: ["SSL", "Branded"] },
];

const stats = [
  { label: "Bot & proxy blocking", value: 98, display: "98", bar: "bg-primary" },
  { label: "Uptime SLA", value: 99, display: "99.9", bar: "bg-[hsl(var(--success))]" },
  { label: "Avg. redirect speed", value: 94, display: "94", bar: "bg-chart-2" },
  { label: "Threat DB coverage", value: 96, display: "96", bar: "bg-destructive" },
];

const flow = ["Visitor", "Smart Link", "Risk eval", "Security rules", "Destination"];

function StatBar({ label, value, display, bar }) {
  return (
    <div className="rounded-[5px] border-[3px] border-[hsl(var(--nb-border))] bg-card p-4 shadow-[5px_5px_0_0_hsl(var(--nb-shadow))]">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-display text-sm font-bold uppercase tracking-wide">{label}</span>
        <span className="font-pixel text-[11px] text-primary">{display}</span>
      </div>
      <div className="h-4 w-full rounded-[2px] border-2 border-[hsl(var(--nb-border))] bg-muted p-[2px]">
        <div className={`h-full rounded-[1px] ${bar}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export default function Landing() {
  const { t } = useI18n();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <PublicNav />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 dot-bg opacity-70" />
        <div className="absolute inset-0 aurora" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:gap-10 lg:py-24 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <div
              className="mb-6 inline-flex items-center gap-2 rounded-[3px] border-[2.5px] border-[hsl(var(--nb-border))] bg-card px-3 py-1.5 shadow-[3px_3px_0_0_hsl(var(--nb-shadow))]"
              data-testid="hero-badge"
            >
              <Lock className="h-3.5 w-3.5 text-primary" />
              <span className="font-display text-xs font-bold uppercase tracking-wide">{t("hero.badge")}</span>
            </div>

            <h1 className="font-pixel text-2xl leading-[1.5] sm:text-3xl lg:text-[2.6rem] lg:leading-[1.45]">
              Every Click.<br />
              <span className="text-primary">Protected.</span>
            </h1>

            <p className="mt-6 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
              {t("hero.subtitle")}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button size="lg" className="gap-2" onClick={() => navigate("/register")} data-testid="hero-primary-cta">
                <Zap className="h-4 w-4" />
                {t("hero.cta.primary")}
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button size="lg" variant="outline" onClick={() => navigate("/login")} data-testid="hero-secondary-cta">
                {t("hero.cta.secondary")}
              </Button>
            </div>

            <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-2 font-display font-semibold uppercase tracking-wide"><Gauge className="h-4 w-4 text-primary" /> Real-time analytics</span>
              <span className="flex items-center gap-2 font-display font-semibold uppercase tracking-wide"><ShieldCheck className="h-4 w-4 text-primary" /> Bot protection</span>
              <span className="flex items-center gap-2 font-display font-semibold uppercase tracking-wide"><Users className="h-4 w-4 text-primary" /> Team workspaces</span>
            </div>
          </motion.div>

          {/* Arcade console card */}
          <motion.div
            className="relative"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="rounded-[6px] border-[3px] border-[hsl(var(--nb-border))] bg-card shadow-[8px_8px_0_0_hsl(var(--nb-shadow))]">
              {/* title bar */}
              <div className="flex items-center gap-2 border-b-[3px] border-[hsl(var(--nb-border))] bg-secondary px-4 py-2.5">
                <span className="h-3 w-3 rounded-full border-2 border-[hsl(var(--nb-border))] bg-destructive" />
                <span className="h-3 w-3 rounded-full border-2 border-[hsl(var(--nb-border))] bg-primary" />
                <span className="h-3 w-3 rounded-full border-2 border-[hsl(var(--nb-border))] bg-[hsl(var(--success))]" />
                <span className="ml-2 flex items-center gap-1.5 font-mono text-xs font-semibold text-muted-foreground">
                  <Terminal className="h-3.5 w-3.5" /> risk-engine
                </span>
              </div>
              <div className="p-5">
                <div className="flex items-center gap-4">
                  <img src="/logo.png" alt="Midnight Link" className="float-slow h-16 w-16 rounded-full border-[3px] border-[hsl(var(--nb-border))]" />
                  <div>
                    <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Live decision</p>
                    <p className="font-pixel text-lg text-[hsl(var(--success))]">ALLOW</p>
                    <p className="font-mono text-xs text-muted-foreground">score 12 / 100 · human · Chrome</p>
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  {[
                    { l: "Human", c: "bg-[hsl(var(--success))]", w: "88%" },
                    { l: "Bot / automation", c: "bg-primary", w: "40%" },
                    { l: "Proxy / VPN / Tor", c: "bg-destructive", w: "22%" },
                  ].map((r) => (
                    <div key={r.l}>
                      <div className="mb-1 flex justify-between font-mono text-[11px] text-muted-foreground">
                        <span>{r.l}</span>
                      </div>
                      <div className="h-3 w-full rounded-[2px] border-2 border-[hsl(var(--nb-border))] bg-muted p-[1.5px]">
                        <div className={`h-full rounded-[1px] ${r.c}`} style={{ width: r.w }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* floating chips */}
            <div className="absolute -right-3 -top-4 hidden rotate-3 items-center gap-2 rounded-[4px] border-[3px] border-[hsl(var(--nb-border))] bg-primary px-3 py-1.5 text-primary-foreground shadow-[4px_4px_0_0_hsl(var(--nb-shadow))] sm:flex">
              <MousePointerClick className="h-4 w-4" />
              <span className="font-pixel text-[10px]">+1,284</span>
            </div>
            <div className="absolute -bottom-4 -left-3 hidden -rotate-2 items-center gap-2 rounded-[4px] border-[3px] border-[hsl(var(--nb-border))] bg-card px-3 py-1.5 shadow-[4px_4px_0_0_hsl(var(--nb-shadow))] sm:flex">
              <Bot className="h-4 w-4 text-destructive" />
              <span className="font-display text-xs font-bold uppercase">312 bots blocked</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Flow strip */}
      <section className="border-y-[3px] border-[hsl(var(--nb-border))] bg-secondary">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-3 px-4 py-5 sm:px-6 lg:px-8">
          {flow.map((step, i) => (
            <React.Fragment key={step}>
              <span className="rounded-[3px] border-2 border-[hsl(var(--nb-border))] bg-card px-3 py-1 font-mono text-xs font-semibold sm:text-sm">{step}</span>
              {i < flow.length - 1 && <ArrowRight className="h-4 w-4 text-primary" />}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* Protection stats (arcade "player stats" homage) */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="mb-10 text-center">
          <p className="mb-3 font-pixel text-[11px] text-primary">PROTECTION STATS</p>
          <h2 className="font-display text-3xl font-bold uppercase tracking-tight sm:text-4xl">Levelled up against abuse</h2>
          <p className="mx-auto mt-3 max-w-xl text-muted-foreground">Every link on Midnight Link ships with these defenses turned on by default.</p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {stats.map((s) => (
            <StatBar key={s.label} {...s} />
          ))}
        </div>
      </section>

      {/* Features bento */}
      <section id="features" className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="mb-12 max-w-2xl">
          <p className="mb-3 font-pixel text-[11px] text-primary">PLATFORM</p>
          <h2 className="font-display text-3xl font-bold uppercase tracking-tight sm:text-4xl">
            One gateway between every visitor and destination
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-12">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className={`card-lift rounded-[5px] border-[3px] border-[hsl(var(--nb-border))] bg-card p-6 shadow-[5px_5px_0_0_hsl(var(--nb-shadow))] ${f.span}`}
                data-testid={`feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-[4px] border-[2.5px] border-[hsl(var(--nb-border))] bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--nb-shadow))]">
                  <Icon className="h-6 w-6" />
                </div>
                <h3 className="font-display text-lg font-bold uppercase tracking-wide">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {f.tags.map((tag) => (
                    <span key={tag} className="rounded-[3px] border-2 border-[hsl(var(--nb-border))] bg-secondary px-2 py-0.5 font-mono text-[11px] font-semibold">{tag}</span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Developers / CTA */}
      <section id="developers" className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-[6px] border-[3px] border-[hsl(var(--nb-border))] night-panel px-8 py-16 shadow-[8px_8px_0_0_hsl(var(--nb-shadow))] sm:px-14">
          <img src={CTA_MOON} alt="" className="pointer-events-none absolute -right-10 -top-10 h-56 w-56 rounded-full object-cover opacity-30" />
          <div className="relative max-w-2xl">
            <p className="mb-3 font-pixel text-[11px] text-primary">START A QUEST</p>
            <h2 className="font-pixel text-xl leading-[1.5] text-white sm:text-2xl">Ready to protect<br />every click?</h2>
            <p className="mt-5 max-w-md text-white/70">
              Start free — no credit card required. Upgrade as your traffic grows.
            </p>
            <Button
              size="lg"
              className="mt-7 gap-2"
              onClick={() => navigate("/register")}
              data-testid="footer-cta-btn"
            >
              <Sparkles className="h-4 w-4" />
              {t("hero.cta.primary")}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t-[3px] border-[hsl(var(--nb-border))]">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6 lg:px-8">
          <Logo />
          <div className="flex flex-col items-center gap-2 sm:items-end">
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm font-medium">
              <Link to="/pricing" className="text-muted-foreground transition-colors hover:text-primary" data-testid="footer-pricing-link">Pricing</Link>
              <Link to="/terms" className="text-muted-foreground transition-colors hover:text-primary" data-testid="footer-terms-link">Terms</Link>
              <Link to="/privacy" className="text-muted-foreground transition-colors hover:text-primary" data-testid="footer-privacy-link">Privacy</Link>
              <Link to="/refund" className="text-muted-foreground transition-colors hover:text-primary" data-testid="footer-refund-link">Refund</Link>
              <Link to="/contact" className="text-muted-foreground transition-colors hover:text-primary" data-testid="footer-contact-link">Contact</Link>
              <a href="mailto:support@midnightlink.link" className="text-muted-foreground transition-colors hover:text-primary" data-testid="footer-support-email">support@midnightlink.link</a>
              <a href="https://wa.me/6281278899056" target="_blank" rel="noreferrer" className="text-muted-foreground transition-colors hover:text-primary" data-testid="footer-whatsapp">WhatsApp +62 812-7889-9056</a>
            </div>
            <p className="text-sm text-muted-foreground" data-testid="footer-legal-notice">
              Midnight Link — operated from Siak, Indonesia
            </p>
            <p className="text-sm text-muted-foreground">
              © {new Date().getFullYear()} Midnight Link. Every Click. Protected.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
