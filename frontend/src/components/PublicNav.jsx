import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu, X } from "lucide-react";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/context/I18nContext";
import { useAuth } from "@/context/AuthContext";

export default function PublicNav() {
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const links = [
    { label: t("nav.features"), to: "/#features", testid: "nav-features-link" },
    { label: t("nav.pricing"), to: "/pricing", testid: "nav-pricing-link" },
    { label: t("nav.developers"), to: "/#developers", testid: "nav-developers-link" },
    { label: t("nav.contact"), to: "/contact", testid: "nav-contact-link" },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" data-testid="public-logo-link">
          <Logo />
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {links.map((l) =>
            l.to.startsWith("/#") ? (
              <a
                key={l.label}
                href={l.to}
                data-testid={l.testid}
                className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {l.label}
              </a>
            ) : (
              <Link
                key={l.label}
                to={l.to}
                data-testid={l.testid}
                className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {l.label}
              </Link>
            )
          )}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <LanguageToggle />
          <ThemeToggle />
          {user ? (
            <Button onClick={() => navigate("/app")} data-testid="nav-dashboard-btn">
              Dashboard
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => navigate("/login")} data-testid="nav-login-btn">
                {t("nav.login")}
              </Button>
              <Button onClick={() => navigate("/register")} data-testid="nav-start-btn">
                {t("nav.start")}
              </Button>
            </>
          )}
        </div>

        <div className="flex items-center gap-1 md:hidden">
          <ThemeToggle />
          <Button variant="ghost" size="icon" onClick={() => setOpen(!open)} data-testid="mobile-nav-btn">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {open && (
        <div className="border-t border-border bg-background px-4 py-4 md:hidden">
          <div className="flex flex-col gap-3">
            {links.map((l) =>
              l.to.startsWith("/#") ? (
                <a key={l.label} href={l.to} data-testid={`mobile-${l.testid}`} className="text-sm font-medium text-muted-foreground">
                  {l.label}
                </a>
              ) : (
                <Link key={l.label} to={l.to} data-testid={`mobile-${l.testid}`} onClick={() => setOpen(false)} className="text-sm font-medium text-muted-foreground">
                  {l.label}
                </Link>
              )
            )}
            <div className="flex gap-2 pt-2">
              <Button variant="outline" className="flex-1" onClick={() => navigate("/login")}>
                {t("nav.login")}
              </Button>
              <Button className="flex-1" onClick={() => navigate("/register")}>
                {t("nav.start")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
