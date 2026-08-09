import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Check, Clock, Sparkles, ShieldCheck } from "lucide-react";
import PublicNav from "@/components/PublicNav";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const rp = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;
const fmtNum = (n) => Number(n || 0).toLocaleString("en-US");
const fmtReq = (n) => (n >= 1000 ? `${n / 1000}k` : String(n));

const PASS_META = {
  1: { name: "1 Day", tag: "Quick burst" },
  3: { name: "3 Days", tag: "Short run" },
  7: { name: "7 Days", tag: "Weekly" },
  14: { name: "14 Days", tag: "Bi-weekly" },
  30: { name: "30 Days", tag: "Full month", popular: true },
};

const PASS_FEATURES = [
  "Smart link & dynamic QR protection",
  "Bot / proxy / VPN / Tor detection",
  "Traffic analytics & visitor intelligence",
  "Device & Layer-7 header firewall",
  "Unlimited links & QR codes",
  "Auto overflow using wallet credits",
];

function PassPricingCard({ pass, onGet }) {
  const meta = PASS_META[pass.days] || { name: `${pass.days} Days` };
  const defaultIdx = Math.min(2, pass.options.length - 1);
  const [sel, setSel] = useState(pass.options[defaultIdx] || pass.options[0]);

  return (
    <Card
      className={`flex flex-col p-6 ${meta.popular ? "border-primary ring-1 ring-primary" : ""}`}
      data-testid={`pass-plan-${pass.days}`}
    >
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-primary" />
          <h3 className="font-display text-lg font-bold uppercase tracking-wide whitespace-nowrap">{meta.name}</h3>
          {meta.popular && <Badge className="gap-1"><Sparkles className="h-3 w-3" />Popular</Badge>}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{meta.tag} · {rp(pass.rate_per_request)}/request</p>
      </div>

      <div className="mb-3">
        <p className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">Requests</p>
        <div className="flex flex-wrap gap-2">
          {pass.options.map((o) => (
            <button
              key={o.requests} type="button" onClick={() => setSel(o)}
              className={`rounded-[4px] border-2 px-2.5 py-1 font-mono text-xs font-semibold transition-colors ${sel?.requests === o.requests ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/50"}`}
              data-testid={`pass-plan-req-${pass.days}-${o.requests}`}
            >
              {fmtReq(o.requests)}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-5">
        <p className="font-display text-3xl font-black" data-testid={`pass-plan-price-${pass.days}`}>{rp(sel?.price)}</p>
        <p className="mt-1 text-xs text-muted-foreground">{fmtNum(sel?.requests)} requests total</p>
      </div>

      <Button
        variant={meta.popular ? "default" : "outline"} className="mt-auto"
        onClick={onGet} data-testid={`pass-plan-cta-${pass.days}`}
      >
        Get started
      </Button>
    </Card>
  );
}

export default function Pricing() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const goPlan = () => navigate(user ? "/app/billing" : "/register");
  const { data, isLoading } = useQuery({
    queryKey: ["passes"],
    queryFn: async () => (await api.get("/billing/passes")).data,
  });
  const passes = data?.passes || [];

  return (
    <div className="min-h-screen bg-background">
      <PublicNav />
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary">Pricing</p>
          <h1 className="font-display text-4xl font-bold tracking-tight">Pay for what you protect</h1>
          <p className="mt-4 text-muted-foreground">
            Pick a duration pass and the number of requests you need. Every pass unlocks the full protection
            suite — they only differ by how long they last and how many clicks they cover.
          </p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3 lg:grid-cols-5">
            {[...Array(5)].map((_, i) => <Card key={i} className="h-96 animate-pulse" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3 lg:grid-cols-5">
            {passes.map((p) => (
              <PassPricingCard key={p.days} pass={p} onGet={goPlan} />
            ))}
          </div>
        )}

        {/* Everything included */}
        <div className="mx-auto mt-16 max-w-3xl">
          <div className="mb-6 flex items-center justify-center gap-2 text-center">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <h2 className="font-display text-lg font-bold uppercase tracking-wide">Every pass includes</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2" data-testid="pass-features">
            {PASS_FEATURES.map((f) => (
              <div key={f} className="flex items-start gap-2 rounded-[4px] border-2 border-[hsl(var(--nb-border))] bg-muted/30 p-3 text-sm">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <span className="text-muted-foreground">{f}</span>
              </div>
            ))}
          </div>
          <p className="mt-6 text-center text-xs text-muted-foreground">
            1 request = 1 click / visit. When your pass runs out, requests keep flowing from your wallet credits.
            If both run out, links still redirect so your campaigns never go dark — protection simply pauses until you top up.
          </p>
        </div>
      </section>
    </div>
  );
}
