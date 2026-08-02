import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, CreditCard, ShieldCheck, Loader2, Sparkles, Download, Lock } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import QRPreview from "@/components/QRPreview";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import api, { formatApiError, BACKEND } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const fmtPrice = (n, cur) =>
  n === 0 ? "Free" : n == null ? "Custom" : `${cur === "IDR" ? "Rp " : "$"}${n.toLocaleString()}`;

const featureList = (l) => [
  `${l.smart_links ?? "Unlimited"} smart links`,
  `${l.dynamic_qr ?? "Unlimited"} dynamic QR codes`,
  `${(l.monthly_events ?? "Unlimited").toLocaleString?.() ?? "Unlimited"} monthly events`,
  `${l.retention_days ?? "Custom"}-day retention`,
  `${l.members ?? "Unlimited"} member(s)`,
  `${l.custom_domains ?? "Unlimited"} custom domain(s)`,
];

function CheckoutDialog({ open, onOpenChange, invoice, onPaid }) {
  const [paying, setPaying] = useState(false);

  const pay = async () => {
    setPaying(true);
    try {
      await api.post(`/billing/invoices/${invoice.id}/simulate-payment`);
      toast.success("Payment received — subscription activated");
      onPaid();
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setPaying(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="checkout-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Pay with QRIS</DialogTitle>
          <DialogDescription>
            Scan the QRIS code with any supported e-wallet or mobile bank to complete your payment.
          </DialogDescription>
        </DialogHeader>
        {invoice && (
          <div className="flex flex-col items-center gap-4">
            <QRPreview value={invoice.qris_string} style={{ fg_color: "#0A0A0A", bg_color: "#FFFFFF", margin: 8 }} size={200} />
            <div className="text-center">
              <p className="text-sm text-muted-foreground">{invoice.plan_name} plan</p>
              <p className="font-display text-2xl font-bold">{fmtPrice(invoice.amount, invoice.currency)}<span className="text-sm font-normal text-muted-foreground">/mo</span></p>
            </div>
            <div className="w-full rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400" data-testid="checkout-demo-note">
              <strong>Demo mode:</strong> no real QRIS provider is connected yet. Use the button below to simulate a successful payment. Activation happens on the server.
            </div>
            <Button className="w-full gap-2" onClick={pay} disabled={paying} data-testid="simulate-payment-btn">
              {paying ? <><Loader2 className="h-4 w-4 animate-spin" /> Verifying…</> : <>I've paid (simulate)</>}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function BillingPage() {
  const { workspace, refreshSession } = useAuth();
  const qc = useQueryClient();
  const [invoice, setInvoice] = useState(null);
  const [dialog, setDialog] = useState(false);

  const plansQ = useQuery({ queryKey: ["plans"], queryFn: async () => (await api.get("/billing/plans")).data });
  const subQ = useQuery({
    queryKey: ["subscription", workspace?.id],
    queryFn: async () => (await api.get("/billing/subscription")).data,
    enabled: !!workspace,
    retry: false,
  });
  const usageQ = useQuery({
    queryKey: ["usage", workspace?.id],
    queryFn: async () => (await api.get("/billing/usage")).data,
    enabled: !!workspace,
    retry: false,
  });
  const invQ = useQuery({
    queryKey: ["invoices", workspace?.id],
    queryFn: async () => (await api.get("/billing/invoices")).data,
    enabled: !!workspace,
    retry: false,
  });

  const noAccess = subQ.isError && subQ.error?.response?.status === 403;

  const currentPlanId = subQ.data?.plan?.id || workspace?.plan || "free";
  const plans = plansQ.data?.plans || [];

  const checkout = useMutation({
    mutationFn: async (planId) => (await api.post("/billing/checkout", { plan_id: planId })).data,
    onSuccess: (data) => { setInvoice(data); setDialog(true); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  const onPaid = async () => {
    await refreshSession();
    qc.invalidateQueries({ queryKey: ["subscription"] });
    qc.invalidateQueries({ queryKey: ["usage"] });
    qc.invalidateQueries({ queryKey: ["invoices"] });
  };

  const cta = (p) => {
    if (p.id === currentPlanId) return { label: "Current plan", disabled: true, variant: "outline" };
    if (p.id === "free") return { label: "Downgrade", disabled: true, variant: "outline" };
    if (p.price == null) return { label: "Contact sales", disabled: false, variant: "outline", contact: true };
    return { label: currentPlanId === "free" ? "Upgrade" : "Switch plan", disabled: false, variant: "default" };
  };

  return (
    <DashboardLayout>
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold tracking-tight">Billing</h1>
        <p className="mt-1 text-sm text-muted-foreground">Manage your subscription and payments.</p>
      </div>

      {noAccess ? (
        <Card className="flex flex-col items-center gap-3 border-dashed py-16 text-center" data-testid="billing-no-access">
          <Lock className="h-8 w-8 text-muted-foreground/50" />
          <div>
            <h3 className="font-display font-semibold">Billing is restricted</h3>
            <p className="text-sm text-muted-foreground">Only Owners and Billing Managers can view or change the subscription.</p>
          </div>
        </Card>
      ) : (
      <>
      <Card className="mb-8 flex flex-wrap items-center justify-between gap-4 p-6" data-testid="current-plan-card">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <ShieldCheck className="h-6 w-6 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Current plan</p>
            <p className="font-display text-xl font-bold capitalize" data-testid="current-plan-name">
              {subQ.isLoading ? "…" : (subQ.data?.plan?.name || "Free")}
            </p>
          </div>
        </div>
        {subQ.data?.subscription?.current_period_end && (
          <Badge variant="secondary">Renews {new Date(subQ.data.subscription.current_period_end).toLocaleDateString()}</Badge>
        )}
      </Card>

      <Card className="mb-8 p-6" data-testid="usage-card">
        <h2 className="mb-4 font-display font-semibold">Usage this month</h2>
        <div className="grid gap-6 sm:grid-cols-3">
          {[
            { key: "smart_links", label: "Smart links" },
            { key: "dynamic_qr", label: "Dynamic QR" },
            { key: "monthly_events", label: "Monthly events" },
          ].map((u) => {
            const d = usageQ.data?.[u.key] || { used: 0, limit: null, pct: 0 };
            const over = d.limit != null && d.used >= d.limit;
            return (
              <div key={u.key} data-testid={`usage-${u.key}`}>
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{u.label}</span>
                  <span className="font-mono">{d.used}{d.limit != null ? ` / ${d.limit}` : " / ∞"}</span>
                </div>
                <Progress value={d.limit != null ? d.pct : 0} className={over ? "[&>div]:bg-destructive" : ""} />
                {over && <p className="mt-1.5 text-xs text-destructive">Limit reached — upgrade to add more.</p>}
              </div>
            );
          })}
        </div>
      </Card>

      <h2 className="mb-4 font-display font-semibold">Plans</h2>
      {plansQ.isLoading ? (
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-80 w-full rounded-xl" />)}</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {plans.map((p) => {
            const c = cta(p);
            const isCurrent = p.id === currentPlanId;
            return (
              <Card key={p.id} className={`flex flex-col p-6 ${p.id === "pro" ? "border-primary ring-1 ring-primary" : ""} ${isCurrent ? "bg-primary/5" : ""}`} data-testid={`billing-plan-${p.id}`}>
                <div className="mb-4">
                  <div className="flex items-center gap-2">
                    <h3 className="font-display text-lg font-bold">{p.name}</h3>
                    {p.id === "pro" && <Badge className="gap-1"><Sparkles className="h-3 w-3" />Popular</Badge>}
                  </div>
                  <p className="mt-3 font-display text-2xl font-black">
                    {fmtPrice(p.price, p.currency)}
                    {p.price > 0 && <span className="text-sm font-normal text-muted-foreground">/mo</span>}
                  </p>
                </div>
                <ul className="mb-6 flex-1 space-y-2 text-sm">
                  {featureList(p.limits).map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span className="text-muted-foreground">{f}</span>
                    </li>
                  ))}
                </ul>
                <Button
                  variant={c.variant}
                  disabled={c.disabled || checkout.isPending}
                  onClick={() => c.contact ? toast.info("Our team will reach out — contact sales@midgate.io") : checkout.mutate(p.id)}
                  data-testid={`billing-cta-${p.id}`}
                  className="gap-2"
                >
                  {p.price > 0 && !c.disabled && <CreditCard className="h-4 w-4" />}
                  {c.label}
                </Button>
              </Card>
            );
          })}
        </div>
      )}

      <h2 className="mb-4 mt-10 font-display font-semibold">Invoices</h2>
      <Card className="p-6" data-testid="invoices-card">
        {(invQ.data?.items?.length ?? 0) === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No invoices yet.</p>
        ) : (
          <ul className="divide-y divide-border">
            {invQ.data.items.map((inv) => (
              <li key={inv.id} className="flex items-center justify-between py-3" data-testid={`invoice-${inv.id}`}>
                <div>
                  <p className="font-medium">{inv.plan_name} plan</p>
                  <p className="font-mono text-xs text-muted-foreground">{new Date(inv.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm">{fmtPrice(inv.amount, inv.currency)}</span>
                  <Badge variant={inv.status === "paid" ? "default" : "secondary"} className="capitalize">{inv.status}</Badge>
                  {inv.status === "paid" && (
                    <Button variant="ghost" size="sm" className="gap-1" data-testid={`receipt-${inv.id}`}
                      onClick={() => window.open(`${BACKEND}/api/billing/invoices/${inv.id}/receipt.pdf`, "_blank")}>
                      <Download className="h-4 w-4" /> Receipt
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      </>
      )}

      <CheckoutDialog open={dialog} onOpenChange={setDialog} invoice={invoice} onPaid={onPaid} />
    </DashboardLayout>
  );
}
