import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Home, RotateCcw } from "lucide-react";

export default function NotFound() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 text-center">
      <div className="absolute inset-0 dot-bg opacity-60" />
      <div className="absolute inset-0 aurora" />
      <div className="relative w-full max-w-lg rounded-[6px] border-[3px] border-[hsl(var(--nb-border))] bg-card p-10 shadow-[8px_8px_0_0_hsl(var(--nb-shadow))]">
        <img
          src="/logo.png"
          alt="Midnight Link"
          className="float-slow mx-auto mb-6 h-20 w-20 rounded-full border-[3px] border-[hsl(var(--nb-border))]"
        />
        <p className="font-pixel text-3xl text-primary sm:text-4xl">404</p>
        <p className="mt-6 font-pixel text-base leading-[1.6] sm:text-lg">GAME OVER</p>
        <p className="mt-4 text-sm text-muted-foreground">
          The witch flew off the map — this page does not exist.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Button asChild data-testid="notfound-home-btn">
            <Link to="/">
              <RotateCcw className="h-4 w-4" /> Respawn at home
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/app">
              <Home className="h-4 w-4" /> Go to dashboard
            </Link>
          </Button>
        </div>
        <p className="mt-7 font-mono text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
          press a button to continue
        </p>
      </div>
    </div>
  );
}
