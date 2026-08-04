import React, { useState } from "react";
import { useParams, Link, useNavigate, Navigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  LayoutDashboard, Users, Building2, DollarSign, ShieldAlert, Ban, LifeBuoy, KeyRound,
  RefreshCw, LogOut, Search, Trash2, Plus, TrendingUp, MousePointerClick, LinkIcon,
  QrCode, Ticket, ShieldCheck, Plug, ExternalLink, CheckCircle2, XCircle, Loader2,
  Wallet, ArrowDownLeft, ArrowUpRight, Clock,
} from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, CartesianGrid } from "recharts";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import SupportTicketsAdmin from "@/components/SupportTicketsAdmin";

const NAV = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "users", label: "Users", icon: Users },
  { key: "workspaces", label: "Workspaces", icon: Building2 },
  { key: "revenue", label: "Revenue", icon: DollarSign },
  { key: "wallets", label: "Wallets", icon: Wallet },
  { key: "security", label: "Security Events", icon: ShieldAlert },
  { key: "blocklist", label: "Blocklist & Feeds", icon: Ban },
  { key: "tickets", label: "Support Tickets", icon: LifeBuoy },
  { key: "integrations", label: "Integrations", icon: Plug },
  { key: "api", label: "API Usage", icon: KeyRound },
];

const money = (n, cur = "IDR") => (cur || "IDR").toUpperCase() === "IDR"
  ? `Rp ${Number(n || 0).toLocaleString("id-ID")}`
  : `${cur} ${Number(n || 0).toLocaleString()}`;
const shortDate = (d) => (d || "").slice(5);

/* ------------------------------- Overview ------------------------------- */
function Stat({ icon: Icon, label, value, accent }) {
  return (
    <Card className="p-5" data-testid={`admin-stat-${label.toLowerCase().replace(/\W+/g, "-")}`}>
      <div className="flex items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${accent || "bg-primary/10 text-primary"}`}><Icon className="h-5 w-5" /></div>
        <div><p className="text-sm text-muted-foreground">{label}</p><p className="font-display text-2xl font-bold">{value}</p></div>
      </div>
    </Card>
  );
}

function ChartCard({ title, children }) {
  return (
    <Card className="p-6">
      <h3 className="mb-4 font-display font-semibold">{title}</h3>
      <ResponsiveContainer width="100%" height={220}>{children}</ResponsiveContainer>
    </Card>
  );
}

function OverviewSection() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-overview"], queryFn: async () => (await api.get("/admin/overview")).data });
  const refresh = useMutation({
    mutationFn: async () => api.post("/admin/feeds/refresh"),
    onSuccess: () => { toast.success("Threat feeds refreshed"); qc.invalidateQueries({ queryKey: ["admin-overview"] }); },
  });
  if (isLoading || !data) return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="admin-stats">
        <Stat icon={Users} label="Users" value={data.users} />
        <Stat icon={Building2} label="Workspaces" value={data.workspaces} />
        <Stat icon={LinkIcon} label="Links" value={data.links} />
        <Stat icon={QrCode} label="QR Codes" value={data.qr} />
        <Stat icon={MousePointerClick} label="Total Clicks" value={data.events} />
        <Stat icon={ShieldAlert} label="Blocked" value={data.blocked} accent="bg-red-500/10 text-red-500" />
        <Stat icon={DollarSign} label="Revenue" value={money(data.revenue)} accent="bg-emerald-500/10 text-emerald-500" />
        <Stat icon={Ticket} label="Open Tickets" value={data.open_tickets} accent="bg-amber-500/10 text-amber-500" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="New signups (14 days)">
          <AreaChart data={data.signups_series} margin={{ left: -28, right: 8, top: 8 }}>
            <defs><linearGradient id="gS" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.4} /><stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid strokeDasharray="3 3" opacity={0.15} vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} fontSize={11} tickLine={false} axisLine={false} />
            <Tooltip labelFormatter={shortDate} />
            <Area type="monotone" dataKey="count" name="Signups" stroke="hsl(var(--primary))" fill="url(#gS)" strokeWidth={2} />
          </AreaChart>
        </ChartCard>
        <ChartCard title="Traffic (14 days)">
          <AreaChart data={data.events_series} margin={{ left: -28, right: 8, top: 8 }}>
            <defs>
              <linearGradient id="gC" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} /><stop offset="95%" stopColor="#3b82f6" stopOpacity={0} /></linearGradient>
              <linearGradient id="gB" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} /><stop offset="95%" stopColor="#ef4444" stopOpacity={0} /></linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" opacity={0.15} vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} fontSize={11} tickLine={false} axisLine={false} />
            <Tooltip labelFormatter={shortDate} />
            <Area type="monotone" dataKey="clicks" name="Clicks" stroke="#3b82f6" fill="url(#gC)" strokeWidth={2} />
            <Area type="monotone" dataKey="blocked" name="Blocked" stroke="#ef4444" fill="url(#gB)" strokeWidth={2} />
          </AreaChart>
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="flex flex-wrap items-center justify-between gap-3 p-6 lg:col-span-2" data-testid="admin-feeds-card">
          <div>
            <h3 className="font-display font-semibold">Threat intelligence feeds</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {data.feeds?.tor_count ?? 0} Tor exit nodes · {data.feeds?.datacenter_ranges ?? 0} datacenter ranges · last refresh {data.feeds?.last_refresh ? new Date(data.feeds.last_refresh).toLocaleString() : "—"}
            </p>
          </div>
          <Button onClick={() => refresh.mutate()} disabled={refresh.isPending} className="gap-2" data-testid="admin-refresh-feeds-btn"><RefreshCw className={`h-4 w-4 ${refresh.isPending ? "animate-spin" : ""}`} />Refresh feeds</Button>
        </Card>
        <Card className="p-6" data-testid="admin-plan-card">
          <h3 className="mb-3 font-display font-semibold">Plans</h3>
          <ul className="space-y-2">
            {Object.entries(data.by_plan || {}).map(([plan, count]) => (
              <li key={plan} className="flex items-center justify-between text-sm">
                <span className="capitalize">{plan}</span>
                <Badge variant="secondary">{count}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

/* -------------------------------- Users --------------------------------- */
function UsersSection() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", search],
    queryFn: async () => (await api.get("/admin/users", { params: search ? { search } : {} })).data,
  });
  const update = useMutation({
    mutationFn: async ({ id, patch }) => api.patch(`/admin/users/${id}`, patch),
    onSuccess: () => { toast.success("User updated"); qc.invalidateQueries({ queryKey: ["admin-users"] }); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const rows = data?.items || [];

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input placeholder="Search name or email…" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" data-testid="admin-user-search" />
      </div>
      {isLoading ? <Skeleton className="h-64 w-full" /> : (
        <Table>
          <TableHeader><TableRow><TableHead>User</TableHead><TableHead>Role</TableHead><TableHead>Joined</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
          <TableBody>
            {rows.map((u) => {
              const isSelf = u.id === user?.id;
              return (
                <TableRow key={u.id} data-testid={`admin-user-row-${u.email}`}>
                  <TableCell><div className="min-w-0"><p className="truncate font-medium">{u.name}{isSelf && <span className="ml-1 text-xs text-muted-foreground">(you)</span>}</p><p className="truncate text-xs text-muted-foreground">{u.email}</p></div></TableCell>
                  <TableCell>
                    {isSelf ? <Badge className="capitalize">{u.role}</Badge> : (
                      <Select value={u.role === "admin" ? "admin" : "user"} onValueChange={(role) => update.mutate({ id: u.id, patch: { role } })}>
                        <SelectTrigger className="h-8 w-[110px]" data-testid={`user-role-select-${u.email}`}><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="admin">Admin</SelectItem><SelectItem value="user">User</SelectItem></SelectContent>
                      </Select>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</TableCell>
                  <TableCell>
                    {isSelf ? <Badge variant="outline">Active</Badge> : (
                      <div className="flex items-center gap-2">
                        <Switch checked={!u.suspended} onCheckedChange={(active) => update.mutate({ id: u.id, patch: { suspended: !active } })} data-testid={`user-suspend-${u.email}`} />
                        <span className={`text-xs ${u.suspended ? "text-red-500" : "text-emerald-600"}`}>{u.suspended ? "Suspended" : "Active"}</span>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

/* ------------------------------ Workspaces ------------------------------ */
function WorkspacesSection() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-workspaces"], queryFn: async () => (await api.get("/admin/workspaces")).data });
  const update = useMutation({
    mutationFn: async ({ id, suspended }) => api.patch(`/admin/workspaces/${id}`, { suspended }),
    onSuccess: () => { toast.success("Workspace updated"); qc.invalidateQueries({ queryKey: ["admin-workspaces"] }); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const rows = data?.items || [];
  return (
    <Card className="p-6">
      {isLoading ? <Skeleton className="h-64 w-full" /> : (
        <Table>
          <TableHeader><TableRow><TableHead>Workspace</TableHead><TableHead>Plan</TableHead><TableHead>Members</TableHead><TableHead>Links</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
          <TableBody>
            {rows.map((w) => (
              <TableRow key={w.id} data-testid={`admin-ws-row-${w.id}`}>
                <TableCell className="font-medium">{w.name}</TableCell>
                <TableCell><Badge variant="secondary" className="capitalize">{w.plan || "free"}</Badge></TableCell>
                <TableCell>{w.member_count}</TableCell>
                <TableCell>{w.link_count}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch checked={!w.suspended} onCheckedChange={(active) => update.mutate({ id: w.id, suspended: !active })} data-testid={`ws-suspend-${w.id}`} />
                    <span className={`text-xs ${w.suspended ? "text-red-500" : "text-emerald-600"}`}>{w.suspended ? "Suspended" : "Active"}</span>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

/* ------------------------------- Revenue -------------------------------- */
function RevenueSection() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-revenue"], queryFn: async () => (await api.get("/admin/revenue")).data });
  if (isLoading || !data) return <Skeleton className="h-64 w-full rounded-xl" />;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat icon={DollarSign} label="Total revenue" value={money(data.paid_total)} accent="bg-emerald-500/10 text-emerald-500" />
        <Stat icon={DollarSign} label="Pending" value={money(data.pending_total)} accent="bg-amber-500/10 text-amber-500" />
        <Stat icon={Ticket} label="Paid invoices" value={data.paid_count} />
        <Stat icon={Ticket} label="Pending invoices" value={data.pending_count} />
      </div>
      <Card className="p-6">
        <h3 className="mb-4 font-display font-semibold">Recent invoices</h3>
        <Table>
          <TableHeader><TableRow><TableHead>Workspace</TableHead><TableHead>Plan</TableHead><TableHead>Amount</TableHead><TableHead>Status</TableHead><TableHead>Date</TableHead></TableRow></TableHeader>
          <TableBody>
            {data.invoices.map((i) => (
              <TableRow key={i.id} data-testid={`invoice-row-${i.id}`}>
                <TableCell className="font-medium">{i.workspace_name}</TableCell>
                <TableCell className="capitalize">{i.plan_name || i.plan_id}</TableCell>
                <TableCell className="font-mono">{money(i.amount, i.currency)}</TableCell>
                <TableCell><Badge variant={i.status === "paid" ? "default" : "secondary"} className="capitalize">{i.status}</Badge></TableCell>
                <TableCell className="text-sm text-muted-foreground">{i.created_at ? new Date(i.created_at).toLocaleDateString() : "—"}</TableCell>
              </TableRow>
            ))}
            {data.invoices.length === 0 && <TableRow><TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">No invoices yet.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

/* --------------------------- Security Events ---------------------------- */
function SecuritySection() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-sec"], queryFn: async () => (await api.get("/admin/security-events", { params: { limit: 100 } })).data });
  const rows = data?.items || [];
  return (
    <Card className="p-6">
      <p className="mb-4 text-sm text-muted-foreground">{data?.total ?? 0} total blocked / challenged events across the platform.</p>
      {isLoading ? <Skeleton className="h-64 w-full" /> : (
        <Table>
          <TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Link</TableHead><TableHead>IP</TableHead><TableHead>Country</TableHead><TableHead>Decision</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
          <TableBody>
            {rows.map((e, idx) => (
              <TableRow key={idx} data-testid="sec-event-row">
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{e.occurred_at ? new Date(e.occurred_at).toLocaleString() : "—"}</TableCell>
                <TableCell className="font-mono text-xs">/{e.alias}</TableCell>
                <TableCell className="font-mono text-xs">{e.ip || "—"}</TableCell>
                <TableCell>{e.country || "—"}</TableCell>
                <TableCell><Badge variant={e.decision === "block" ? "destructive" : "secondary"} className="capitalize">{e.decision}</Badge></TableCell>
                <TableCell className="max-w-[240px] truncate text-xs text-muted-foreground">{(e.risk_reasons || []).join(", ") || e.bot_category || "—"}</TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && <TableRow><TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">No security events yet.</TableCell></TableRow>}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

/* --------------------------- Blocklist & Feeds -------------------------- */
function BlocklistSection() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ value: "", note: "" });
  const { data, isLoading } = useQuery({ queryKey: ["admin-global-blocklist"], queryFn: async () => (await api.get("/admin/global-blocklist")).data });
  const add = useMutation({
    mutationFn: async () => api.post("/admin/global-blocklist", form),
    onSuccess: () => { toast.success("Added to global blocklist"); setForm({ value: "", note: "" }); qc.invalidateQueries({ queryKey: ["admin-global-blocklist"] }); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const del = useMutation({
    mutationFn: async (id) => api.delete(`/admin/global-blocklist/${id}`),
    onSuccess: () => { toast.success("Removed"); qc.invalidateQueries({ queryKey: ["admin-global-blocklist"] }); },
  });
  const rows = data?.items || [];
  return (
    <Card className="p-6">
      <h3 className="mb-1 font-display font-semibold">Global IP blocklist</h3>
      <p className="mb-4 text-sm text-muted-foreground">IPs / CIDR ranges blocked across every workspace.</p>
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="flex-1 space-y-1.5"><label className="text-xs">IP or CIDR</label><Input value={form.value} onChange={(e) => setForm((s) => ({ ...s, value: e.target.value }))} className="font-mono" placeholder="9.9.9.0/24" data-testid="global-value-input" /></div>
        <div className="flex-1 space-y-1.5"><label className="text-xs">Note</label><Input value={form.note} onChange={(e) => setForm((s) => ({ ...s, note: e.target.value }))} data-testid="global-note-input" /></div>
        <Button onClick={() => form.value.trim() && add.mutate()} disabled={add.isPending} className="gap-2" data-testid="global-add-btn"><Plus className="h-4 w-4" />Add</Button>
      </div>
      {isLoading ? <Skeleton className="h-40 w-full" /> : rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No global blocks yet.</p>
      ) : (
        <Table>
          <TableHeader><TableRow><TableHead>Value</TableHead><TableHead>Note</TableHead><TableHead>Added by</TableHead><TableHead></TableHead></TableRow></TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id} data-testid={`global-row-${r.id}`}>
                <TableCell className="font-mono">{r.value}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{r.note || "—"}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{r.added_by}</TableCell>
                <TableCell><Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => del.mutate(r.id)} data-testid={`global-del-${r.id}`}><Trash2 className="h-4 w-4" /></Button></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

/* ------------------------------ API Usage ------------------------------- */
function ApiSection() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-api-usage"], queryFn: async () => (await api.get("/admin/api-usage")).data });
  const rows = data?.items || [];
  return (
    <Card className="p-6">
      <h3 className="mb-4 font-display font-semibold">API keys usage</h3>
      {isLoading ? <Skeleton className="h-40 w-full" /> : (
        <Table>
          <TableHeader><TableRow><TableHead>Label</TableHead><TableHead>Prefix</TableHead><TableHead>Requests</TableHead></TableRow></TableHeader>
          <TableBody>
            {rows.map((k, i) => (
              <TableRow key={i} data-testid="api-usage-row">
                <TableCell>{k.name || k.label}</TableCell>
                <TableCell className="font-mono text-xs">{k.prefix}</TableCell>
                <TableCell className="font-mono">{k.request_count ?? 0}</TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && <TableRow><TableCell colSpan={3} className="py-8 text-center text-sm text-muted-foreground">No API keys yet.</TableCell></TableRow>}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

/* ---------------------------- Integrations ------------------------------ */
function IntegrationsSection() {
  const qc = useQueryClient();
  const [key, setKey] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["admin-ip-intel"],
    queryFn: async () => (await api.get("/admin/ip-intel")).data,
  });

  const save = useMutation({
    mutationFn: async (body) => (await api.put("/admin/ip-intel", body)).data,
    onSuccess: (d) => {
      qc.setQueryData(["admin-ip-intel"], d);
      setKey("");
      toast.success("Integration updated");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });
  const test = useMutation({
    mutationFn: async () => (await api.post("/admin/ip-intel/test")).data,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["admin-ip-intel"] });
      d.ok ? toast.success(d.message) : toast.error(d.message || "Connection failed");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });
  const removeKey = useMutation({
    mutationFn: async () => (await api.delete("/admin/ip-intel/key")).data,
    onSuccess: (d) => {
      qc.setQueryData(["admin-ip-intel"], d);
      toast.success("API key removed");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });

  if (isLoading) return <Skeleton className="h-96 w-full max-w-2xl" data-testid="integrations-loading" />;

  const configured = data?.configured;
  const enabled = data?.enabled;
  const stats = data?.stats || {};
  const lastTest = data?.last_test;

  const StatusBadge = () => {
    if (!configured) return <Badge variant="secondary" data-testid="ipintel-status-badge">Not configured</Badge>;
    if (!enabled) return <Badge variant="outline" className="border-amber-500 text-amber-600" data-testid="ipintel-status-badge">Disabled</Badge>;
    return <Badge className="bg-emerald-600 hover:bg-emerald-600" data-testid="ipintel-status-badge">Active</Badge>;
  };

  return (
    <div className="max-w-2xl space-y-6" data-testid="integrations-section">
      <p className="text-sm text-muted-foreground">
        Connect a paid IP intelligence provider to accurately detect VPNs, proxies, Tor and
        risky IPs on every click. When active, results enrich MidGate's risk scoring and
        per-link proxy/VPN protection automatically.
      </p>

      <Card className="overflow-hidden" data-testid="ipintel-card">
        <div className="flex items-center justify-between gap-3 border-b border-border p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display font-semibold">proxycheck.io</h3>
                <a href="https://proxycheck.io/dashboard/" target="_blank" rel="noreferrer"
                   className="text-muted-foreground hover:text-foreground" data-testid="ipintel-dashboard-link">
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
              <p className="text-xs text-muted-foreground">VPN / Proxy / Tor detection · risk score · ASN</p>
            </div>
          </div>
          <StatusBadge />
        </div>

        <div className="space-y-5 p-5">
          {/* API key */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">API key</label>
            {configured && (
              <p className="text-xs text-muted-foreground">
                Current key: <span className="font-mono">{data.key_masked}</span>
                {data.updated_by && <> · set by {data.updated_by}</>}
              </p>
            )}
            <div className="flex gap-2">
              <Input
                type="password"
                autoComplete="new-password"
                placeholder={configured ? "Enter a new key to replace" : "e.g. 190vm7-37y704-751911-58778j"}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                className="font-mono"
                data-testid="ipintel-key-input"
              />
              <Button
                onClick={() => save.mutate({ api_key: key, enabled: enabled ?? true })}
                disabled={!key.trim() || save.isPending}
                className="gap-2 whitespace-nowrap"
                data-testid="ipintel-save-btn"
              >
                {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Save key
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Stored encrypted on the server and never shown again. Free tier allows 1,000 lookups/day.
            </p>
          </div>

          {/* Enable toggle */}
          <div className="flex items-center justify-between rounded-lg border border-border p-4">
            <div>
              <p className="text-sm font-medium">Enable live lookups</p>
              <p className="text-xs text-muted-foreground">Query proxycheck.io on incoming traffic (cached 24h per IP).</p>
            </div>
            <Switch
              checked={!!enabled}
              disabled={!configured || save.isPending}
              onCheckedChange={(v) => save.mutate({ enabled: v })}
              data-testid="ipintel-enable-switch"
            />
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => test.mutate()} disabled={!configured || test.isPending}
              className="gap-2" data-testid="ipintel-test-btn">
              {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Test connection
            </Button>
            {configured && (
              <Button variant="ghost" onClick={() => removeKey.mutate()} disabled={removeKey.isPending}
                className="gap-2 text-destructive hover:text-destructive" data-testid="ipintel-remove-btn">
                <Trash2 className="h-4 w-4" />Remove key
              </Button>
            )}
          </div>

          {lastTest && (
            <div className={`flex items-start gap-2 rounded-lg p-3 text-sm ${lastTest.ok ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-destructive/10 text-destructive"}`}
              data-testid="ipintel-test-result">
              {lastTest.ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0" />}
              <span>{lastTest.message}</span>
            </div>
          )}
        </div>
      </Card>

      {/* Usage stats */}
      <Card className="p-5" data-testid="ipintel-stats-card">
        <h4 className="mb-4 text-sm font-semibold">Usage this session</h4>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: "API queries", value: stats.queries ?? 0 },
            { label: "Cache hits", value: stats.cache_hits ?? 0 },
            { label: "Cached IPs", value: stats.cached_ips ?? 0 },
            { label: "Errors", value: stats.errors ?? 0 },
          ].map((s) => (
            <div key={s.label} data-testid={`ipintel-stat-${s.label.toLowerCase().replace(/\W+/g, "-")}`}>
              <p className="font-display text-2xl font-bold">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>
        {stats.last_error && (
          <p className="mt-4 text-xs text-destructive">Last error: {stats.last_error}</p>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------- Wallets -------------------------------- */
const creditNum = (n) => Number(n || 0).toLocaleString("id-ID");

function WalletDetailDialog({ workspaceId, onClose }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-wallet-detail", workspaceId],
    queryFn: async () => (await api.get(`/admin/wallets/${workspaceId}`)).data,
    enabled: !!workspaceId,
  });
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl" data-testid="wallet-detail-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">
            {data?.workspace?.name || "Wallet"} · <span className="font-mono">{creditNum(data?.balance)} credits</span>
          </DialogTitle>
          <DialogDescription>Credit ledger and Mayar top-up history for this workspace.</DialogDescription>
        </DialogHeader>
        {isLoading ? <Skeleton className="h-64 w-full" /> : (
          <div className="max-h-[60vh] space-y-6 overflow-auto pr-1">
            <div>
              <h4 className="mb-2 text-sm font-semibold">Ledger</h4>
              {(data?.ledger?.length ?? 0) === 0 ? <p className="text-sm text-muted-foreground">No entries.</p> : (
                <Table>
                  <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Description</TableHead><TableHead className="text-right">Amount</TableHead><TableHead className="text-right">Balance</TableHead><TableHead>Date</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {data.ledger.map((e) => {
                      const pos = e.amount >= 0;
                      return (
                        <TableRow key={e.id} data-testid={`wallet-ledger-${e.id}`}>
                          <TableCell className="capitalize">{e.type}</TableCell>
                          <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground">{e.description}</TableCell>
                          <TableCell className={`text-right font-mono ${pos ? "text-emerald-600" : "text-destructive"}`}>{pos ? "+" : ""}{creditNum(e.amount)}</TableCell>
                          <TableCell className="text-right font-mono text-xs">{creditNum(e.balance_after)}</TableCell>
                          <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{e.created_at ? new Date(e.created_at).toLocaleString("id-ID") : "—"}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
            <div>
              <h4 className="mb-2 text-sm font-semibold">Top-ups (Mayar)</h4>
              {(data?.topups?.length ?? 0) === 0 ? <p className="text-sm text-muted-foreground">No top-ups yet.</p> : (
                <Table>
                  <TableHeader><TableRow><TableHead>Amount</TableHead><TableHead>Status</TableHead><TableHead>Invoice</TableHead><TableHead>Date</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {data.topups.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell className="font-mono">{money(t.amount)}</TableCell>
                        <TableCell><Badge variant={t.credited ? "default" : "secondary"} className="capitalize">{t.credited ? "paid" : t.status}</Badge></TableCell>
                        <TableCell className="font-mono text-xs">{t.mayar_invoice_id ? String(t.mayar_invoice_id).slice(0, 8) : "—"}</TableCell>
                        <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{t.created_at ? new Date(t.created_at).toLocaleString("id-ID") : "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function WalletAdjustDialog({ ws, onClose, onDone }) {
  const [mode, setMode] = useState("credit");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const mut = useMutation({
    mutationFn: async () => {
      const signed = (mode === "debit" ? -1 : 1) * Math.abs(Number(amount) || 0);
      return (await api.post(`/admin/wallets/${ws.workspace_id}/adjust`, { amount: signed, reason: reason || undefined })).data;
    },
    onSuccess: () => { toast.success(mode === "credit" ? "Credits added" : "Credits deducted"); onDone(); onClose(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const amt = Math.abs(Number(amount) || 0);
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md" data-testid="wallet-adjust-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Adjust wallet — {ws.name}</DialogTitle>
          <DialogDescription>Manually credit (refund) or deduct credits. 1 credit = Rp1. Logged to the ledger.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={() => setMode("credit")} className={`rounded-lg border p-3 text-sm font-medium transition-colors ${mode === "credit" ? "border-emerald-500 bg-emerald-500/10 text-emerald-600" : "border-border text-muted-foreground hover:border-emerald-500/50"}`} data-testid="wallet-adjust-mode-credit">
              <ArrowDownLeft className="mb-1 h-4 w-4" /> Credit / Refund
            </button>
            <button type="button" onClick={() => setMode("debit")} className={`rounded-lg border p-3 text-sm font-medium transition-colors ${mode === "debit" ? "border-destructive bg-destructive/10 text-destructive" : "border-border text-muted-foreground hover:border-destructive/50"}`} data-testid="wallet-adjust-mode-debit">
              <ArrowUpRight className="mb-1 h-4 w-4" /> Deduct
            </button>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm">Amount (credits)</label>
            <Input type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} className="font-mono" placeholder="e.g. 50000" data-testid="wallet-adjust-amount" />
            {amt > 0 && <p className="text-xs text-muted-foreground">{mode === "credit" ? "Add" : "Deduct"} {creditNum(amt)} credits (≈ {money(amt)})</p>}
          </div>
          <div className="space-y-1.5">
            <label className="text-sm">Reason (optional)</label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Goodwill refund for ticket #123" data-testid="wallet-adjust-reason" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => amt > 0 && mut.mutate()} disabled={amt <= 0 || mut.isPending} data-testid="wallet-adjust-submit" className="gap-2">
            {mut.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {mode === "credit" ? "Add credits" : "Deduct credits"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function WalletsSection() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [detailWs, setDetailWs] = useState(null);
  const [adjustWs, setAdjustWs] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["admin-wallets", search],
    queryFn: async () => (await api.get("/admin/wallets", { params: search ? { search } : {} })).data,
  });
  const rows = data?.items || [];
  return (
    <div className="space-y-6" data-testid="admin-wallets-section">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={Wallet} label="Credits in circulation" value={creditNum(data?.total_balance)} />
        <Stat icon={DollarSign} label="Total topped up" value={money(data?.total_topup)} accent="bg-emerald-500/10 text-emerald-500" />
        <Stat icon={Clock} label="Pending top-ups" value={data?.pending_topups ?? 0} accent="bg-amber-500/10 text-amber-500" />
      </div>
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search workspace…" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" data-testid="admin-wallet-search" />
        </div>
        {isLoading ? <Skeleton className="h-64 w-full" /> : rows.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No workspaces found.</p>
        ) : (
          <Table>
            <TableHeader><TableRow><TableHead>Workspace</TableHead><TableHead>Plan</TableHead><TableHead className="text-right">Balance</TableHead><TableHead className="text-right">Topped up</TableHead><TableHead></TableHead></TableRow></TableHeader>
            <TableBody>
              {rows.map((w) => (
                <TableRow key={w.workspace_id} data-testid={`wallet-row-${w.workspace_id}`}>
                  <TableCell className="font-medium">{w.name}</TableCell>
                  <TableCell><Badge variant="secondary" className="capitalize">{w.plan}</Badge></TableCell>
                  <TableCell className="text-right font-mono" data-testid={`wallet-balance-${w.workspace_id}`}>{creditNum(w.balance)}</TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">{money(w.topup_total)} · {w.topup_count}x</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setDetailWs(w.workspace_id)} data-testid={`wallet-view-${w.workspace_id}`}>View</Button>
                      <Button size="sm" variant="outline" onClick={() => setAdjustWs(w)} data-testid={`wallet-adjust-${w.workspace_id}`}>Adjust</Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
      {detailWs && <WalletDetailDialog workspaceId={detailWs} onClose={() => setDetailWs(null)} />}
      {adjustWs && <WalletAdjustDialog ws={adjustWs} onClose={() => setAdjustWs(null)} onDone={() => qc.invalidateQueries({ queryKey: ["admin-wallets"] })} />}
    </div>
  );
}

const SECTIONS = {
  overview: OverviewSection,
  users: UsersSection,
  workspaces: WorkspacesSection,
  revenue: RevenueSection,
  wallets: WalletsSection,
  security: SecuritySection,
  blocklist: BlocklistSection,
  tickets: SupportTicketsAdmin,
  integrations: IntegrationsSection,
  api: ApiSection,
};

export default function AdminConsole() {
  const { section = "overview" } = useParams();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  if (!SECTIONS[section]) return <Navigate to="/admin" replace />;
  const Section = SECTIONS[section];
  const current = NAV.find((n) => n.key === section) || NAV[0];
  const initials = (user?.name || "A").slice(0, 2).toUpperCase();
  const doLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="flex min-h-screen bg-muted/30" data-testid="admin-console">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-background lg:flex">
        <div className="flex h-16 items-center gap-2 border-b border-border px-5">
          <Logo />
        </div>
        <div className="px-4 pb-2 pt-4">
          <p className="flex items-center gap-1.5 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" /> Admin Console
          </p>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((n) => {
            const active = n.key === section;
            return (
              <Link key={n.key} to={`/admin/${n.key}`} data-testid={`admin-nav-${n.key}`}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}>
                <n.icon className="h-4 w-4" />{n.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3">
          <button onClick={doLogout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground" data-testid="admin-logout-btn">
            <LogOut className="h-4 w-4" />Log out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border bg-background px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <current.icon className="h-5 w-5 text-primary" />
            <h1 className="font-display text-lg font-bold">{current.label}</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="lg:hidden">
              <Select value={section} onValueChange={(v) => navigate(`/admin/${v}`)}>
                <SelectTrigger className="w-[140px]" data-testid="admin-mobile-nav"><SelectValue /></SelectTrigger>
                <SelectContent>{NAV.map((n) => <SelectItem key={n.key} value={n.key}>{n.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <ThemeToggle />
            <Avatar className="h-9 w-9"><AvatarFallback className="bg-primary text-xs font-semibold text-primary-foreground">{initials}</AvatarFallback></Avatar>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
          <Section />
        </main>
      </div>
    </div>
  );
}
