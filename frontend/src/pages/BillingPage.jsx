import React, { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check, Wallet, ShieldCheck, Loader2, Sparkles, Plus, ArrowUpRight,
  ArrowDownLeft, Lock, ExternalLink, Info, Clock, Zap, AlertTriangle, Ticket,
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
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const rp = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;
const fmtNum = (n) => Number(n || 0).toLocaleString("id-ID");
const fmtReq = (n) => (n >= 1000 ? `${n / 1000}rb` : String(n));

const QUICK = [25000, 50000, 100000, 250000, 500000];
const LEDGER_LABEL = { topup: "Top-up", spend: "Pembelian pass", refund: "Refund", adjustment: "Penyesuaian", bonus: "Bonus" };

const PASS_META = {
  1: { name: "1 Hari", tag: "Cepat" },
  3: { name: "3 Hari", tag: "Singkat" },
  7: { name: "7 Hari", tag: "Mingguan" },
  14: { name: "14 Hari", tag: "Dua mingguan" },
  30: { name: "30 Hari", tag: "Sebulan penuh", popular: true },
};

const fmtDate = (iso) => {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch { return "—"; }
};

function TopupDialog({ open, onOpenChange, presetAmount, onCredited, rupiahPerCredit = 1, bonusPercent = 0, minTopup = 10000 }) {
  const [amount, setAmount] = useState(50000);
  const [pending, setPending] = useState(null); // { order_id, payment_url }
  const [checking, setChecking] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    if (open) {
      setAmount(presetAmount && presetAmount >= minTopup ? presetAmount : Math.max(50000, minTopup));
      setPending(null);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open, presetAmount, minTopup]);

  const stopPolling = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };

  const checkStatus = useCallback(async (orderId, quiet = true) => {
    try {
      const { data } = await api.get(`/wallet/topup/${orderId}`);
      if (data.credited) {
        stopPolling();
        toast.success("Pembayaran diterima — kredit ditambahkan ke wallet");
        onCredited();
        onOpenChange(false);
        return true;
      }
      if (!quiet) toast.info("Pembayaran belum terdeteksi. Mungkin butuh beberapa saat setelah bayar.");
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

  const rpc = Math.max(1, Number(rupiahPerCredit) || 1);
  const amt = Number(amount) || 0;
  const baseCredits = Math.floor(amt / rpc);
  const bonusCredits = Math.floor((baseCredits * (Number(bonusPercent) || 0)) / 100);
  const credits = baseCredits + bonusCredits;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) stopPolling(); onOpenChange(o); }}>
      <DialogContent className="max-w-md" data-testid="topup-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Top up wallet</DialogTitle>
          <DialogDescription>
            Bayar aman dengan QRIS, e-wallet, atau transfer bank via Mayar. 1 kredit = {rp(rpc)}.
          </DialogDescription>
        </DialogHeader>

        {!pending ? (
          <div className="space-y-5">
            <div>
              <Label htmlFor="topup-amount">Jumlah (Rp)</Label>
              <Input
                id="topup-amount" type="number" min={minTopup} step={1000} value={amount}
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
            <div className="rounded-lg bg-muted/50 p-3 text-sm" data-testid="topup-credit-preview">
              Anda menerima <span className="font-mono font-semibold">{fmtNum(credits)} kredit</span>{" "}
              <span className="text-muted-foreground">untuk {rp(amt)}</span>
              {bonusCredits > 0 && <span className="text-primary"> (termasuk {fmtNum(bonusCredits)} bonus)</span>}
            </div>
            <Button
              className="w-full gap-2" disabled={start.isPending || amt < minTopup || credits < 1}
              onClick={() => start.mutate()} data-testid="topup-submit-btn"
            >
              {start.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Memulai…</> : <><ExternalLink className="h-4 w-4" /> Lanjut ke pembayaran</>}
            </Button>
            <p className="text-center text-xs text-muted-foreground">Minimum top-up {rp(minTopup)}.</p>
          </div>
        ) : (
          <div className="space-y-4 text-center" data-testid="topup-waiting">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
              <Loader2 className="h-7 w-7 animate-spin text-primary" />
            </div>
            <div>
              <p className="font-medium">Menunggu pembayaran…</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Selesaikan pembayaran di tab baru. Kredit ditambahkan otomatis setelah terkonfirmasi.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Button variant="outline" className="gap-2" onClick={() => window.open(pending.payment_url, "_blank", "noopener")}>
                <ExternalLink className="h-4 w-4" /> Buka halaman pembayaran
              </Button>
              <Button
                className="gap-2" disabled={checking}
                onClick={async () => { setChecking(true); await checkStatus(pending.order_id, false); setChecking(false); }}
                data-testid="topup-check-btn"
              >
                {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Saya sudah bayar
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PassCard({ pass, rupiahPerCredit, balance, topupEnabled, onBuy, onTopup, buyingReqs }) {
  const meta = PASS_META[pass.days] || { name: `${pass.days} Hari` };
  const defaultIdx = Math.min(2, pass.options.length - 1);
  const [sel, setSel] = useState(pass.options[defaultIdx] || pass.options[0]);
  const price = sel?.price ?? 0;
  const priceCredits = Math.ceil(price / Math.max(1, rupiahPerCredit));
  const short = priceCredits - balance;
  const isBuying = buyingReqs === sel?.requests;

  return (
    <Card
      className={`flex flex-col p-6 ${meta.popular ? "border-primary ring-1 ring-primary" : ""}`}
      data-testid={`pass-card-${pass.days}`}
    >
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-primary" />
          <h3 className="font-display text-lg font-bold uppercase tracking-wide">{meta.name}</h3>
          {meta.popular && <Badge className="gap-1"><Sparkles className="h-3 w-3" />Populer</Badge>}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{meta.tag} · {rp(pass.rate_per_request)}/request</p>
      </div>

      <div className="mb-3">
        <p className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">Jumlah request</p>
        <div className="flex flex-wrap gap-2">
          {pass.options.map((o) => (
            <button
              key={o.requests} type="button" onClick={() => setSel(o)}
              className={`rounded-[4px] border-2 px-2.5 py-1 font-mono text-xs font-semibold transition-colors ${sel?.requests === o.requests ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/50"}`}
              data-testid={`pass-req-${pass.days}-${o.requests}`}
            >
              {fmtReq(o.requests)}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4 mt-auto">
        <p className="font-display text-3xl font-black" data-testid={`pass-price-${pass.days}`}>{rp(price)}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {fmtNum(sel?.requests)} request · = {fmtNum(priceCredits)} kredit
        </p>
      </div>

      <ul className="mb-5 space-y-1.5 text-xs text-muted-foreground">
        <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 shrink-0 text-primary" /> Semua fitur proteksi</li>
        <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 shrink-0 text-primary" /> Link & QR tanpa batas</li>
        <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 shrink-0 text-primary" /> Overflow otomatis pakai kredit</li>
      </ul>

      {short > 0 ? (
        <Button
          variant="default" className="gap-2" disabled={!topupEnabled}
          onClick={() => onTopup(short * Math.max(1, rupiahPerCredit))}
          data-testid={`pass-cta-${pass.days}`}
        >
          <Plus className="h-4 w-4" /> {topupEnabled ? `Top up ${rp(short * Math.max(1, rupiahPerCredit))}` : "Top-up nonaktif"}
        </Button>
      ) : (
        <Button
          variant="default" className="gap-2" disabled={isBuying || buyingReqs != null}
          onClick={() => onBuy({ days: pass.days, requests: sel.requests })}
          data-testid={`pass-cta-${pass.days}`}
        >
          {isBuying ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
          Beli — {fmtNum(priceCredits)} kredit
        </Button>
      )}
    </Card>
  );
}

export default function BillingPage() {
  const { workspace, refreshSession } = useAuth();
  const qc = useQueryClient();
  const [topupOpen, setTopupOpen] = useState(false);
  const [presetAmount, setPresetAmount] = useState(0);

  const passesQ = useQuery({ queryKey: ["passes"], queryFn: async () => (await api.get("/billing/passes")).data });
  const subQ = useQuery({
    queryKey: ["subscription", workspace?.id],
    queryFn: async () => (await api.get("/billing/subscription")).data,
    enabled: !!workspace, retry: false,
  });
  const entQ = useQuery({
    queryKey: ["entitlement", workspace?.id],
    queryFn: async () => (await api.get("/wallet/entitlement")).data,
    enabled: !!workspace, retry: false,
  });
  const walletQ = useQuery({
    queryKey: ["wallet", workspace?.id],
    queryFn: async () => (await api.get("/wallet/summary")).data,
    enabled: !!workspace, retry: false,
  });

  const noAccess = subQ.isError && subQ.error?.response?.status === 403;
  const passes = passesQ.data?.passes || [];
  const ent = entQ.data || {};
  const balance = walletQ.data?.balance ?? 0;
  const topupEnabled = walletQ.data?.topup_enabled ?? true;
  const topupMsg = walletQ.data?.topup_disabled_message
    || "Pembayaran sedang tidak tersedia untuk sementara. Silakan coba lagi nanti.";
  const rupiahPerCredit = Math.max(1, walletQ.data?.rupiah_per_credit ?? 1);
  const bonusPercent = walletQ.data?.bonus_percent ?? 0;
  const minTopup = walletQ.data?.min_topup ?? 10000;
  const reqPerCredit = Math.max(1, walletQ.data?.requests_per_credit ?? ent.requests_per_credit ?? 333);

  const refreshAll = useCallback(async () => {
    await refreshSession();
    qc.invalidateQueries({ queryKey: ["wallet"] });
    qc.invalidateQueries({ queryKey: ["subscription"] });
    qc.invalidateQueries({ queryKey: ["entitlement"] });
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
          toast.success("Pembayaran diterima — kredit ditambahkan ke wallet");
          refreshAll();
        }
      } catch (e) { /* ignore */ }
      if (ticks > 12) clearInterval(iv);
    }, 3000);
    window.history.replaceState({}, "", "/app/billing");
    return () => clearInterval(iv);
  }, [refreshAll]);

  const purchase = useMutation({
    mutationFn: async ({ days, requests }) => (await api.post("/wallet/purchase-pass", { days, requests })).data,
    onSuccess: async (data) => {
      toast.success(`Pass aktif — ${data.label}`);
      await refreshAll();
    },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  const openTopup = (amount = 0) => {
    if (!topupEnabled) { toast.info(topupMsg); return; }
    setPresetAmount(amount); setTopupOpen(true);
  };

  const buyingReqs = purchase.isPending ? purchase.variables?.requests : null;

  // entitlement figures
  const included = ent.requests_included ?? 0;
  const used = ent.requests_used ?? 0;
  const remaining = ent.requests_remaining ?? 0;
  const pct = included ? Math.min(100, Math.round((used / included) * 100)) : 0;
  const overflowReqs = ent.credit_requests_available ?? (balance * reqPerCredit);
  const exhausted = !!ent.quota_exhausted;

  return (
    <DashboardLayout>
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold tracking-tight">Billing</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Beli pass durasi & isi kredit. 1 kredit = {rp(rupiahPerCredit)}. Semua paket punya fitur sama — beda di durasi & jumlah request.
        </p>
      </div>

      {noAccess ? (
        <Card className="flex flex-col items-center gap-3 border-dashed py-16 text-center" data-testid="billing-no-access">
          <Lock className="h-8 w-8 text-muted-foreground/50" />
          <div>
            <h3 className="font-display font-semibold">Billing dibatasi</h3>
            <p className="text-sm text-muted-foreground">Hanya Owner dan Billing Manager yang bisa melihat atau mengubah billing.</p>
          </div>
        </Card>
      ) : (
      <>
      {/* Wallet + active pass */}
      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card className="relative overflow-hidden p-6 lg:col-span-2" data-testid="wallet-card">
          <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/5" />
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Wallet className="h-4 w-4" /> Saldo wallet
              </div>
              <p className="mt-2 font-display text-4xl font-black tracking-tight" data-testid="wallet-balance">
                {fmtNum(balance)}
                <span className="ml-2 text-base font-semibold text-muted-foreground">kredit</span>
              </p>
              <p className="mt-1 text-sm text-muted-foreground">≈ {rp(balance * rupiahPerCredit)} · 1 kredit = {rp(rupiahPerCredit)}</p>
              <p className="mt-1 text-xs text-muted-foreground" data-testid="wallet-overflow-capacity">
                Kapasitas overflow: <span className="font-mono font-semibold text-foreground">{fmtNum(overflowReqs)} request</span> (dari kredit)
              </p>
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

        <Card className="flex flex-col justify-between p-6" data-testid="active-pass-card">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
              <Ticket className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Pass aktif</p>
              <p className="font-display text-base font-bold" data-testid="active-pass-label">
                {entQ.isLoading ? "…" : (ent.active ? ent.label : "Tidak ada pass aktif")}
              </p>
            </div>
          </div>
          {ent.active ? (
            <Badge variant="secondary" className="mt-4 w-fit" data-testid="active-pass-expiry">
              Berlaku sampai {fmtDate(ent.expires_at)}
            </Badge>
          ) : (
            <p className="mt-4 text-xs text-muted-foreground">Beli pass di bawah untuk mengaktifkan proteksi & kuota request.</p>
          )}
        </Card>
      </div>

      {/* Entitlement detail */}
      <Card className="mb-6 p-6" data-testid="entitlement-card">
        <h2 className="mb-4 font-display font-semibold uppercase tracking-wide">Kuota request</h2>
        {entQ.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            <div data-testid="entitlement-quota">
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Request pass</span>
                <span className="font-mono">{ent.active ? `${fmtNum(used)} / ${fmtNum(included)}` : "— / —"}</span>
              </div>
              <Progress value={ent.active ? pct : 0} className={pct >= 100 ? "[&>div]:bg-destructive" : ""} />
              <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-[4px] border-2 border-[hsl(var(--nb-border))] bg-muted/40 p-2">
                  <p className="font-mono text-base font-bold" data-testid="ent-included">{fmtNum(included)}</p>
                  <p className="text-muted-foreground">Total</p>
                </div>
                <div className="rounded-[4px] border-2 border-[hsl(var(--nb-border))] bg-muted/40 p-2">
                  <p className="font-mono text-base font-bold" data-testid="ent-used">{fmtNum(used)}</p>
                  <p className="text-muted-foreground">Terpakai</p>
                </div>
                <div className="rounded-[4px] border-2 border-[hsl(var(--nb-border))] bg-muted/40 p-2">
                  <p className="font-mono text-base font-bold text-primary" data-testid="ent-remaining">{fmtNum(remaining)}</p>
                  <p className="text-muted-foreground">Sisa</p>
                </div>
              </div>
            </div>

            <div className="flex flex-col justify-between gap-3" data-testid="entitlement-overflow">
              <div className="rounded-[4px] border-2 border-[hsl(var(--nb-border))] p-4">
                <p className="text-xs uppercase text-muted-foreground">Cadangan overflow (dari kredit)</p>
                <p className="mt-1 font-display text-2xl font-black" data-testid="ent-credit-requests">{fmtNum(overflowReqs)} <span className="text-sm font-semibold text-muted-foreground">request</span></p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {fmtNum(balance)} kredit × {fmtNum(reqPerCredit)} request/kredit{ent.overflow_requests ? ` + ${fmtNum(ent.overflow_requests)} sisa` : ""}
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                Saat kuota pass habis, request otomatis memakai kredit ({fmtNum(reqPerCredit)} request per 1 kredit).
              </p>
            </div>
          </div>
        )}

        {exhausted && (
          <div className="mt-5 flex items-start gap-3 rounded-[4px] border-2 border-amber-500/60 bg-amber-500/10 p-4 text-sm text-amber-700 dark:text-amber-300" data-testid="quota-exhausted-banner">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Kuota & kredit habis — proteksi dipause</p>
              <p className="mt-0.5 text-amber-700/90 dark:text-amber-300/90">
                Link Anda <span className="font-semibold">tetap redirect</span> agar kampanye tidak mati, tetapi perlindungan
                (bot/proxy/VPN filter) dilonggarkan sampai Anda beli pass baru atau top-up kredit.
              </p>
            </div>
          </div>
        )}
      </Card>

      {/* Passes */}
      <div className="mb-4 flex items-center gap-2">
        <h2 className="font-display font-semibold uppercase tracking-wide">Pilih pass</h2>
        <span className="text-xs text-muted-foreground">— pilih durasi, lalu jumlah request</span>
      </div>
      {passesQ.isLoading ? (
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-96 w-full rounded-xl" />)}</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {passes.map((p) => (
            <PassCard
              key={p.days} pass={p} rupiahPerCredit={rupiahPerCredit} balance={balance}
              topupEnabled={topupEnabled} buyingReqs={buyingReqs}
              onBuy={(v) => purchase.mutate(v)} onTopup={(amt) => openTopup(amt)}
            />
          ))}
        </div>
      )}

      {/* Transactions */}
      <div className="mb-4 mt-10 flex items-center gap-2">
        <h2 className="font-display font-semibold uppercase tracking-wide">Riwayat transaksi</h2>
      </div>
      <Card className="p-6" data-testid="ledger-card">
        {walletQ.isLoading ? (
          <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : (walletQ.data?.ledger?.length ?? 0) === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Info className="h-6 w-6 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">Belum ada transaksi. Top up wallet untuk mulai.</p>
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
                      {positive ? "+" : ""}{fmtNum(e.amount)}
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

      <TopupDialog open={topupOpen} onOpenChange={setTopupOpen} presetAmount={presetAmount} onCredited={refreshAll} rupiahPerCredit={rupiahPerCredit} bonusPercent={bonusPercent} minTopup={minTopup} />
    </DashboardLayout>
  );
}
