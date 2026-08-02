import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2, ShieldCheck, X, FlaskConical, ListChecks, Network, Radar } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const FIELDS = ["is_bot", "is_headless", "is_tor", "is_datacenter", "is_proxy", "bot_category", "country", "device", "browser", "os", "risk_score", "referrer"];
const BOOL_FIELDS = ["is_bot", "is_headless", "is_tor", "is_datacenter", "is_proxy"];
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
        value: BOOL_FIELDS.includes(c.field) ? c.value === "true" : c.value,
      }));
      await api.post("/security/rules", { name, action, priority: Number(priority), enabled: true, conditions: conds });
      toast.success("Rule created");
      onSaved(); onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
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
              <Input required value={name} onChange={(e) => setName(e.target.value)} data-testid="rule-name-input" placeholder="Block Tor traffic" />
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
                  <SelectTrigger className="w-[130px]" data-testid={`cond-field-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>{FIELDS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
                </Select>
                <Select value={c.operator} onValueChange={(v) => setCond(i, "operator", v)}>
                  <SelectTrigger className="w-[110px]" data-testid={`cond-op-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>{OPERATORS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
                </Select>
                {BOOL_FIELDS.includes(c.field) ? (
                  <Select value={String(c.value)} onValueChange={(v) => setCond(i, "value", v)}>
                    <SelectTrigger className="flex-1" data-testid={`cond-value-${i}`}><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="true">true</SelectItem><SelectItem value="false">false</SelectItem></SelectContent>
                  </Select>
                ) : (
                  <Input className="flex-1" value={String(c.value)} onChange={(e) => setCond(i, "value", e.target.value)} data-testid={`cond-value-${i}`} placeholder="value (e.g. US,ID)" />
                )}
                {conditions.length > 1 && <Button type="button" variant="ghost" size="icon" onClick={() => removeCond(i)}><X className="h-4 w-4" /></Button>}
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

function IntelBadge({ on, label }) {
  return <Badge variant={on ? "default" : "secondary"} className="gap-1">{label}: {on ? "yes" : "no"}</Badge>;
}

function Simulator() {
  const [f, setF] = useState({ ip: "8.8.8.8", country: "US", ua: "Mozilla/5.0 (Windows NT 10.0; Win64) Chrome/120" });
  const [result, setResult] = useState(null);
  const run = async () => {
    try { setResult((await api.post("/security/simulate", f)).data); }
    catch (err) { toast.error(formatApiError(err.response?.data?.detail) || err.message); }
  };
  return (
    <Card className="p-6" data-testid="simulator-card">
      <div className="mb-4 flex items-center gap-2"><FlaskConical className="h-4 w-4 text-primary" /><h2 className="font-display font-semibold">Request simulator</h2></div>
      <div className="space-y-3">
        <div className="space-y-1.5"><Label className="text-xs">IP address</Label><Input value={f.ip} onChange={(e) => setF((s) => ({ ...s, ip: e.target.value }))} data-testid="sim-ip" placeholder="e.g. 3.5.1.1 (AWS)" /></div>
        <div className="space-y-1.5"><Label className="text-xs">User-Agent</Label><Input value={f.ua} onChange={(e) => setF((s) => ({ ...s, ua: e.target.value }))} data-testid="sim-ua" /></div>
        <div className="space-y-1.5"><Label className="text-xs">Country</Label><Input value={f.country} onChange={(e) => setF((s) => ({ ...s, country: e.target.value }))} data-testid="sim-country" /></div>
      </div>
      <Button className="mt-4 w-full gap-2" onClick={run} data-testid="sim-run-btn"><Radar className="h-4 w-4" />Evaluate</Button>
      {result && (
        <div className="mt-4 rounded-lg border border-border p-4" data-testid="sim-result">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Decision</span>
            <Badge className="capitalize" data-testid="sim-decision"><span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${actionColor(result.decision)}`} />{result.decision}</Badge>
          </div>
          <div className="mt-2 flex items-center justify-between"><span className="text-sm text-muted-foreground">Risk score</span><span className="font-mono font-bold">{result.risk_score} / 100</span></div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <IntelBadge on={result.signals?.is_bot} label="Bot" />
            <IntelBadge on={result.signals?.is_tor} label="Tor" />
            <IntelBadge on={result.signals?.is_datacenter} label="Datacenter" />
            <IntelBadge on={result.signals?.is_proxy} label="Proxy" />
          </div>
          {result.reasons?.length > 0 && <ul className="mt-3 space-y-1 text-xs text-muted-foreground">{result.reasons.map((r, i) => <li key={i}>• {r}</li>)}</ul>}
        </div>
      )}
    </Card>
  );
}

function IPLists() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ list_type: "block", value: "", note: "" });
  const { data, isLoading } = useQuery({ queryKey: ["ip-rules"], queryFn: async () => (await api.get("/security/ip-rules")).data });
  const add = useMutation({
    mutationFn: async () => api.post("/security/ip-rules", form),
    onSuccess: () => { toast.success("IP rule added"); setForm({ list_type: form.list_type, value: "", note: "" }); qc.invalidateQueries({ queryKey: ["ip-rules"] }); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const del = useMutation({ mutationFn: async (id) => api.delete(`/security/ip-rules/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["ip-rules"] }) });
  const items = data?.items || [];
  const allow = items.filter((i) => i.list_type === "allow");
  const block = items.filter((i) => i.list_type === "block");

  const List = ({ title, rows, variant }) => (
    <Card className="p-5">
      <h3 className="mb-3 font-display font-semibold">{title} <span className="text-sm font-normal text-muted-foreground">({rows.length})</span></h3>
      {rows.length === 0 ? <p className="py-4 text-center text-sm text-muted-foreground">Empty.</p> : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2" data-testid={`ip-rule-${r.value}`}>
              <div><span className="font-mono text-sm">{r.value}</span>{r.note && <span className="ml-2 text-xs text-muted-foreground">{r.note}</span>}</div>
              <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => del.mutate(r.id)} data-testid={`ip-del-${r.value}`}><Trash2 className="h-4 w-4" /></Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <h3 className="mb-3 font-display font-semibold">Add IP rule</h3>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5"><Label className="text-xs">List</Label>
            <Select value={form.list_type} onValueChange={(v) => setForm((s) => ({ ...s, list_type: v }))}>
              <SelectTrigger className="w-[130px]" data-testid="ip-list-type"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="block">Blocklist</SelectItem><SelectItem value="allow">Allowlist</SelectItem></SelectContent>
            </Select>
          </div>
          <div className="flex-1 space-y-1.5"><Label className="text-xs">IP or CIDR</Label><Input value={form.value} onChange={(e) => setForm((s) => ({ ...s, value: e.target.value }))} data-testid="ip-value-input" placeholder="1.2.3.4 or 10.0.0.0/24" className="font-mono" /></div>
          <div className="flex-1 space-y-1.5"><Label className="text-xs">Note</Label><Input value={form.note} onChange={(e) => setForm((s) => ({ ...s, note: e.target.value }))} data-testid="ip-note-input" placeholder="optional" /></div>
          <Button onClick={() => add.mutate()} disabled={!form.value} className="gap-2" data-testid="ip-add-btn"><Plus className="h-4 w-4" />Add</Button>
        </div>
      </Card>
      {isLoading ? <Skeleton className="h-40 w-full rounded-xl" /> : (
        <div className="grid gap-4 md:grid-cols-2">
          <List title="Allowlist (always allowed)" rows={allow} />
          <List title="Blocklist (always blocked)" rows={block} />
        </div>
      )}
    </div>
  );
}

function Feeds() {
  const { data } = useQuery({ queryKey: ["feeds"], queryFn: async () => (await api.get("/security/feeds")).data });
  return (
    <div className="grid gap-4 sm:grid-cols-3" data-testid="feeds-card">
      <Card className="p-5"><p className="text-sm text-muted-foreground">Tor exit nodes</p><p className="mt-1 font-display text-3xl font-bold">{data?.tor_count ?? "…"}</p></Card>
      <Card className="p-5"><p className="text-sm text-muted-foreground">Datacenter ranges</p><p className="mt-1 font-display text-3xl font-bold">{data?.datacenter_ranges ?? "…"}</p></Card>
      <Card className="p-5"><p className="text-sm text-muted-foreground">Last refresh</p><p className="mt-1 text-sm font-medium">{data?.last_refresh ? new Date(data.last_refresh).toLocaleString() : "—"}</p></Card>
    </div>
  );
}

export default function ProtectionPage() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["rules", workspace?.id], queryFn: async () => (await api.get("/security/rules")).data, enabled: !!workspace });
  const refresh = () => qc.invalidateQueries({ queryKey: ["rules"] });
  const toggle = useMutation({ mutationFn: async (rule) => api.patch(`/security/rules/${rule.id}`, { ...rule, enabled: !rule.enabled }), onSuccess: refresh });
  const del = useMutation({ mutationFn: async (id) => api.delete(`/security/rules/${id}`), onSuccess: () => { toast.success("Rule deleted"); refresh(); } });
  const rules = data?.items || [];

  return (
    <DashboardLayout>
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold tracking-tight">Traffic Protection</h1>
        <p className="mt-1 text-sm text-muted-foreground">Score every click, block bots, proxies, Tor and datacenter IPs.</p>
      </div>

      <Feeds />

      <Tabs defaultValue="rules" className="mt-6">
        <TabsList data-testid="protection-tabs">
          <TabsTrigger value="rules" data-testid="tab-rules"><ListChecks className="mr-1.5 h-4 w-4" />Rules</TabsTrigger>
          <TabsTrigger value="ip" data-testid="tab-ip"><Network className="mr-1.5 h-4 w-4" />IP Lists</TabsTrigger>
          <TabsTrigger value="sim" data-testid="tab-sim"><FlaskConical className="mr-1.5 h-4 w-4" />Simulator</TabsTrigger>
        </TabsList>

        <TabsContent value="rules" className="mt-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display font-semibold">Security rules</h2>
            <Button onClick={() => setDialog(true)} className="gap-2" data-testid="new-rule-btn"><Plus className="h-4 w-4" />New rule</Button>
          </div>
          {isLoading ? <div className="space-y-3">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>
          : rules.length === 0 ? (
            <Card className="flex flex-col items-center gap-3 border-dashed py-12 text-center" data-testid="rules-empty">
              <ShieldCheck className="h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">No custom rules yet. Default risk thresholds apply (0–29 allow, 30–59 challenge, 60+ block).</p>
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
                      <p className="mt-1 truncate text-xs text-muted-foreground">{r.conditions.map((c) => `${c.field} ${c.operator} ${c.value}`).join(" AND ")}</p>
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
        </TabsContent>

        <TabsContent value="ip" className="mt-4"><IPLists /></TabsContent>
        <TabsContent value="sim" className="mt-4"><div className="max-w-lg"><Simulator /></div></TabsContent>
      </Tabs>

      <RuleDialog open={dialog} onOpenChange={setDialog} onSaved={refresh} />
    </DashboardLayout>
  );
}
