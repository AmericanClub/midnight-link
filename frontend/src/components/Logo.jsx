import React from "react";

// Midnight Link brand mark — the amber "witch moon" logo + wordmark.
export default function Logo({ className = "", showWord = true, size = 32 }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`} data-testid="brand-logo">
      <span
        className="relative inline-flex shrink-0 items-center justify-center"
        style={{ width: size, height: size }}
      >
        <span
          aria-hidden="true"
          className="absolute inset-0 rounded-full bg-primary/40 blur-[6px]"
        />
        <img
          src="/logo.png"
          alt="Midnight Link"
          width={size}
          height={size}
          className="relative rounded-full ring-1 ring-primary/30"
          style={{ width: size, height: size }}
        />
      </span>
      {showWord && (
        <span className="font-display text-xl font-extrabold tracking-tight text-foreground">
          Midnight<span className="text-gradient">Link</span>
        </span>
      )}
    </div>
  );
}
