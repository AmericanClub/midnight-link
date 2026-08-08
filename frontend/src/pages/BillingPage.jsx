import React, { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check, Wallet, ShieldCheck, Loader2, Sparkles, Plus, ArrowUpRight,
  ArrowDownLeft, Lock, ExternalLink, Info,
} from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const rp = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;
const fmtPrice = (n, cur) =>
  n === 0 ? "Free" : n == null ? "Custom" : `${cur === "IDR" ? "Rp" : "$"}${Number(n).toLocaleString("id-ID")}`;

const featureList = (l) => [
  `${l.smart_links ?? "Unlimited"} smart links`,
  `${l.dynamic_qr ?? "Unlimited"} dynamic QR codes`,
  `${(l.monthly_events ?? "Unlimited").toLocaleString?.() ?? "Unlimited"} monthly events`,
  `${l.retention_days ?? "Custom"}-day retention`,
  `${l.members ?? "Unlimited"} member(s)`,
  `${l.custom_domains ?? "Unlimited"} custom domain(s)`,
];

const QUICK = [25000, 50000, 100000, 250000, 500000];
const LEDGER_LABEL = { topup: "Top-up", spend: "Plan purchase", refund: "Refund", adjustment: "Adjustment", bonus: "Bonus" };

function TopupDialog({ open, onOpenChange, presetAmount, onCredited }) {
  const [amount, setAmount] = useState(50000);
  const [pending, setPending] = useState(null); // { order_id, payment_url }
  const [checking, setChecking] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    if (open) {
      setAmount(presetAmount && presetAmount >= 10000 ? presetAmount : 50000);
      setPending(null);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open, presetAmount]);

  const stopPolling = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };

  const checkStatus = useCallback(async (orderId, quiet = true) => {
    try {
      const { data } = await api.get(`/wallet/topup/${orderId}`);
      if (data.credited) {
        stopPolling();
        toast.success("Payment received — credits added to your wallet");
        onCredited();
        onOpenChange(false);
        return true;
      }
      if (!quiet) toast.info("Payment not detected yet. It can take a moment after you pay.");
    } catch (e) { /* keep polling */ }
    return false;
  }, [onCredited, onOpenChange]);

  const start = useMutation({
    mutationFn: async () => (await api.post("/wallet/topup", {
      amount: Number(amount),
      return_url: `${window.location.origin}/app/billing`,
    })).data,
    onSuccess: (data) => {
      setPending(data);
      window.open(data.payment_url, "_blank", "noopener");
      let ticks = 0;
      stopPolling();
      pollRef.current = setInterval(async () => {
        ticks += 1;
        const done = await checkStatus(data.order_id, true);
        if (done || ticks > 90) stopPolling();
      }, 4000);
    },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  const credits = Number(amount) || 0;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) stopPolling(); onOpenChange(o); }}>
      <DialogContent className="max-w-md" data-testid="topup-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Top up your wallet</DialogTitle>
          <DialogDescription>
            Pay securely with QRIS, e-wallet, or bank transfer via Mayar. 1 credit = Rp1.
          </DialogDescription>
        </DialogHeader>

        {!pending ? (
          <div className="space-y-5">
            <div>
              <Label htmlFor="topup-amount">Amount (Rp)</Label>
              <Input
                id="topup-amount" type="number" min={10000} step={1000} value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="mt-1.5 font-mono" data-testid="topup-amount-input"
              />
              <div className="mt-2 flex flex-wrap gap-2">
                {QUICK.map((q) => (
                  <button
                    key={q} type="button" onClick={() => setAmount(q)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${Number(amount) === q ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/50"}`}
                    data-testid={`topup-quick-${q}`}
                  >
                    {rp(q)}
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-lg bg-muted/50 p-3 text-sm">
              You'll receive <span className="font-mono font-semibold">{credits.toLocaleString("id-ID")} credits</span>{" "}
              <span className="text-muted-foreground">(≈ {rp(credits)})</span>
            </div>
            <Button
              className="w-full gap-2" disabled={start.isPending || credits < 10000}
              onClick={() => start.mutate()} data-testid="topup-submit-btn"
            >
              {start.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Starting…</> : <><ExternalLink className="h-4 w-4" /> Continue to payment</>}
            </Button>
            <p className="text-center text-xs text-muted-foreground">Minimum top-up {rp(10000)}.</p>
          </div>
        ) : (
          <div className="space-y-4 text-center" data-testid="topup-waiting">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
              <Loader2 className="h-7 w-7 animate-spin text-primary" />
            </div>
            <div>
              <p className="font-medium">Waiting for your payment…</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Complete the payment in the new tab. We'll credit your wallet automatically once it's confirmed.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Button variant="outline" className="gap-2" onClick={() => window.open(pending.payment_url, "_blank", "noopener")}>
                <ExternalLink className="h-4 w-4" /> Open payment page
              </Button>
              <Button
                className="gap-2" disabled={checking}
                onClick={async () => { setChecking(true); await checkStatus(pending.order_id, false); setChecking(false); }}
                data-testid="topup-check-btn"
              >
                {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} I've completed the payment
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function BillingPage() {
  const { workspace, refreshSession } = useAuth();
  const qc = useQueryClient();
  const [topupOpen, setTopupOpen] = useState(false);
  const [presetAmount, setPresetAmount] = useState(0);

  const plansQ = useQuery({ queryKey: ["plans"], queryFn: async () => (await api.get("/billing/plans")).data });
  const subQ = useQuery({
    queryKey: ["subscription", workspace?.id],
    queryFn: async () => (await api.get("/billing/subscription")).data,
    enabled: !!workspace, retry: false,
  });
  const usageQ = useQuery({
    queryKey: ["usage", workspace?.id],
    queryFn: async () => (await api.get("/billing/usage")).data,
    enabled: !!workspace, retry: false,
  });
  const walletQ = useQuery({
    queryKey: ["wallet", workspace?.id],
    queryFn: async () => (await api.get("/wallet/summary")).data,
    enabled: !!workspace, retry: false,
  });

  const noAccess = subQ.isError && subQ.error?.response?.status === 403;
  const currentPlanId = subQ.data?.plan?.id || workspace?.plan || "free";
  const plans = plansQ.data?.plans || [];
  const balance = walletQ.data?.balance ?? 0;
  const topupEnabled = walletQ.data?.topup_enabled ?? true;
  const topupMsg = walletQ.data?.topup_disabled_message
    || "Pembayaran sedang tidak tersedia untuk sementara. Silakan coba lagi nanti.";

  const refreshAll = useCallback(async () => {
    await refreshSession();
    qc.invalidateQueries({ queryKey: ["wallet"] });
    qc.invalidateQueries({ queryKey: ["subscription"] });
    qc.invalidateQueries({ queryKey: ["usage"] });
  }, [qc, refreshSession]);

  // Auto-detect return from Mayar (?topup=<order_id>)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const order = params.get("topup");
    if (!order) return;
    let ticks = 0;
    const iv = setInterval(async () => {
      ticks += 1;
      try {
        const { data } = await api.get(`/wallet/topup/${order}`);
        if (data.credited) {
          clearInterval(iv);
          toast.success("Payment received — credits added to your wallet");
          refreshAll();
        }
      } catch (e) { /* ignore */ }
      if (ticks > 12) clearInterval(iv);
    }, 3000);
    window.history.replaceState({}, "", "/app/billing");
    return () => clearInterval(iv);
  }, [refreshAll]);

  const purchase = useMutation({
    mutationFn: async (planId) => (await api.post("/wallet/purchase-plan", { plan_id: planId })).data,
    onSuccess: async (data) => { toast.success("Plan activated with credits"); await refreshAll(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  const openTopup = (amount = 0) => {
    if (!topupEnabled) { toast.info(topupMsg); return; }
    setPresetAmount(amount); setTopupOpen(true);
  };

  const planCta = (p) => {
    if (p.id === currentPlanId) return { label: "Current plan", disabled: true, variant: "outline" };
    if (p.id === "free") return { label: "Free", disabled: true, variant: "outline" };
    if (p.price == null) return { label: "Contact sales", variant: "outline", action: () => toast.info("Our team will reach out — sales@midnightlink.link") };
    const short = p.price - balance;
    if (short > 0) return { label: topupEnabled ? `Top up ${rp(short)}` : "Top up unavailable", variant: "default", topup: true, disabled: !topupEnabled, action: () => openTopup(short) };
    return { label: `Activate — ${p.price.toLocaleString("id-ID")} credits`, variant: "default", action: () => purchase.mutate(p.id) };
  };

  return (
    <DashboardLayout>
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold tracking-tight">Billing</h1>
        <p className="mt-1 text-sm text-muted-foreground">Top up credits and activate plans. 1 credit = Rp1.</p>
      </div>

      {noAccess ? (
        <Card className="flex flex-col items-center gap-3 border-dashed py-16 text-center" data-testid="billing-no-access">
          <Lock className="h-8 w-8 text-muted-foreground/50" />
          <div>
            <h3 className="font-display font-semibold">Billing is restricted</h3>
            <p className="text-sm text-muted-foreground">Only Owners and Billing Managers can view or change billing.</p>
          </div>
        </Card>
      ) : (
      <>
      {/* Wallet + current plan */}
      <div className="mb-8 grid gap-4 lg:grid-cols-3">
        <Card className="relative overflow-hidden p-6 lg:col-span-2" data-testid="wallet-card">
          <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/5" />
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Wallet className="h-4 w-4" /> Wallet balance
              </div>
              <p className="mt-2 font-display text-4xl font-black tracking-tight" data-testid="wallet-balance">
                {Number(balance).toLocaleString("id-ID")}
                <span className="ml-2 text-base font-semibold text-muted-foreground">credits</span>
              </p>
              <p className="mt-1 text-sm text-muted-foreground">≈ {rp(balance)} · 1 credit = Rp1</p>
            </div>
            <Button className="gap-2" onClick={() => openTopup(0)} disabled={!topupEnabled} data-testid="wallet-topup-btn">
              <Plus className="h-4 w-4" /> Top up
            </Button>
          </div>
          {!topupEnabled && (
            <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400" data-testid="topup-disabled-banner">
              {topupMsg}
            </div>
          )}
        </Card>

        <Card className="flex flex-col justify-between p-6" data-testid="current-plan-card">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
              <ShieldCheck className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Current plan</p>
              <p className="font-display text-lg font-bold capitalize" data-testid="current-plan-name">
                {subQ.isLoading ? "…" : (subQ.data?.plan?.name || "Free")}
              </p>
            </div>
          </div>
          {subQ.data?.subscription?.current_period_end && (
            <Badge variant="secondary" className="mt-4 w-fit">
              Renews {new Date(subQ.data.subscription.current_period_end).toLocaleDateString("id-ID")}
            </Badge>
          )}
        </Card>
      </div>

      {/* Usage */}
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

      {/* Plans */}
      <h2 className="mb-4 font-display font-semibold">Plans</h2>
      {plansQ.isLoading ? (
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-80 w-full rounded-xl" />)}</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {plans.map((p) => {
            const c = planCta(p);
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
                  variant={c.variant} disabled={c.disabled || purchase.isPending}
                  onClick={c.action} data-testid={`billing-cta-${p.id}`} className="gap-2"
                >
                  {c.topup ? <Plus className="h-4 w-4" /> : (p.price > 0 && !c.disabled && <Wallet className="h-4 w-4" />)}
                  {c.label}
                </Button>
              </Card>
            );
          })}
        </div>
      )}

      {/* Transactions */}
      <div className="mb-4 mt-10 flex items-center gap-2">
        <h2 className="font-display font-semibold">Transaction history</h2>
      </div>
      <Card className="p-6" data-testid="ledger-card">
        {walletQ.isLoading ? (
          <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : (walletQ.data?.ledger?.length ?? 0) === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Info className="h-6 w-6 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">No transactions yet. Top up your wallet to get started.</p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {walletQ.data.ledger.map((e) => {
              const positive = e.amount >= 0;
              return (
                <li key={e.id} className="flex items-center justify-between py-3" data-testid={`ledger-${e.id}`}>
                  <div className="flex items-center gap-3">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-full ${positive ? "bg-emerald-500/10 text-emerald-600" : "bg-destructive/10 text-destructive"}`}>
                      {positive ? <ArrowDownLeft className="h-4 w-4" /> : <ArrowUpRight className="h-4 w-4" />}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{LEDGER_LABEL[e.type] || e.type}</p>
                      <p className="text-xs text-muted-foreground">{e.description}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`font-mono text-sm font-semibold ${positive ? "text-emerald-600" : "text-destructive"}`}>
                      {positive ? "+" : ""}{Number(e.amount).toLocaleString("id-ID")}
                    </p>
                    <p className="font-mono text-xs text-muted-foreground">{new Date(e.created_at).toLocaleDateString("id-ID")}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
      </>
      )}

      <TopupDialog open={topupOpen} onOpenChange={setTopupOpen} presetAmount={presetAmount} onCredited={refreshAll} />
    </DashboardLayout>
  );
}
