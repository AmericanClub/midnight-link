import React, { useState } from "react";
import { useParams, Link, useNavigate, Navigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  LayoutDashboard, Users, Building2, DollarSign, ShieldAlert, Ban, LifeBuoy, KeyRound,
  RefreshCw, LogOut, Search, Trash2, Plus, TrendingUp, MousePointerClick, LinkIcon,
  QrCode, Ticket, ShieldCheck, Plug, ExternalLink, CheckCircle2, XCircle, Loader2,
  Wallet, ArrowDownLeft, ArrowUpRight, Clock, Store, Copy, RotateCw, Send, Power, ArrowLeft,
  CreditCard, Save, Coins,
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import SupportTicketsAdmin from "@/components/SupportTicketsAdmin";

const NAV = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "users", label: "Users", icon: Users },
  { key: "workspaces", label: "Workspaces", icon: Building2 },
  { key: "revenue", label: "Revenue", icon: DollarSign },
  { key: "wallets", label: "Wallets", icon: Wallet },
  { key: "payments", label: "Payments", icon: CreditCard },
  { key: "partners", label: "Payment Partners", icon: Store },
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
        risky IPs on every click. When active, results enrich Midnight Link's risk scoring and
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

      <SafeBrowsingCard />
    </div>
  );
}

/* ---------------------- Safe Browsing (Google) -------------------------- */
function SafeBrowsingCard() {
  const qc = useQueryClient();
  const [key, setKey] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["admin-safe-browsing"],
    queryFn: async () => (await api.get("/admin/safe-browsing")).data,
  });
  const save = useMutation({
    mutationFn: async (body) => (await api.put("/admin/safe-browsing", body)).data,
    onSuccess: (d) => { qc.setQueryData(["admin-safe-browsing"], d); setKey(""); toast.success("Safe Browsing updated"); },
    onError: (e) => toast.error(formatApiError(e)),
  });
  const test = useMutation({
    mutationFn: async () => (await api.post("/admin/safe-browsing/test")).data,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["admin-safe-browsing"] });
      d.ok ? toast.success(d.message) : toast.error(d.message || "Connection failed");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });
  const removeKey = useMutation({
    mutationFn: async () => (await api.delete("/admin/safe-browsing/key")).data,
    onSuccess: (d) => { qc.setQueryData(["admin-safe-browsing"], d); toast.success("API key removed"); },
    onError: (e) => toast.error(formatApiError(e)),
  });

  if (isLoading) return <Skeleton className="h-80 w-full max-w-2xl" data-testid="safebrowsing-loading" />;

  const configured = data?.configured;
  const enabled = data?.enabled;
  const stats = data?.stats || {};
  const lastTest = data?.last_test;

  const StatusBadge = () => {
    if (!configured) return <Badge variant="secondary" data-testid="sb-status-badge">Not configured</Badge>;
    if (!enabled) return <Badge variant="outline" className="border-amber-500 text-amber-600" data-testid="sb-status-badge">Disabled</Badge>;
    return <Badge className="bg-emerald-600 hover:bg-emerald-600" data-testid="sb-status-badge">Active</Badge>;
  };

  return (
    <div className="space-y-6" data-testid="safebrowsing-section">
      <div className="border-t border-border pt-6">
        <h3 className="font-display font-semibold">URL threat scanning</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Scan every destination URL for phishing, malware and unwanted software <b>before</b> a
          short link or QR is created. Flagged links are rejected — protecting the reputation of
          your domain in email and browsers. Advisory provided by Google.
        </p>
      </div>

      <Card className="overflow-hidden" data-testid="safebrowsing-card">
        <div className="flex items-center justify-between gap-3 border-b border-border p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display font-semibold">Google Safe Browsing</h3>
                <a href="https://developers.google.com/safe-browsing/v4/get-started" target="_blank" rel="noreferrer"
                   className="text-muted-foreground hover:text-foreground" data-testid="sb-dashboard-link">
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
              <p className="text-xs text-muted-foreground">Phishing / malware / unwanted-software detection</p>
            </div>
          </div>
          <StatusBadge />
        </div>

        <div className="space-y-5 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">API key</label>
            {configured && (
              <p className="text-xs text-muted-foreground">
                Current key: <span className="font-mono">{data.key_masked}</span>
                {data.source && <> · source: {data.source}</>}
                {data.updated_by && <> · set by {data.updated_by}</>}
              </p>
            )}
            <div className="flex gap-2">
              <Input
                type="password"
                autoComplete="new-password"
                placeholder={configured ? "Enter a new key to replace" : "AIza… (from Google Cloud Console)"}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                className="font-mono"
                data-testid="sb-key-input"
              />
              <Button
                onClick={() => save.mutate({ api_key: key, enabled: enabled ?? true })}
                disabled={!key.trim() || save.isPending}
                className="gap-2 whitespace-nowrap"
                data-testid="sb-save-btn"
              >
                {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Save key
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Stored encrypted on the server and never shown again. Enable the <b>Safe Browsing API</b> in Google Cloud Console — free (non-commercial).
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border p-4">
            <div>
              <p className="text-sm font-medium">Scan destination URLs</p>
              <p className="text-xs text-muted-foreground">Reject phishing/malware links when members create or edit them.</p>
            </div>
            <Switch
              checked={!!enabled}
              disabled={!configured || save.isPending}
              onCheckedChange={(v) => save.mutate({ enabled: v })}
              data-testid="sb-enable-switch"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => test.mutate()} disabled={!configured || test.isPending}
              className="gap-2" data-testid="sb-test-btn">
              {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Test connection
            </Button>
            {configured && (
              <Button variant="ghost" onClick={() => removeKey.mutate()} disabled={removeKey.isPending}
                className="gap-2 text-destructive hover:text-destructive" data-testid="sb-remove-btn">
                <Trash2 className="h-4 w-4" />Remove key
              </Button>
            )}
          </div>

          {lastTest && (
            <div className={`flex items-start gap-2 rounded-lg p-3 text-sm ${lastTest.ok ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-destructive/10 text-destructive"}`}
              data-testid="sb-test-result">
              {lastTest.ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0" />}
              <span>{lastTest.message}</span>
            </div>
          )}
        </div>
      </Card>

      <Card className="p-5" data-testid="sb-stats-card">
        <h4 className="mb-4 text-sm font-semibold">Scan stats this session</h4>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: "URLs scanned", value: stats.queries ?? 0 },
            { label: "Threats blocked", value: stats.blocked ?? 0 },
            { label: "Cache hits", value: stats.cache_hits ?? 0 },
            { label: "Errors", value: stats.errors ?? 0 },
          ].map((s) => (
            <div key={s.label} data-testid={`sb-stat-${s.label.toLowerCase().replace(/\W+/g, "-")}`}>
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

function PaymentSwitchCard() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState(null);
  const { data } = useQuery({
    queryKey: ["payment-settings"],
    queryFn: async () => (await api.get("/admin/payment-settings")).data,
  });
  const enabled = data?.topup_enabled ?? true;
  const message = msg ?? data?.topup_disabled_message ?? "";
  const save = async (patch) => {
    try {
      await api.put("/admin/payment-settings", patch);
      toast.success("Payment settings updated");
      qc.invalidateQueries({ queryKey: ["payment-settings"] });
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };
  return (
    <Card className="p-6" data-testid="payment-switch-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-display text-base font-semibold">Wallet top-up payments</h3>
            <Badge variant={enabled ? "default" : "destructive"} data-testid="payment-status-badge">{enabled ? "Enabled" : "Disabled"}</Badge>
          </div>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Master switch for customer wallet top-ups (Mayar QRIS). Turn it <strong>off</strong> to stop
            all top-ups so no Mayar fees are incurred until your cheaper gateways are approved.
            Partner “midnight” charges are <strong>not</strong> affected.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-muted-foreground">{enabled ? "On" : "Off"}</span>
          <Switch checked={enabled} onCheckedChange={(v) => save({ topup_enabled: v })} data-testid="payment-topup-toggle" />
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <label className="text-xs font-medium text-muted-foreground">Message shown to customers when off</label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input value={message} onChange={(e) => setMsg(e.target.value)} placeholder="Pembayaran sedang tidak tersedia untuk sementara. Silakan coba lagi nanti." data-testid="payment-message-input" />
          <Button variant="outline" onClick={() => save({ topup_disabled_message: message })} data-testid="payment-message-save">Save message</Button>
        </div>
      </div>
    </Card>
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
      <PaymentSwitchCard />
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

/* -------------------------- Payment Partners ---------------------------- */
const copyText = (t) => { navigator.clipboard?.writeText(t); toast.success("Copied to clipboard"); };

function SecretReveal({ label, value, testid }) {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
      <p className="mb-1 text-xs font-medium text-amber-600">{label} — shown once, copy it now</p>
      <div className="flex items-center gap-2">
        <code className="flex-1 truncate rounded bg-background px-2 py-1 font-mono text-xs" data-testid={testid}>{value}</code>
        <Button size="sm" variant="outline" className="gap-1" onClick={() => copyText(value)}><Copy className="h-3.5 w-3.5" /> Copy</Button>
      </div>
    </div>
  );
}

function NewPartnerDialog({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [hook, setHook] = useState("");
  const [creds, setCreds] = useState(null);
  const mut = useMutation({
    mutationFn: async () => (await api.post("/admin/partners", {
      name, source_tag: tag || undefined, webhook_url: hook || undefined,
    })).data,
    onSuccess: (d) => { setCreds(d); onCreated(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg" data-testid="new-partner-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{creds ? "Partner created" : "New payment partner"}</DialogTitle>
          <DialogDescription>{creds ? "Store these credentials in the partner app now." : "Create a partner app (e.g. midnight) that can collect payments through Midnight Link."}</DialogDescription>
        </DialogHeader>
        {!creds ? (
          <div className="space-y-4">
            <div className="space-y-1.5"><label className="text-sm">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="midnight" data-testid="partner-name-input" /></div>
            <div className="space-y-1.5"><label className="text-sm">Source tag (optional)</label>
              <Input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="midnight" /></div>
            <div className="space-y-1.5"><label className="text-sm">Webhook URL (where Midnight Link sends charge.paid)</label>
              <Input value={hook} onChange={(e) => setHook(e.target.value)} placeholder="https://midnight.app/api/midgate/webhook" data-testid="partner-hook-input" /></div>
            <DialogFooter>
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button onClick={() => name.length >= 2 && mut.mutate()} disabled={name.length < 2 || mut.isPending} data-testid="partner-create-submit" className="gap-2">
                {mut.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Create partner
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-3">
            <SecretReveal label="Partner API Key (Authorization: Bearer …)" value={creds.api_key} testid="partner-new-apikey" />
            <SecretReveal label="Webhook Signing Secret (verify X-MidnightLink-Signature)" value={creds.webhook_secret} testid="partner-new-secret" />
            <DialogFooter><Button onClick={onClose} data-testid="partner-creds-done">Done</Button></DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function FilterChips({ value, onChange, options }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button key={o.value} type="button" onClick={() => onChange(o.value)} data-testid={`filter-${o.value}`}
          className={`rounded-full border px-3 py-1 text-xs transition-colors ${value === o.value ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/50"}`}>{o.label}</button>
      ))}
    </div>
  );
}

function Pager({ data, onPage }) {
  if (!data || (data.total ?? 0) === 0) return null;
  const { page, pages, total } = data;
  return (
    <div className="flex items-center justify-between pt-3 text-sm text-muted-foreground">
      <span>{total} total · page {page} of {pages}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)} data-testid="pager-prev">Prev</Button>
        <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)} data-testid="pager-next">Next</Button>
      </div>
    </div>
  );
}

function PaginatedCharges({ partnerId, refreshParent }) {
  const [status, setStatus] = useState("all");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["partner-charges", partnerId, status, q, page],
    queryFn: async () => (await api.get(`/admin/partners/${partnerId}/charges`, {
      params: { status: status === "all" ? undefined : status, q: q || undefined, page, limit: 15 },
    })).data,
  });
  const apply = () => { setQ(qInput.trim()); setPage(1); };
  const resend = async (cid) => {
    try { await api.post(`/admin/partners/${partnerId}/charges/${cid}/resend`); toast.success("Webhook resent"); refetch(); refreshParent?.(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };
  const items = data?.items || [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <FilterChips value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={[
          { value: "all", label: "All" }, { value: "paid", label: "Paid" },
          { value: "pending", label: "Pending" }, { value: "expired", label: "Expired" }]} />
        <div className="ml-auto flex items-center gap-2">
          <Input value={qInput} onChange={(e) => setQInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && apply()} placeholder="Search reference or customer…" className="h-9 w-60" data-testid="charge-search" />
          <Button size="sm" variant="outline" onClick={apply}>Search</Button>
        </div>
      </div>
      {isLoading ? <Skeleton className="h-56 w-full" /> : items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No charges match.</p>
      ) : (
        <Table>
          <TableHeader><TableRow><TableHead>Reference</TableHead><TableHead>Customer</TableHead><TableHead className="text-right">Amount</TableHead><TableHead>Status</TableHead><TableHead>Notified</TableHead><TableHead>Created</TableHead><TableHead></TableHead></TableRow></TableHeader>
          <TableBody>
            {items.map((c) => (
              <TableRow key={c.id} data-testid={`partner-charge-${c.id}`}>
                <TableCell className="font-mono text-xs">{c.reference_id}</TableCell>
                <TableCell className="text-xs" data-testid={`partner-charge-customer-${c.id}`}>
                  <div className="font-medium text-foreground">{c.customer?.name || "—"}</div>
                  {c.customer?.email && <div className="text-muted-foreground">{c.customer.email}</div>}
                </TableCell>
                <TableCell className="text-right font-mono">{money(c.amount)}</TableCell>
                <TableCell><Badge variant={c.status === "paid" ? "default" : "secondary"}>{c.status}</Badge></TableCell>
                <TableCell>{c.notified ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <XCircle className="h-4 w-4 text-muted-foreground/40" />}</TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{c.created_at ? new Date(c.created_at).toLocaleString("id-ID") : "—"}</TableCell>
                <TableCell className="text-right">{c.status === "paid" && <Button size="sm" variant="ghost" className="gap-1" onClick={() => resend(c.id)} data-testid={`partner-resend-${c.id}`}><Send className="h-3.5 w-3.5" /> Resend</Button>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Pager data={data} onPage={setPage} />
    </div>
  );
}

function PaginatedDeliveries({ partnerId }) {
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ["partner-deliveries", partnerId, status, page],
    queryFn: async () => (await api.get(`/admin/partners/${partnerId}/deliveries`, {
      params: { status: status === "all" ? undefined : status, page, limit: 15 },
    })).data,
  });
  const items = data?.items || [];
  return (
    <div className="space-y-4">
      <FilterChips value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={[
        { value: "all", label: "All" }, { value: "success", label: "Success" }, { value: "failed", label: "Failed" }]} />
      {isLoading ? <Skeleton className="h-56 w-full" /> : items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No deliveries match.</p>
      ) : (
        <Table>
          <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Status</TableHead><TableHead>Code</TableHead><TableHead>Attempts</TableHead><TableHead>Error</TableHead><TableHead>When</TableHead></TableRow></TableHeader>
          <TableBody>
            {items.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="font-mono text-xs">{d.event}</TableCell>
                <TableCell><Badge variant={d.status === "success" ? "default" : "destructive"}>{d.status}</Badge></TableCell>
                <TableCell className="font-mono text-xs">{d.status_code ?? "—"}</TableCell>
                <TableCell>{d.attempts}</TableCell>
                <TableCell className="max-w-[180px] truncate text-xs text-muted-foreground">{d.error || "—"}</TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{d.created_at ? new Date(d.created_at).toLocaleString("id-ID") : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Pager data={data} onPage={setPage} />
    </div>
  );
}

function PartnerDetail({ partnerId, onBack }) {
  const qc = useQueryClient();
  const [hook, setHook] = useState(null);
  const [reveal, setReveal] = useState(null);
  const { data, refetch } = useQuery({
    queryKey: ["admin-partner", partnerId],
    queryFn: async () => (await api.get(`/admin/partners/${partnerId}`)).data,
  });
  const p = data?.partner;
  const hookValue = hook ?? (p?.webhook_url || "");
  const run = (fn, ok) => async () => { try { const r = await fn(); if (ok) ok(r); refetch(); qc.invalidateQueries({ queryKey: ["admin-partners"] }); } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); } };
  const saveHook = run(() => api.patch(`/admin/partners/${partnerId}`, { webhook_url: hookValue }), () => toast.success("Webhook saved"));
  const toggle = run(() => api.patch(`/admin/partners/${partnerId}`, { active: !p.active }), () => toast.success("Updated"));
  const rotK = run(() => api.post(`/admin/partners/${partnerId}/rotate-key`), (r) => setReveal({ label: "New API Key", value: r.data.api_key, testid: "partner-rotated-key" }));
  const rotS = run(() => api.post(`/admin/partners/${partnerId}/rotate-secret`), (r) => setReveal({ label: "New Webhook Secret", value: r.data.webhook_secret, testid: "partner-rotated-secret" }));
  const del = run(() => api.delete(`/admin/partners/${partnerId}`), () => { toast.success("Partner deleted"); onBack(); });

  return (
    <div className="space-y-6" data-testid="partner-detail">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground" data-testid="partner-back"><ArrowLeft className="h-4 w-4" /> Back to partners</button>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-display text-xl font-bold">{p?.name || "Partner"}</h2>
        {p && <Badge variant={p.active ? "default" : "secondary"}>{p.active ? "active" : "inactive"}</Badge>}
        <code className="font-mono text-xs text-muted-foreground">{p?.key_prefix}…{p?.key_last4}</code>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={QrCode} label="Charges" value={data?.stats?.charges ?? 0} />
        <Stat icon={CheckCircle2} label="Paid" value={data?.stats?.paid_count ?? 0} accent="bg-emerald-500/10 text-emerald-500" />
        <Stat icon={DollarSign} label="Collected" value={money(data?.stats?.paid_amount)} />
      </div>
      <Tabs defaultValue="charges" className="w-full">
        <TabsList data-testid="partner-tabs">
          <TabsTrigger value="charges" data-testid="tab-charges">Charges</TabsTrigger>
          <TabsTrigger value="deliveries" data-testid="tab-deliveries">Deliveries</TabsTrigger>
          <TabsTrigger value="settings" data-testid="tab-settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="charges"><Card className="mt-4 p-6"><PaginatedCharges partnerId={partnerId} refreshParent={refetch} /></Card></TabsContent>
        <TabsContent value="deliveries"><Card className="mt-4 p-6"><PaginatedDeliveries partnerId={partnerId} /></Card></TabsContent>
        <TabsContent value="settings">
          <Card className="mt-4 space-y-4 p-6">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Webhook URL <span className="text-xs text-muted-foreground">— where Midnight Link sends charge.paid</span></label>
              <div className="flex gap-2">
                <Input value={hookValue} onChange={(e) => setHook(e.target.value)} placeholder="https://midnight.app/api/midgate/webhook" data-testid="partner-hook-edit" />
                <Button variant="outline" onClick={saveHook} data-testid="partner-hook-save">Save</Button>
              </div>
            </div>
            {reveal && <SecretReveal {...reveal} />}
            <div className="flex flex-wrap gap-2 border-t pt-4">
              <Button size="sm" variant="outline" className="gap-1" onClick={rotK} data-testid="partner-rotate-key"><RotateCw className="h-3.5 w-3.5" /> Rotate API key</Button>
              <Button size="sm" variant="outline" className="gap-1" onClick={rotS}><RotateCw className="h-3.5 w-3.5" /> Rotate secret</Button>
              <Button size="sm" variant="outline" className="gap-1" onClick={toggle} data-testid="partner-toggle-active"><Power className="h-3.5 w-3.5" /> {p?.active ? "Deactivate" : "Activate"}</Button>
              <Button size="sm" variant="destructive" className="ml-auto gap-1" onClick={del} data-testid="partner-delete"><Trash2 className="h-3.5 w-3.5" /> Delete partner</Button>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function PartnersSection() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["admin-partners"],
    queryFn: async () => (await api.get("/admin/partners")).data,
  });
  const rows = data?.items || [];
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-partners"] });
  const totals = rows.reduce((a, p) => ({ collected: a.collected + (p.paid_amount || 0), charges: a.charges + (p.charges || 0) }), { collected: 0, charges: 0 });

  if (selected) return <PartnerDetail partnerId={selected} onBack={() => { setSelected(null); invalidate(); }} />;

  return (
    <div className="space-y-6" data-testid="admin-partners-section">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Apps (e.g. midnight) that collect payments through Midnight Link's Mayar gateway.</p>
        <Button className="gap-2" onClick={() => setShowNew(true)} data-testid="new-partner-btn"><Plus className="h-4 w-4" /> New partner</Button>
      </div>
      {rows.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Stat icon={Store} label="Partners" value={rows.length} />
          <Stat icon={QrCode} label="Total charges" value={totals.charges} />
          <Stat icon={DollarSign} label="Total collected" value={money(totals.collected)} accent="bg-emerald-500/10 text-emerald-500" />
        </div>
      )}
      <Card className="p-6">
        {isLoading ? <Skeleton className="h-56 w-full" /> : rows.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <Store className="h-7 w-7 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">No payment partners yet. Create one for midnight.</p>
          </div>
        ) : (
          <Table>
            <TableHeader><TableRow><TableHead>Partner</TableHead><TableHead>API key</TableHead><TableHead>Webhook</TableHead><TableHead className="text-right">Collected</TableHead><TableHead>Status</TableHead><TableHead></TableHead></TableRow></TableHeader>
            <TableBody>
              {rows.map((p) => (
                <TableRow key={p.id} data-testid={`partner-row-${p.id}`} className="cursor-pointer" onClick={() => setSelected(p.id)}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell className="font-mono text-xs">{p.key_prefix}…{p.key_last4}</TableCell>
                  <TableCell className="max-w-[200px] truncate text-xs text-muted-foreground">{p.webhook_url || "—"}</TableCell>
                  <TableCell className="text-right font-mono">{money(p.paid_amount)} <span className="text-xs text-muted-foreground">· {p.paid_count}/{p.charges}</span></TableCell>
                  <TableCell><Badge variant={p.active ? "default" : "secondary"}>{p.active ? "active" : "inactive"}</Badge></TableCell>
                  <TableCell className="text-right"><Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setSelected(p.id); }} data-testid={`partner-manage-${p.id}`}>Manage</Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
      {showNew && <NewPartnerDialog onClose={() => setShowNew(false)} onCreated={invalidate} />}
    </div>
  );
}

/* ------------------------------- Payments ------------------------------- */
function LabeledField({ label, hint, children }) {
  return (
    <div>
      <label className="text-sm font-display font-bold uppercase tracking-wide">{label}</label>
      {hint && <p className="mb-1.5 mt-0.5 text-xs text-muted-foreground normal-case">{hint}</p>}
      <div className={hint ? "" : "mt-1.5"}>{children}</div>
    </div>
  );
}

function PaymentsSection() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-payment-config"],
    queryFn: async () => (await api.get("/admin/payment-config")).data,
  });

  const [gw, setGw] = useState({ mayar_api_key: "", mayar_webhook_token: "", mayar_base_url: "" });
  const [kq, setKq] = useState({ klikqris_api_key: "", klikqris_merchant_id: "", klikqris_base_url: "" });
  const [activeGw, setActiveGw] = useState("mayar");
  const [cr, setCr] = useState({ rupiah_per_credit: 1000, bonus_percent: 0, min_topup: 10000, requests_per_credit: 333 });
  const [pay, setPay] = useState({ topup_enabled: true, topup_disabled_message: "" });

  React.useEffect(() => {
    if (!data) return;
    setGw((g) => ({ ...g, mayar_base_url: data.gateway?.base_url || "" }));
    setKq((k) => ({ ...k, klikqris_base_url: data.klikqris?.base_url || "",
      klikqris_merchant_id: data.klikqris?.merchant_id || "" }));
    setActiveGw(data.active_gateway || "mayar");
    setCr({
      rupiah_per_credit: data.credits?.rupiah_per_credit ?? 1000,
      bonus_percent: data.credits?.bonus_percent ?? 0,
      min_topup: data.credits?.min_topup ?? 10000,
      requests_per_credit: data.credits?.requests_per_credit ?? 333,
    });
    setPay({
      topup_enabled: data.payments?.topup_enabled ?? true,
      topup_disabled_message: data.payments?.topup_disabled_message || "",
    });
  }, [data]);

  const save = useMutation({
    mutationFn: async (patch) => (await api.put("/admin/payment-config", patch)).data,
    onSuccess: () => {
      toast.success("Settings saved");
      qc.invalidateQueries({ queryKey: ["admin-payment-config"] });
      qc.invalidateQueries({ queryKey: ["wallet"] });
    },
    onError: (e) => toast.error(formatApiError(e.response?.data?.detail) || e.message),
  });
  const test = useMutation({
    mutationFn: async (gateway) => (await api.post(`/admin/payment-config/test${gateway ? `?gateway=${gateway}` : ""}`)).data,
    onSuccess: (r) => (r.ok ? toast.success(r.message) : toast.error(r.message)),
    onError: (e) => toast.error(formatApiError(e.response?.data?.detail) || e.message),
  });

  if (isLoading) {
    return <div className="max-w-3xl space-y-4"><Skeleton className="h-56 w-full" /><Skeleton className="h-56 w-full" /></div>;
  }

  const gwStatus = data?.gateway || {};
  const connected = gwStatus.api_key_set;
  const kqStatus = data?.klikqris || {};
  const kqConnected = kqStatus.api_key_set && kqStatus.merchant_id_set;
  const rpc = Math.max(1, Number(cr.rupiah_per_credit) || 1);
  const bonus = Math.max(0, Number(cr.bonus_percent) || 0);
  const base100 = Math.floor(100000 / rpc);
  const preview100 = base100 + Math.floor((base100 * bonus) / 100);

  const saveGateway = () => {
    const patch = {};
    if (gw.mayar_base_url && gw.mayar_base_url.trim()) patch.mayar_base_url = gw.mayar_base_url.trim();
    if (gw.mayar_api_key.trim()) patch.mayar_api_key = gw.mayar_api_key.trim();
    if (gw.mayar_webhook_token.trim()) patch.mayar_webhook_token = gw.mayar_webhook_token.trim();
    if (Object.keys(patch).length === 0) { toast.info("No gateway changes"); return; }
    save.mutate(patch, { onSuccess: () => setGw((g) => ({ ...g, mayar_api_key: "", mayar_webhook_token: "" })) });
  };
  const saveKlik = () => {
    const patch = {};
    if (kq.klikqris_base_url && kq.klikqris_base_url.trim()) patch.klikqris_base_url = kq.klikqris_base_url.trim();
    if (kq.klikqris_merchant_id && kq.klikqris_merchant_id.trim()) patch.klikqris_merchant_id = kq.klikqris_merchant_id.trim();
    if (kq.klikqris_api_key.trim()) patch.klikqris_api_key = kq.klikqris_api_key.trim();
    if (Object.keys(patch).length === 0) { toast.info("No KlikQRIS changes"); return; }
    save.mutate(patch, { onSuccess: () => setKq((k) => ({ ...k, klikqris_api_key: "" })) });
  };
  const setActive = (name) => { setActiveGw(name); save.mutate({ active_gateway: name }); };
  const saveCredits = () => save.mutate({
    rupiah_per_credit: Math.max(1, parseInt(cr.rupiah_per_credit, 10) || 1),
    bonus_percent: Math.max(0, Number(cr.bonus_percent) || 0),
    min_topup: Math.max(0, parseInt(cr.min_topup, 10) || 0),
    requests_per_credit: Math.max(1, parseInt(cr.requests_per_credit, 10) || 1),
  });
  const savePay = () => save.mutate({
    topup_enabled: pay.topup_enabled,
    topup_disabled_message: pay.topup_disabled_message,
  });

  return (
    <div className="max-w-3xl space-y-6" data-testid="payments-section">
      {/* ---- Active gateway selector ---- */}
      <Card className="p-6" data-testid="active-gateway-card">
        <div className="mb-4">
          <h3 className="font-display text-lg font-bold uppercase tracking-wide">Active Payment Gateway</h3>
          <p className="text-sm text-muted-foreground">Only one IDR gateway can be active at a time. Customer top-ups & partner charges use the active one.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            { key: "mayar", label: "Mayar", desc: "Hosted checkout (QRIS, e-wallet, VA)", ok: connected },
            { key: "klikqris", label: "KlikQRIS", desc: "Dynamic QRIS · 0% MDR", ok: kqConnected },
          ].map((g) => (
            <button
              key={g.key} type="button" onClick={() => setActive(g.key)} disabled={save.isPending}
              className={`flex items-start gap-3 rounded-[4px] border-2 p-4 text-left transition-colors ${activeGw === g.key ? "border-primary bg-primary/10" : "border-[hsl(var(--nb-border))] hover:border-primary/50"}`}
              data-testid={`gateway-select-${g.key}`}
            >
              <div className={`mt-0.5 flex h-9 w-9 items-center justify-center rounded-[4px] ${activeGw === g.key ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                {g.key === "klikqris" ? <QrCode className="h-5 w-5" /> : <Store className="h-5 w-5" />}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-display font-bold uppercase">{g.label}</span>
                  {activeGw === g.key && <Badge className="text-[10px]">Active</Badge>}
                </div>
                <p className="text-xs text-muted-foreground">{g.desc}</p>
                <p className={`mt-1 text-xs font-semibold ${g.ok ? "text-emerald-600" : "text-destructive"}`}>
                  {g.ok ? "Configured" : "Not set — add credentials below"}
                </p>
              </div>
            </button>
          ))}
        </div>
      </Card>

      {/* ---- Mayar gateway ---- */}
      <Card className="p-6">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[4px] border-[2.5px] border-[hsl(var(--nb-border))] bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--nb-shadow))]">
              <Store className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-display text-lg font-bold uppercase tracking-wide">Payment Gateway — Mayar</h3>
              <p className="text-sm text-muted-foreground">Credentials are stored in the database & override .env values</p>
            </div>
          </div>
          <Badge variant={connected ? "success" : "destructive"} data-testid="gw-status-badge">
            {connected ? "Configured" : "Not set"}
          </Badge>
        </div>

        <div className="mb-5 grid grid-cols-2 gap-3 rounded-[4px] border-2 border-[hsl(var(--nb-border))] bg-muted/40 p-3 text-sm sm:grid-cols-3">
          <div><p className="text-xs uppercase text-muted-foreground">API Key</p><p className="font-mono font-semibold" data-testid="gw-apikey-current">{gwStatus.api_key_masked || "—"}</p></div>
          <div><p className="text-xs uppercase text-muted-foreground">Webhook token</p><p className="font-semibold">{gwStatus.webhook_token_set ? "Set" : "Not set"}</p></div>
          <div><p className="text-xs uppercase text-muted-foreground">Source</p><p className="font-semibold uppercase">{gwStatus.source || "none"}</p></div>
        </div>

        <div className="space-y-4">
          <LabeledField label="New API Key" hint="Leave blank to keep the current key. Never shown again for security.">
            <Input type="password" placeholder="Paste Mayar API key…" autoComplete="off"
              value={gw.mayar_api_key} onChange={(e) => setGw((g) => ({ ...g, mayar_api_key: e.target.value }))}
              className="font-mono" data-testid="gw-apikey-input" />
          </LabeledField>
          <LabeledField label="New webhook token" hint="Used to verify Mayar callbacks. Leave blank to keep unchanged.">
            <Input type="password" placeholder="Paste webhook token…" autoComplete="off"
              value={gw.mayar_webhook_token} onChange={(e) => setGw((g) => ({ ...g, mayar_webhook_token: e.target.value }))}
              className="font-mono" data-testid="gw-webhook-input" />
          </LabeledField>
          <LabeledField label="Base URL" hint="Default: https://api.mayar.id/hl/v1">
            <Input placeholder="https://api.mayar.id/hl/v1"
              value={gw.mayar_base_url} onChange={(e) => setGw((g) => ({ ...g, mayar_base_url: e.target.value }))}
              className="font-mono" data-testid="gw-baseurl-input" />
          </LabeledField>

          <div className="rounded-[4px] border-2 border-dashed border-[hsl(var(--nb-border))] p-3 text-xs text-muted-foreground">
            <span className="font-semibold">Webhook URL for the Mayar dashboard:</span>{" "}
            <code className="font-mono">{`${window.location.origin.replace(/^http/, "https")}`}/api/wallet/mayar/webhook</code>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button onClick={saveGateway} disabled={save.isPending} className="gap-2" data-testid="gw-save-btn">
              <Save className="h-4 w-4" /> Save gateway
            </Button>
            <Button variant="outline" onClick={() => test.mutate("mayar")} disabled={test.isPending} className="gap-2" data-testid="gw-test-btn">
              {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Test connection
            </Button>
          </div>
        </div>
      </Card>

      {/* ---- KlikQRIS gateway ---- */}
      <Card className="p-6" data-testid="klikqris-card">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[4px] border-[2.5px] border-[hsl(var(--nb-border))] bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--nb-shadow))]">
              <QrCode className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-display text-lg font-bold uppercase tracking-wide">Payment Gateway — KlikQRIS</h3>
              <p className="text-sm text-muted-foreground">Dynamic QRIS (0% MDR). Credentials stored in the database & override .env values</p>
            </div>
          </div>
          <Badge variant={kqConnected ? "success" : "destructive"} data-testid="kq-status-badge">
            {kqConnected ? "Configured" : "Not set"}
          </Badge>
        </div>

        <div className="mb-5 grid grid-cols-2 gap-3 rounded-[4px] border-2 border-[hsl(var(--nb-border))] bg-muted/40 p-3 text-sm sm:grid-cols-3">
          <div><p className="text-xs uppercase text-muted-foreground">API Key</p><p className="font-mono font-semibold" data-testid="kq-apikey-current">{kqStatus.api_key_masked || "—"}</p></div>
          <div><p className="text-xs uppercase text-muted-foreground">Merchant ID</p><p className="font-semibold">{kqStatus.merchant_id_set ? "Set" : "Not set"}</p></div>
          <div><p className="text-xs uppercase text-muted-foreground">Source</p><p className="font-semibold uppercase">{kqStatus.source || "none"}</p></div>
        </div>

        <div className="space-y-4">
          <LabeledField label="New API Key (x-api-key)" hint="Leave blank to keep the current key. Never shown again for security.">
            <Input type="password" placeholder="Paste KlikQRIS API key…" autoComplete="off"
              value={kq.klikqris_api_key} onChange={(e) => setKq((k) => ({ ...k, klikqris_api_key: e.target.value }))}
              className="font-mono" data-testid="kq-apikey-input" />
          </LabeledField>
          <LabeledField label="Merchant ID (id_merchant)">
            <Input placeholder="e.g. 1786xxxxxxxx" autoComplete="off"
              value={kq.klikqris_merchant_id} onChange={(e) => setKq((k) => ({ ...k, klikqris_merchant_id: e.target.value }))}
              className="font-mono" data-testid="kq-merchant-input" />
          </LabeledField>
          <LabeledField label="Base URL" hint="Default: https://klikqris.com/api">
            <Input placeholder="https://klikqris.com/api"
              value={kq.klikqris_base_url} onChange={(e) => setKq((k) => ({ ...k, klikqris_base_url: e.target.value }))}
              className="font-mono" data-testid="kq-baseurl-input" />
          </LabeledField>

          <div className="rounded-[4px] border-2 border-dashed border-[hsl(var(--nb-border))] p-3 text-xs text-muted-foreground">
            <span className="font-semibold">Callback / Webhook URL for the KlikQRIS dashboard:</span>{" "}
            <code className="font-mono">{`${window.location.origin.replace(/^http/, "https")}`}/api/wallet/klikqris/webhook</code>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button onClick={saveKlik} disabled={save.isPending} className="gap-2" data-testid="kq-save-btn">
              <Save className="h-4 w-4" /> Save KlikQRIS
            </Button>
            <Button variant="outline" onClick={() => test.mutate("klikqris")} disabled={test.isPending} className="gap-2" data-testid="kq-test-btn">
              {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Test connection
            </Button>
          </div>
        </div>
      </Card>

      {/* ---- Credit conversion ---- */}
      <Card className="p-6">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[4px] border-[2.5px] border-[hsl(var(--nb-border))] bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--nb-shadow))]">
            <Coins className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-display text-lg font-bold uppercase tracking-wide">Credit Conversion</h3>
            <p className="text-sm text-muted-foreground">How many Rupiah equal 1 credit when a member tops up</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <LabeledField label="Rupiah / 1 credit">
            <Input type="number" min={1} step={100} value={cr.rupiah_per_credit}
              onChange={(e) => setCr((c) => ({ ...c, rupiah_per_credit: e.target.value }))}
              className="font-mono" data-testid="credit-rpc-input" />
          </LabeledField>
          <LabeledField label="Bonus (%)">
            <Input type="number" min={0} step={1} value={cr.bonus_percent}
              onChange={(e) => setCr((c) => ({ ...c, bonus_percent: e.target.value }))}
              className="font-mono" data-testid="credit-bonus-input" />
          </LabeledField>
          <LabeledField label="Min. top-up (Rp)">
            <Input type="number" min={0} step={1000} value={cr.min_topup}
              onChange={(e) => setCr((c) => ({ ...c, min_topup: e.target.value }))}
              className="font-mono" data-testid="credit-min-input" />
          </LabeledField>
          <LabeledField label="Requests / 1 credit" hint="Overflow when pass quota runs out">
            <Input type="number" min={1} step={1} value={cr.requests_per_credit}
              onChange={(e) => setCr((c) => ({ ...c, requests_per_credit: e.target.value }))}
              className="font-mono" data-testid="credit-rpcredit-input" />
          </LabeledField>
        </div>

        <div className="mt-4 rounded-[4px] border-2 border-[hsl(var(--nb-border))] bg-primary/10 p-3 text-sm" data-testid="credit-preview">
          <span className="font-semibold">Example:</span> Rp 100,000 ={" "}
          <span className="font-mono font-bold text-primary">{preview100.toLocaleString("en-US")} credits</span>
          {bonus > 0 && <span className="text-muted-foreground"> (incl. {bonus}% bonus)</span>}
          {" · "}Rp {rpc.toLocaleString("en-US")} = 1 credit
        </div>
        <p className="mt-2 text-xs text-muted-foreground" data-testid="credit-overflow-note">
          Overflow: when a pass request quota runs out, 1 credit is automatically spent for{" "}
          <span className="font-mono font-semibold">{Math.max(1, parseInt(cr.requests_per_credit, 10) || 1).toLocaleString("en-US")} extra requests</span>{" "}
          (≈Rp{Math.round(rpc / Math.max(1, parseInt(cr.requests_per_credit, 10) || 1)).toLocaleString("en-US")}/request).
        </p>

        <div className="mt-5">
          <Button onClick={saveCredits} disabled={save.isPending} className="gap-2" data-testid="credit-save-btn">
            <Save className="h-4 w-4" /> Save conversion
          </Button>
        </div>
      </Card>

      {/* ---- Top-up availability ---- */}
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[4px] border-[2.5px] border-[hsl(var(--nb-border))] bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--nb-shadow))]">
            <Power className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-display text-lg font-bold uppercase tracking-wide">Top-up availability</h3>
            <p className="text-sm text-muted-foreground">Turn off temporarily if the gateway is having issues</p>
          </div>
        </div>
        <div className="flex items-center justify-between rounded-[4px] border-2 border-[hsl(var(--nb-border))] p-3">
          <span className="font-display text-sm font-bold uppercase tracking-wide">Top-up enabled</span>
          <Switch checked={pay.topup_enabled} onCheckedChange={(v) => setPay((p) => ({ ...p, topup_enabled: v }))} data-testid="payment-topup-toggle" />
        </div>
        {!pay.topup_enabled && (
          <div className="mt-4">
            <LabeledField label="Message when top-up is disabled">
              <Input value={pay.topup_disabled_message}
                onChange={(e) => setPay((p) => ({ ...p, topup_disabled_message: e.target.value }))}
                placeholder="Payments are temporarily unavailable…" data-testid="payment-message-input" />
            </LabeledField>
          </div>
        )}
        <div className="mt-5">
          <Button onClick={savePay} disabled={save.isPending} className="gap-2" data-testid="payment-save-btn">
            <Save className="h-4 w-4" /> Save
          </Button>
        </div>
      </Card>
    </div>
  );
}

const SECTIONS = {
  overview: OverviewSection,
  payments: PaymentsSection,
  users: UsersSection,
  workspaces: WorkspacesSection,
  revenue: RevenueSection,
  wallets: WalletsSection,
  partners: PartnersSection,
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
