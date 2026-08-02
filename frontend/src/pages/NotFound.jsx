import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import Logo from "@/components/Logo";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-4 text-center">
      <Logo size={40} />
      <div>
        <p className="font-display text-6xl font-black text-primary">404</p>
        <p className="mt-2 text-muted-foreground">This page could not be found.</p>
      </div>
      <Button asChild data-testid="notfound-home-btn">
        <Link to="/">Back to home</Link>
      </Button>
    </div>
  );
}
