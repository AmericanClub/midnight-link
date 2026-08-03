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
} from "lucide-react";
import PublicNav from "@/components/PublicNav";
import Logo from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/context/I18nContext";

const HERO_IMG =
  "https://images.unsplash.com/photo-1644088379091-d574269d422f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzNzl8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGdlb21ldHJpYyUyMG5ldHdvcmt8ZW58MHx8fHwxNzg1NjQ3Mjk2fDA&ixlib=rb-4.1.0&q=85";

const features = [
  { icon: Link2, title: "Smart Links", desc: "Branded short links with device, country, and A/B routing.", span: "md:col-span-7" },
  { icon: ShieldCheck, title: "Traffic Protection", desc: "Real-time risk scoring on every click. Allow, challenge, or block.", span: "md:col-span-5" },
  { icon: Bot, title: "Bot Detection", desc: "Classify crawlers, automation, proxy, VPN, Tor and hosting IPs.", span: "md:col-span-5" },
  { icon: BarChart3, title: "Traffic Analytics", desc: "Clicks, unique visitors, geography, devices and referrers in real time.", span: "md:col-span-7" },
  { icon: QrCode, title: "Dynamic QR Codes", desc: "Editable QR destinations that never require a reprint.", span: "md:col-span-6" },
  { icon: Globe, title: "Custom Domains", desc: "Serve links from your own branded domains with managed SSL.", span: "md:col-span-6" },
];

const flow = [
  "Visitor", "Smart Link", "Risk evaluation", "Security rules", "Destination",
];

export default function Landing() {
  const { t } = useI18n();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <PublicNav />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-40" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:gap-8 lg:py-28 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <Badge
              variant="secondary"
              className="mb-6 gap-1.5 rounded-full border border-border px-3 py-1"
              data-testid="hero-badge"
            >
              <Lock className="h-3.5 w-3.5 text-primary" />
              {t("hero.badge")}
            </Badge>
            <h1 className="font-display text-4xl font-black leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
              {t("hero.title")}
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted-foreground">
              {t("hero.subtitle")}
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button
                size="lg"
                className="gap-2 text-base"
                onClick={() => navigate("/register")}
                data-testid="hero-primary-cta"
              >
                {t("hero.cta.primary")}
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="text-base"
                onClick={() => navigate("/login")}
                data-testid="hero-secondary-cta"
              >
                {t("hero.cta.secondary")}
              </Button>
            </div>
            <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
              <span className="flex items-center gap-2"><Gauge className="h-4 w-4 text-primary" /> Real-time analytics</span>
              <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-primary" /> Bot protection</span>
              <span className="flex items-center gap-2"><Users className="h-4 w-4 text-primary" /> Team workspaces</span>
            </div>
          </motion.div>

          <motion.div
            className="relative"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="overflow-hidden rounded-2xl border border-border shadow-2xl">
              <img src={HERO_IMG} alt="Secure network" className="h-full w-full object-cover" />
            </div>
            <div className="absolute -bottom-6 -left-6 hidden rounded-xl border border-border bg-card p-4 shadow-xl sm:block">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Risk score</p>
                  <p className="font-mono text-lg font-bold text-foreground">12 / 100 · Allow</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Flow strip */}
      <section className="border-y border-border bg-muted/40">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-3 px-4 py-6 text-sm sm:px-6 lg:px-8">
          {flow.map((step, i) => (
            <React.Fragment key={step}>
              <span className="font-mono font-medium text-foreground">{step}</span>
              {i < flow.length - 1 && <ArrowRight className="h-4 w-4 text-muted-foreground" />}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* Features bento */}
      <section id="features" className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <div className="mb-14 max-w-2xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary">Platform</p>
          <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
            One gateway between every visitor and destination
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className={`card-lift rounded-xl border border-border bg-card p-7 ${f.span}`}
                data-testid={`feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}
              >
                <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <h3 className="font-display text-lg font-bold">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Developers CTA */}
      <section id="developers" className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="overflow-hidden rounded-2xl border border-border bg-foreground px-8 py-14 text-background sm:px-14">
          <div className="max-w-2xl">
            <h2 className="font-display text-3xl font-bold tracking-tight">Ready to protect every click?</h2>
            <p className="mt-3 text-background/70">
              Start free — no credit card required. Upgrade as your traffic grows.
            </p>
            <Button
              size="lg"
              variant="secondary"
              className="mt-7 gap-2"
              onClick={() => navigate("/register")}
              data-testid="footer-cta-btn"
            >
              {t("hero.cta.primary")}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6 lg:px-8">
          <Logo />
          <div className="flex flex-col items-center gap-2 sm:items-end">
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm">
              <Link to="/pricing" className="text-muted-foreground transition-colors hover:text-foreground" data-testid="footer-pricing-link">Pricing</Link>
              <Link to="/terms" className="text-muted-foreground transition-colors hover:text-foreground" data-testid="footer-terms-link">Terms</Link>
              <Link to="/privacy" className="text-muted-foreground transition-colors hover:text-foreground" data-testid="footer-privacy-link">Privacy</Link>
              <Link to="/refund" className="text-muted-foreground transition-colors hover:text-foreground" data-testid="footer-refund-link">Refund</Link>
              <Link to="/contact" className="text-muted-foreground transition-colors hover:text-foreground" data-testid="footer-contact-link">Contact</Link>
              <a href="mailto:support@midgate.co" className="text-muted-foreground transition-colors hover:text-foreground" data-testid="footer-support-email">support@midgate.co</a>
              <a href="https://wa.me/6285111219661" target="_blank" rel="noreferrer" className="text-muted-foreground transition-colors hover:text-foreground" data-testid="footer-whatsapp">WhatsApp +62 851-1121-9661</a>
            </div>
            <p className="text-sm text-muted-foreground">
              © {new Date().getFullYear()} MidGate. Every Click. Protected.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
