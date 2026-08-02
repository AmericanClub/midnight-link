import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, BarChart3, Bot } from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left brand panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-foreground p-12 text-background lg:flex">
        <div className="absolute inset-0 grid-bg opacity-10" />
        <div className="relative">
          <Link to="/" className="[&_span]:text-background">
            <Logo />
          </Link>
        </div>
        <div className="relative max-w-md">
          <h2 className="font-display text-3xl font-bold leading-tight tracking-tight">
            Every click, protected by an intelligent gateway.
          </h2>
          <ul className="mt-8 space-y-4 text-background/80">
            <li className="flex items-center gap-3"><ShieldCheck className="h-5 w-5" /> Real-time traffic protection</li>
            <li className="flex items-center gap-3"><Bot className="h-5 w-5" /> Bot, proxy & VPN detection</li>
            <li className="flex items-center gap-3"><BarChart3 className="h-5 w-5" /> Instant visitor analytics</li>
          </ul>
        </div>
        <p className="relative text-sm text-background/50">© {new Date().getFullYear()} MidGate</p>
      </div>

      {/* Right form panel */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between p-6">
          <Link to="/" className="lg:hidden">
            <Logo />
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-sm">
            <h1 className="font-display text-2xl font-bold tracking-tight">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>}
            <div className="mt-8">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
