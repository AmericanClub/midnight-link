import React from "react";
import { ShieldCheck, Bot, Wifi, Globe } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const signals = [
  { icon: Bot, title: "Bot Detection", desc: "Classify crawlers, automation and headless browsers." },
  { icon: Wifi, title: "Proxy / VPN / Tor", desc: "Detect anonymized and datacenter traffic." },
  { icon: Globe, title: "Geo & ASN Rules", desc: "Restrict by country, region or network." },
  { icon: ShieldCheck, title: "Risk Scoring", desc: "0–100 score drives Allow, Challenge or Block." },
];

export default function ProtectionPage() {
  return (
    <DashboardLayout>
      <div className="mb-8">
        <div className="flex items-center gap-2">
          <h1 className="font-display text-2xl font-bold tracking-tight">Traffic Protection</h1>
          <Badge variant="secondary" data-testid="protection-coming-soon">Coming soon</Badge>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          MidGate Protect evaluates every click. Configurable rules and challenges arrive in a later milestone.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {signals.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.title} className="card-lift p-6" data-testid={`protection-${s.title.toLowerCase().replace(/\W+/g, "-")}`}>
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10">
                <Icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-display font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{s.desc}</p>
            </Card>
          );
        })}
      </div>

      <Card className="mt-6 p-6">
        <h2 className="mb-4 font-display font-semibold">Default risk thresholds</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { range: "0–29", action: "Allow", color: "bg-emerald-500" },
            { range: "30–59", action: "Challenge", color: "bg-amber-500" },
            { range: "60–79", action: "Review", color: "bg-orange-500" },
            { range: "80–100", action: "Block", color: "bg-red-500" },
          ].map((r) => (
            <div key={r.range} className="rounded-lg border border-border p-4">
              <div className={`mb-2 h-1.5 w-8 rounded-full ${r.color}`} />
              <p className="font-mono text-sm font-semibold">{r.range}</p>
              <p className="text-xs text-muted-foreground">{r.action}</p>
            </div>
          ))}
        </div>
      </Card>
    </DashboardLayout>
  );
}
