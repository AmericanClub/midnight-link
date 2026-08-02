import React from "react";

export default function Logo({ className = "", showWord = true, size = 28 }) {
  return (
    <div className={`flex items-center gap-2 ${className}`} data-testid="brand-logo">
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path
          d="M16 2L28 7v9c0 7.2-5 11.6-12 14C9 27.6 4 23.2 4 16V7l12-5z"
          fill="hsl(var(--primary))"
        />
        <path
          d="M10.5 21V12.2l5.5 5.2 5.5-5.2V21"
          stroke="white"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
      {showWord && (
        <span className="font-display text-xl font-extrabold tracking-tight text-foreground">
          MidGate
        </span>
      )}
    </div>
  );
}
