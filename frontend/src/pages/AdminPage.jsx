import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Users, Building2, ShieldAlert, Activity, RefreshCw, Plus, Trash2, Globe2, KeyRound, LifeBuoy, Send } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TicketMessages, STATUS_VARIANT, PRIORITIES } from "@/components/TicketThread";
import api, { formatApiError } from "@/lib/api";

function Stat({ icon: Icon, label, value }) {
  return (
    <Card className="p-5" data-testid={`admin-stat-${label.toLowerCase().replace(/\W+/g, "-")}`}>
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10"><Icon className="h-5 w-5 text-primary" /></div>
        <div><p className="text-sm text-muted-foreground">{label}</p><p className="font-display text-2xl font-bold">{value}</p></div>
      </div>
    </Card>
  );
}

function Overview() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-overview"], queryFn: async () => (await api.get("/admin/overview")).data });
  const refresh = useMutation({
    mutationFn: async () => api.post("/admin/feeds/refresh"),
    onSuccess: () => { toast.success("Threat feeds refreshed"); qc.invalidateQueries({ queryKey: ["admin-overview"] }); },
  });
  if (isLoading) return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={Users} label="Users" value={data.users} />
        <Stat icon={Building2} label="Workspaces" value={data.workspaces} />
        <Stat icon={Activity} label="Events" value={data.events} />
        <Stat icon={ShieldAlert} label="Blocked" value={data.blocked} />
        <Stat icon={ShieldAlert} label="Challenged" value={data.challenged} />
        <Stat icon={KeyRound} label="API keys" value={data.api_keys} />
        <Stat icon={Activity} label="API checks" value={data.api_checks} />
        <Stat icon={Building2} label="Paid invoices" value={data.paid_invoices} />
      </div>
      <Card className="flex flex-wrap items-center justify-between gap-3 p-6" data-testid="admin-feeds-card">
        <div>
          <h3 className="font-display font-semibold">Threat intelligence feeds</h3>
          <p className="text-sm text-muted-foreground">
            {data.feeds.tor_count} Tor exit nodes · {data.feeds.datacenter_ranges} datacenter ranges ·
            last refresh {data.feeds.last_refresh ? new Date(data.feeds.last_refresh).toLocaleString() : "—"}
          </p>
        </div>
        <Button onClick={() => refresh.mutate()} disabled={refresh.isPending} className="gap-2" data-testid="admin-refresh-feeds-btn">
          <RefreshCw className={`h-4 w-4 ${refresh.isPending ? "animate-spin" : ""}`} />Refresh feeds
        </Button>
      </Card>
    </div>
  );
}

function SecurityEvents() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-events"], queryFn: async () => (await api.get("/admin/security-events")).data });
  if (isLoading) return <Skeleton className="h-64 w-full rounded-xl" />;
  const rows = data?.items || [];
  return (
    <Card className="p-6" data-testid="admin-events-card">
      <h3 className="mb-4 font-display font-semibold">Security events <span className="text-sm font-normal text-muted-foreground">({data?.total ?? 0})</span></h3>
      {rows.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">No blocked or challenged events yet.</p> : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Decision</TableHead><TableHead>Risk</TableHead><TableHead>Country</TableHead><TableHead>Source</TableHead><TableHead>Reasons</TableHead></TableRow></TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="whitespace-nowrap font-mono text-xs">{new Date(r.occurred_at).toLocaleString()}</TableCell>
                  <TableCell><Badge variant={r.decision === "block" ? "destructive" : "secondary"} className="capitalize">{r.decision}</Badge></TableCell>
                  <TableCell className="font-mono">{r.risk_score}</TableCell>
                  <TableCell>{r.country}</TableCell>
                  <TableCell><Badge variant="outline">{r.source || "redirect"}</Badge></TableCell>
                  <TableCell className="max-w-xs truncate text-xs text-muted-foreground">{(r.risk_reasons || []).join(", ")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </Card>
  );
}

function SimpleList({ queryKey, url, columns, render, testid }) {
  const { data, isLoading } = useQuery({ queryKey: [queryKey], queryFn: async () => (await api.get(url)).data });
  if (isLoading) return <Skeleton className="h-64 w-full rounded-xl" />;
  const rows = data?.items || [];
  return (
    <Card className="p-6" data-testid={testid}>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader><TableRow>{columns.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow></TableHeader>
          <TableBody>{rows.map(render)}</TableBody>
        </Table>
      </div>
      {rows.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No data.</p>}
    </Card>
  );
}

function GlobalBlocklist() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ value: "", note: "" });
  const { data, isLoading } = useQuery({ queryKey: ["admin-global"], queryFn: async () => (await api.get("/admin/global-blocklist")).data });
  const add = useMutation({
    mutationFn: async () => api.post("/admin/global-blocklist", form),
    onSuccess: () => { toast.success("Added to global blocklist"); setForm({ value: "", note: "" }); qc.invalidateQueries({ queryKey: ["admin-global"] }); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const del = useMutation({ mutationFn: async (id) => api.delete(`/admin/global-blocklist/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-global"] }) });
  const rows = data?.items || [];
  return (
    <Card className="p-6" data-testid="admin-global-card">
      <div className="mb-4 flex items-center gap-2"><Globe2 className="h-4 w-4 text-primary" /><h3 className="font-display font-semibold">Global IP blocklist</h3></div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex-1 space-y-1.5"><label className="text-xs">IP or CIDR</label><Input value={form.value} onChange={(e) => setForm((s) => ({ ...s, value: e.target.value }))} className="font-mono" placeholder="9.9.9.0/24" data-testid="global-value-input" /></div>
        <div className="flex-1 space-y-1.5"><label className="text-xs">Note</label><Input value={form.note} onChange={(e) => setForm((s) => ({ ...s, note: e.target.value }))} data-testid="global-note-input" /></div>
        <Button onClick={() => add.mutate()} disabled={!form.value} className="gap-2" data-testid="global-add-btn"><Plus className="h-4 w-4" />Add</Button>
      </div>
      {isLoading ? <Skeleton className="h-24 w-full" /> : rows.length === 0 ? <p className="py-4 text-center text-sm text-muted-foreground">Empty.</p> : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2" data-testid={`global-${r.value}`}>
              <div><span className="font-mono text-sm">{r.value}</span>{r.note && <span className="ml-2 text-xs text-muted-foreground">{r.note}</span>}</div>
              <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => del.mutate(r.id)}><Trash2 className="h-4 w-4" /></Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const STATUS_FILTERS = ["all", "open", "pending", "resolved", "closed"];

function AdminTicketPanel({ ticketId, onChanged }) {
  const qc = useQueryClient();
  const [reply, setReply] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["admin-ticket", ticketId],
    queryFn: async () => (await api.get(`/support/admin/tickets/${ticketId}`)).data,
    enabled: !!ticketId,
  });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-ticket", ticketId] });
    qc.invalidateQueries({ queryKey: ["admin-tickets"] });
    onChanged?.();
  };
  const send = useMutation({
    mutationFn: async () => api.post(`/support/admin/tickets/${ticketId}/reply`, { body: reply }),
    onSuccess: () => { setReply(""); toast.success("Reply sent"); invalidate(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const update = useMutation({
    mutationFn: async (patch) => api.patch(`/support/admin/tickets/${ticketId}`, patch),
    onSuccess: () => { toast.success("Ticket updated"); invalidate(); },
  });

  if (isLoading || !data) return <Skeleton className="h-[520px] w-full rounded-xl" />;
  return (
    <Card className="flex h-[520px] flex-col p-5" data-testid="admin-ticket-thread">
      <div className="mb-3 border-b border-border pb-3">
        <p className="truncate font-display font-semibold">{data.subject}</p>
        <p className="text-xs text-muted-foreground">
          {data.requester_name} · <span className="font-mono">{data.requester_email}</span> {data.is_public ? "· (public)" : ""}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Select value={data.status} onValueChange={(v) => update.mutate({ status: v })}>
            <SelectTrigger className="h-8 w-[130px]" data-testid="admin-ticket-status"><SelectValue /></SelectTrigger>
            <SelectContent>{STATUS_FILTERS.filter((s) => s !== "all").map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={data.priority} onValueChange={(v) => update.mutate({ priority: v })}>
            <SelectTrigger className="h-8 w-[120px]" data-testid="admin-ticket-priority"><SelectValue /></SelectTrigger>
            <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p.v} value={p.v}>{p.label}</SelectItem>)}</SelectContent>
          </Select>
          <Badge variant="outline" className="capitalize">{data.category}</Badge>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto pr-1">
        <TicketMessages messages={data.messages} mySide="admin" />
      </div>
      <div className="mt-3 flex items-end gap-2 border-t border-border pt-3">
        <Textarea rows={2} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Reply to customer…" className="resize-none" data-testid="admin-reply-input" />
        <Button size="icon" onClick={() => reply.trim() && send.mutate()} disabled={send.isPending || !reply.trim()} data-testid="admin-reply-send"><Send className="h-4 w-4" /></Button>
      </div>
    </Card>
  );
}

function SupportTickets() {
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["admin-tickets", filter],
    queryFn: async () => (await api.get("/support/admin/tickets", { params: filter === "all" ? {} : { status: filter } })).data,
  });
  const items = data?.items || [];

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Select value={filter} onValueChange={(v) => { setFilter(v); setSelected(null); }}>
            <SelectTrigger className="h-9 w-[150px]" data-testid="ticket-filter-select"><SelectValue /></SelectTrigger>
            <SelectContent>{STATUS_FILTERS.map((s) => <SelectItem key={s} value={s} className="capitalize">{s === "all" ? "All tickets" : s}</SelectItem>)}</SelectContent>
          </Select>
          <Badge variant="secondary" data-testid="tickets-open-count">{data?.open_count ?? 0} open</Badge>
        </div>
        <div className="space-y-2" data-testid="admin-tickets-list">
          {isLoading ? [...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
            : items.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">No tickets.</p>
            : items.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelected(t.id)}
                data-testid={`admin-ticket-item-${t.id}`}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${selected === t.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate font-medium">{t.subject}</p>
                  <Badge variant={STATUS_VARIANT[t.status]} className="shrink-0 capitalize">{t.status}</Badge>
                </div>
                <p className="mt-1 truncate text-xs text-muted-foreground">{t.requester_email} · {t.category} · {t.priority}</p>
              </button>
            ))}
        </div>
      </div>
      <div>
        {selected ? <AdminTicketPanel ticketId={selected} />
          : <Card className="flex h-[520px] flex-col items-center justify-center gap-3 border-dashed text-center" data-testid="admin-no-ticket"><LifeBuoy className="h-10 w-10 text-muted-foreground/30" /><p className="text-sm text-muted-foreground">Select a ticket to view & reply.</p></Card>}
      </div>
    </div>
  );
}

export default function AdminPage() {
  return (
    <DashboardLayout>
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold tracking-tight">Admin</h1>
        <p className="mt-1 text-sm text-muted-foreground">Platform monitoring and controls.</p>
      </div>
      <Tabs defaultValue="overview">
        <TabsList data-testid="admin-tabs" className="flex-wrap">
          <TabsTrigger value="overview" data-testid="admin-tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="events" data-testid="admin-tab-events">Security Events</TabsTrigger>
          <TabsTrigger value="users" data-testid="admin-tab-users">Users</TabsTrigger>
          <TabsTrigger value="workspaces" data-testid="admin-tab-workspaces">Workspaces</TabsTrigger>
          <TabsTrigger value="global" data-testid="admin-tab-global">Global Blocklist</TabsTrigger>
          <TabsTrigger value="api" data-testid="admin-tab-api">API Usage</TabsTrigger>
          <TabsTrigger value="tickets" data-testid="admin-tab-tickets">Support Tickets</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="mt-4"><Overview /></TabsContent>
        <TabsContent value="events" className="mt-4"><SecurityEvents /></TabsContent>
        <TabsContent value="users" className="mt-4">
          <SimpleList queryKey="admin-users" url="/admin/users" testid="admin-users-card"
            columns={["Name", "Email", "Role", "Joined"]}
            render={(u) => (
              <TableRow key={u.id}>
                <TableCell>{u.name}</TableCell><TableCell className="font-mono text-xs">{u.email}</TableCell>
                <TableCell><Badge variant={u.role === "admin" ? "default" : "secondary"}>{u.role}</Badge></TableCell>
                <TableCell className="text-xs text-muted-foreground">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</TableCell>
              </TableRow>
            )} />
        </TabsContent>
        <TabsContent value="workspaces" className="mt-4">
          <SimpleList queryKey="admin-workspaces" url="/admin/workspaces" testid="admin-workspaces-card"
            columns={["Workspace", "Plan", "Links", "Members"]}
            render={(w) => (
              <TableRow key={w.id}>
                <TableCell>{w.name}</TableCell><TableCell><Badge className="capitalize">{w.plan}</Badge></TableCell>
                <TableCell className="font-mono">{w.link_count}</TableCell><TableCell className="font-mono">{w.member_count}</TableCell>
              </TableRow>
            )} />
        </TabsContent>
        <TabsContent value="global" className="mt-4"><GlobalBlocklist /></TabsContent>
        <TabsContent value="api" className="mt-4">
          <SimpleList queryKey="admin-api" url="/admin/api-usage" testid="admin-api-card"
            columns={["Key", "Prefix", "Requests", "Last used"]}
            render={(k) => (
              <TableRow key={k.id}>
                <TableCell>{k.name}</TableCell><TableCell className="font-mono text-xs">{k.prefix}</TableCell>
                <TableCell className="font-mono">{k.request_count}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{k.last_used ? new Date(k.last_used).toLocaleString() : "never"}</TableCell>
              </TableRow>
            )} />
        </TabsContent>
        <TabsContent value="tickets" className="mt-4"><SupportTickets /></TabsContent>
      </Tabs>
    </DashboardLayout>
  );
}
