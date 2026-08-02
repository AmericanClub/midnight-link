import React from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import PublicNav from "@/components/PublicNav";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";

const fmt = (n, cur) =>
  n === 0 ? "Free" : n == null ? "Custom" : `${cur === "IDR" ? "Rp" : "$"}${n.toLocaleString()}`;

const featureList = (limits) => [
  `${limits.smart_links ?? "Unlimited"} smart links`,
  `${limits.dynamic_qr ?? "Unlimited"} dynamic QR codes`,
  `${(limits.monthly_events ?? "Unlimited").toLocaleString?.() ?? "Unlimited"} monthly events`,
  `${limits.retention_days ?? "Custom"}-day data retention`,
  `${limits.members ?? "Unlimited"} team member(s)`,
  `${limits.custom_domains ?? "Unlimited"} custom domain(s)`,
];

export default function Pricing() {
  const navigate = useNavigate();
  const { data } = useQuery({
    queryKey: ["plans"],
    queryFn: async () => (await api.get("/billing/plans")).data,
  });
  const plans = data?.plans || [];

  return (
    <div className="min-h-screen bg-background">
      <PublicNav />
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary">Pricing</p>
          <h1 className="font-display text-4xl font-bold tracking-tight">Simple plans that scale</h1>
          <p className="mt-4 text-muted-foreground">
            Start free. Billing (QRIS) is prepared and activates in the billing milestone.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-3 lg:grid-cols-5">
          {plans.map((p) => (
            <Card
              key={p.id}
              className={`flex flex-col p-6 ${p.id === "pro" ? "border-primary ring-1 ring-primary" : ""}`}
              data-testid={`plan-${p.id}`}
            >
              <div className="mb-4">
                <div className="flex items-center gap-2">
                  <h3 className="font-display text-lg font-bold">{p.name}</h3>
                  {p.id === "pro" && <Badge>Popular</Badge>}
                </div>
                <p className="mt-3 font-display text-3xl font-black">
                  {fmt(p.price, p.currency)}
                  {p.price > 0 && <span className="text-sm font-normal text-muted-foreground">/mo</span>}
                </p>
              </div>
              <ul className="mb-6 flex-1 space-y-2.5 text-sm">
                {featureList(p.limits).map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span className="text-muted-foreground">{f}</span>
                  </li>
                ))}
              </ul>
              <Button
                variant={p.id === "pro" ? "default" : "outline"}
                onClick={() => navigate("/register")}
                data-testid={`plan-cta-${p.id}`}
              >
                {p.price === 0 ? "Start for Free" : p.price == null ? "Contact sales" : "Choose plan"}
              </Button>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
