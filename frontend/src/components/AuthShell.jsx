import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, BarChart3, Bot, ArrowLeft } from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import SoundToggle from "@/components/SoundToggle";
import { useI18n } from "@/context/I18nContext";

export default function AuthShell({ title, subtitle, children }) {
  const { t } = useI18n();
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left brand panel */}
      <div className="night-panel relative hidden flex-col justify-between overflow-hidden border-r-[3px] border-[hsl(var(--nb-border))] p-12 text-white lg:flex">
        <div className="absolute inset-0 dot-bg opacity-30" />
        <div className="relative">
          <Link to="/">
            <Logo onDark size={34} />
          </Link>
        </div>
        <div className="relative max-w-md">
          <p className="mb-4 font-pixel text-[11px] text-primary">MIDNIGHT LINK</p>
          <h2 className="font-pixel text-xl leading-[1.5]">
            Every click,<br />protected by an<br /><span className="text-primary">intelligent gateway.</span>
          </h2>
          <ul className="mt-9 space-y-3">
            {[
              { icon: ShieldCheck, label: "Real-time traffic protection" },
              { icon: Bot, label: "Bot, proxy & VPN detection" },
              { icon: BarChart3, label: "Instant visitor analytics" },
            ].map((f) => {
              const Icon = f.icon;
              return (
                <li key={f.label} className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-[4px] border-[2.5px] border-white/70 bg-primary text-primary-foreground">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="font-display text-sm font-semibold uppercase tracking-wide text-white/90">{f.label}</span>
                </li>
              );
            })}
          </ul>
        </div>
        <p className="relative font-mono text-xs text-white/45">© {new Date().getFullYear()} Midnight Link</p>
      </div>

      {/* Right form panel */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between p-6">
          <Link to="/" className="lg:hidden">
            <Logo />
          </Link>
          <Link
            to="/"
            data-testid="auth-back-home-link"
            className="hidden items-center gap-1.5 font-display text-sm font-semibold uppercase tracking-wide text-muted-foreground transition-colors hover:text-primary lg:flex"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("nav.backHome")}
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <LanguageToggle />
            <ThemeToggle />
            <SoundToggle />
          </div>
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-sm">
            <h1 className="font-display text-2xl font-bold uppercase tracking-tight">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>}
            <div className="mt-8">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
