import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2, ShieldCheck, Play, X, FlaskConical } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const FIELDS = ["is_bot", "country", "device", "browser", "os", "risk_score", "referrer"];
const OPERATORS = ["equals", "not_equals", "in", "not_in", "contains", "gt", "lt"];
const ACTIONS = [
  { v: "allow", label: "Allow", color: "bg-emerald-500" },
  { v: "challenge", label: "Challenge", color: "bg-amber-500" },
  { v: "block", label: "Block", color: "bg-red-500" },
  { v: "log_only", label: "Log only", color: "bg-slate-400" },
];

const actionColor = (a) => ACTIONS.find((x) => x.v === a)?.color || "bg-slate-400";

function RuleDialog({ open, onOpenChange, onSaved }) {
  const [name, setName] = useState("");
  const [action, setAction] = useState("block");
  const [priority, setPriority] = useState(100);
  const [conditions, setConditions] = useState([{ field: "is_bot", operator: "equals", value: "true" }]);
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    if (open) { setName(""); setAction("block"); setPriority(100); setConditions([{ field: "is_bot", operator: "equals", value: "true" }]); }
  }, [open]);

  const setCond = (i, k, v) => setConditions((c) => c.map((x, idx) => idx === i ? { ...x, [k]: v } : x));
  const addCond = () => setConditions((c) => [...c, { field: "country", operator: "in", value: "" }]);
  const removeCond = (i) => setConditions((c) => c.filter((_, idx) => idx !== i));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const conds = conditions.map((c) => ({
        field: c.field, operator: c.operator,
        value: c.field === "is_bot" ? c.value === "true" : c.value,
      }));
      await api.post("/security/rules", { name, action, priority: Number(priority), enabled: true, conditions: conds });
      toast.success("Rule created");
      onSaved();
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="rule-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">New Security Rule</DialogTitle>
          <DialogDescription>When all conditions match, apply the action to the click.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input required value={name} onChange={(e) => setName(e.target.value)} data-testid="rule-name-input" placeholder="Block bots" />
            </div>
            <div className="space-y-2">
              <Label>Priority</Label>
              <Input type="number" value={priority} onChange={(e) => setPriority(e.target.value)} data-testid="rule-priority-input" />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Action</Label>
            <Select value={action} onValueChange={setAction}>
              <SelectTrigger data-testid="rule-action-select"><SelectValue /></SelectTrigger>
              <SelectContent>{ACTIONS.map((a) => <SelectItem key={a.v} value={a.v}>{a.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Conditions (all must match)</Label>
            {conditions.map((c, i) => (
              <div key={i} className="flex items-center gap-2">
                <Select value={c.field} onValueChange={(v) => setCond(i, "field", v)}>
                  <SelectTrigger className="w-[120px]" data-testid={`cond-field-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>{FIELDS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
                </Select>
                <Select value={c.operator} onValueChange={(v) => setCond(i, "operator", v)}>
                  <SelectTrigger className="w-[110px]" data-testid={`cond-op-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>{OPERATORS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
                </Select>
                <Input className="flex-1" value={String(c.value)} onChange={(e) => setCond(i, "value", e.target.value)} data-testid={`cond-value-${i}`} placeholder="value" />
                {conditions.length > 1 && (
                  <Button type="button" variant="ghost" size="icon" onClick={() => removeCond(i)}><X className="h-4 w-4" /></Button>
                )}
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addCond} data-testid="add-condition-btn"><Plus className="mr-1 h-4 w-4" />Add condition</Button>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={loading} data-testid="rule-save-btn">{loading ? "Saving…" : "Create rule"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Simulator() {
  const [sig, setSig] = useState({ country: "US", device: "Desktop", browser: "Chrome", os: "Windows", is_bot: false });
  const [result, setResult] = useState(null);
  const run = async () => {
    try {
      const { data } = await api.post("/security/simulate", sig);
      setResult(data);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    }
  };
  return (
    <Card className="p-6" data-testid="simulator-card">
      <div className="mb-4 flex items-center gap-2">
        <FlaskConical className="h-4 w-4 text-primary" />
        <h2 className="font-display font-semibold">Rule simulator</h2>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-xs">Country</Label>
          <Input value={sig.country} onChange={(e) => setSig((s) => ({ ...s, country: e.target.value }))} data-testid="sim-country" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Device</Label>
          <Select value={sig.device} onValueChange={(v) => setSig((s) => ({ ...s, device: v }))}>
            <SelectTrigger data-testid="sim-device"><SelectValue /></SelectTrigger>
            <SelectContent>{["Desktop", "Mobile", "Tablet"].map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 col-span-2">
          <Label className="text-xs">Simulate bot traffic</Label>
          <Switch checked={sig.is_bot} onCheckedChange={(v) => setSig((s) => ({ ...s, is_bot: v }))} data-testid="sim-bot-switch" />
        </div>
      </div>
      <Button className="mt-4 w-full gap-2" onClick={run} data-testid="sim-run-btn"><Play className="h-4 w-4" />Evaluate</Button>
      {result && (
        <div className="mt-4 rounded-lg border border-border p-4" data-testid="sim-result">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Decision</span>
            <Badge className="capitalize" data-testid="sim-decision"><span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${actionColor(result.decision)}`} />{result.decision}</Badge>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Risk score</span>
            <span className="font-mono font-bold">{result.risk_score} / 100</span>
          </div>
          {result.reasons?.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
              {result.reasons.map((r, i) => <li key={i}>• {r}</li>)}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}

export default function ProtectionPage() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["rules", workspace?.id],
    queryFn: async () => (await api.get("/security/rules")).data,
    enabled: !!workspace,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["rules"] });

  const toggle = useMutation({
    mutationFn: async (rule) => api.patch(`/security/rules/${rule.id}`, { ...rule, enabled: !rule.enabled }),
    onSuccess: refresh,
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  const del = useMutation({
    mutationFn: async (id) => api.delete(`/security/rules/${id}`),
    onSuccess: () => { toast.success("Rule deleted"); refresh(); },
  });

  const rules = data?.items || [];

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Traffic Protection</h1>
          <p className="mt-1 text-sm text-muted-foreground">Every click is scored and evaluated against your rules.</p>
        </div>
        <Button onClick={() => setDialog(true)} className="gap-2" data-testid="new-rule-btn"><Plus className="h-4 w-4" />New rule</Button>
      </div>

      <Card className="mb-6 p-6">
        <h2 className="mb-4 font-display font-semibold">Default risk thresholds</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { range: "0–29", action: "Allow", color: "bg-emerald-500" },
            { range: "30–59", action: "Challenge", color: "bg-amber-500" },
            { range: "60–79", action: "Block", color: "bg-orange-500" },
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

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="mb-3 font-display font-semibold">Security rules</h2>
          {isLoading ? (
            <div className="space-y-3">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>
          ) : rules.length === 0 ? (
            <Card className="flex flex-col items-center gap-3 border-dashed py-12 text-center" data-testid="rules-empty">
              <ShieldCheck className="h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">No custom rules yet. Default thresholds apply.</p>
              <Button onClick={() => setDialog(true)} variant="outline" className="gap-2"><Plus className="h-4 w-4" />Create your first rule</Button>
            </Card>
          ) : (
            <div className="space-y-3" data-testid="rules-list">
              {rules.map((r) => (
                <Card key={r.id} className="p-4" data-testid={`rule-${r.id}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge className="capitalize"><span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${actionColor(r.action)}`} />{r.action}</Badge>
                        <p className="truncate font-semibold">{r.name}</p>
                        <span className="font-mono text-xs text-muted-foreground">P{r.priority}</span>
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {r.conditions.map((c) => `${c.field} ${c.operator} ${c.value}`).join(" AND ")}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch checked={r.enabled} onCheckedChange={() => toggle.mutate(r)} data-testid={`rule-toggle-${r.id}`} />
                      <Button variant="ghost" size="icon" className="text-destructive" onClick={() => del.mutate(r.id)} data-testid={`rule-delete-${r.id}`}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
        <Simulator />
      </div>

      <RuleDialog open={dialog} onOpenChange={setDialog} onSaved={refresh} />
    </DashboardLayout>
  );
}
