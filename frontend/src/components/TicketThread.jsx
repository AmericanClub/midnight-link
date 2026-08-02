import React from "react";

function ago(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function TicketMessages({ messages = [], mySide = "user" }) {
  return (
    <div className="space-y-3" data-testid="ticket-messages">
      {messages.map((m) => {
        const mine = m.author === mySide;
        return (
          <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={`ticket-msg-${m.id}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${mine ? "rounded-br-sm bg-primary text-primary-foreground" : "rounded-bl-sm bg-muted"}`}>
              <p className="mb-0.5 text-[11px] font-medium opacity-70">
                {m.author === "admin" ? (m.author_name || "Support") : m.author_name} · {ago(m.created_at)}
              </p>
              <p className="whitespace-pre-wrap">{m.body}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export const STATUS_VARIANT = {
  open: "default",
  pending: "secondary",
  resolved: "outline",
  closed: "secondary",
};
export const CATEGORIES = [
  { v: "bug", label: "Bug" },
  { v: "abuse", label: "Abuse" },
  { v: "billing", label: "Billing" },
  { v: "other", label: "Other" },
];
export const PRIORITIES = [
  { v: "low", label: "Low" },
  { v: "medium", label: "Medium" },
  { v: "high", label: "High" },
];
