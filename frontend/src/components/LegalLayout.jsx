import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import Logo from "@/components/Logo";
import { Button } from "@/components/ui/button";

const LEGAL_LINKS = [
  { to: "/terms", label: "Terms of Service" },
  { to: "/privacy", label: "Privacy Policy" },
  { to: "/refund", label: "Refund & Cancellation" },
  { to: "/contact", label: "Contact" },
];

export default function LegalLayout({ title, updated, children, testid }) {
  return (
    <div className="min-h-screen bg-background" data-testid={testid}>
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" data-testid="legal-logo-link"><Logo /></Link>
          <Button asChild variant="ghost" size="sm" className="gap-2">
            <Link to="/" data-testid="legal-back-home"><ArrowLeft className="h-4 w-4" />Home</Link>
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:py-16">
        <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">Last updated: {updated}</p>
        <article className="legal-prose mt-8">{children}</article>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-3 px-4 py-8 text-sm sm:px-6">
          <div className="flex flex-wrap items-center justify-center gap-4">
            {LEGAL_LINKS.map((l) => (
              <Link key={l.to} to={l.to} className="text-muted-foreground transition-colors hover:text-foreground" data-testid={`legal-footer-${l.to.slice(1)}`}>
                {l.label}
              </Link>
            ))}
          </div>
          <p className="text-center text-muted-foreground" data-testid="legal-notice">
            MidGate is a digital service operated from Siak, Indonesia ·{" "}
            <a href="mailto:support@midgate.co" className="hover:text-foreground">support@midgate.co</a> ·{" "}
            <a href="https://wa.me/6285111219661" target="_blank" rel="noreferrer" className="hover:text-foreground">WhatsApp +62 851-1121-9661</a>
          </p>
          <p className="text-muted-foreground">© {new Date().getFullYear()} MidGate. Every Click. Protected.</p>
        </div>
      </footer>
    </div>
  );
}
