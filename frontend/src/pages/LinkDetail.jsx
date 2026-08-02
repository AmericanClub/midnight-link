import React, { useMemo, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Copy, ExternalLink, MousePointerClick, Users, ShieldAlert, Download, ShieldCheck } from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import DashboardLayout from "@/components/DashboardLayout";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import DateRangeFilter, { rangeToDates } from "@/components/DateRangeFilter";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import api, { shortUrl, BACKEND } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function Stat({ icon: Icon, label, value }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="font-display text-2xl font-bold">{value}</p>
        </div>
      </div>
    </Card>
  );
}

function Breakdown({ title, rows }) {
  const max = Math.max(1, ...(rows || []).map((r) => r.count));
  return (
    <Card className="p-6">
      <h2 className="mb-4 font-display font-semibold">{title}</h2>
      {(rows?.length ?? 0) === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No data yet.</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.name}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span>{r.name}</span>
                <span className="font-mono text-muted-foreground">{r.count}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${(r.count / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const PRESETS = [
  { v: "off", label: "Off", desc: "Log only — nothing blocked", color: "bg-slate-400" },
  { v: "moderate", label: "Moderate", desc: "Block bots + Tor", color: "bg-amber-500" },
  { v: "strict", label: "Strict", desc: "Bots, Tor, datacenter & proxy/VPN", color: "bg-red-500" },
];
const PRESET_VALUES = {
  off: { enabled: false },
  moderate: { enabled: true, block_bots: true, block_tor: true, block_datacenter: false, block_proxy_vpn: false, block_action: "fallback" },
  strict: { enabled: true, block_bots: true, block_tor: true, block_datacenter: true, block_proxy_vpn: true, block_action: "block_page" },
};

function ProtectionSettings({ linkId }) {
  const [p, setP] = useState(null);
  const { data } = useQuery({
    queryKey: ["link-protection", linkId],
    queryFn: async () => (await api.get(`/links/${linkId}/protection`)).data,
  });
  React.useEffect(() => { if (data) setP(data); }, [data]);

  const save = useMutation({
    mutationFn: async () => api.patch(`/links/${linkId}/protection`, p),
    onSuccess: () => toast.success("Protection settings saved"),
    onError: (err) => toast.error(err.response?.data?.detail || err.message),
  });

  if (!p) return null;
  // manual edits switch the preset to "custom"
  const set = (k, v) => setP((s) => ({ ...s, [k]: v, preset: "custom" }));
  const applyPreset = (name) => setP((s) => ({ ...s, ...PRESET_VALUES[name], preset: name }));
  const Toggle = ({ k, label, desc }) => (
    <div className="flex items-center justify-between rounded-lg border border-border p-3">
      <div><p className="text-sm font-medium">{label}</p>{desc && <p className="text-xs text-muted-foreground">{desc}</p>}</div>
      <Switch checked={!!p[k]} onCheckedChange={(v) => set(k, v)} data-testid={`prot-${k}`} />
    </div>
  );

  return (
    <Card className="mt-6 p-6" data-testid="link-protection-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-primary" /><h2 className="font-display font-semibold">Protection</h2></div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Enabled</span>
          <Switch checked={!!p.enabled} onCheckedChange={(v) => set("enabled", v)} data-testid="prot-enabled" />
        </div>
      </div>

      <div className="mb-5" data-testid="protection-presets">
        <div className="mb-2 flex items-center gap-2">
          <Label className="text-xs">Quick preset</Label>
          {p.preset === "custom" && <Badge variant="secondary" data-testid="preset-custom-badge">Custom</Badge>}
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {PRESETS.map((pr) => (
            <button
              type="button"
              key={pr.v}
              onClick={() => applyPreset(pr.v)}
              data-testid={`preset-${pr.v}`}
              className={`rounded-lg border p-3 text-left transition-colors ${p.preset === pr.v ? "border-primary bg-primary/5 ring-1 ring-primary" : "border-border hover:border-primary/40"}`}
            >
              <div className="flex items-center gap-2">
                <span className={`inline-block h-2 w-2 rounded-full ${pr.color}`} />
                <span className="text-sm font-semibold">{pr.label}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{pr.desc}</p>
            </button>
          ))}
        </div>
      </div>

      <div className={`grid gap-3 sm:grid-cols-2 ${p.enabled ? "" : "pointer-events-none opacity-50"}`}>
        <Toggle k="block_bots" label="Block bots" desc="Crawlers, automation, headless" />
        <Toggle k="block_tor" label="Block Tor" desc="Known Tor exit nodes" />
        <Toggle k="block_datacenter" label="Block datacenter IPs" desc="Cloud / hosting ranges" />
        <Toggle k="block_proxy_vpn" label="Block proxy / VPN" desc="Anonymizers" />
      </div>
      <div className={`mt-4 grid gap-4 sm:grid-cols-2 ${p.enabled ? "" : "pointer-events-none opacity-50"}`}>
        <div className="space-y-1.5">
          <Label className="text-xs">When blocked</Label>
          <Select value={p.block_action} onValueChange={(v) => set("block_action", v)}>
            <SelectTrigger data-testid="prot-action"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="fallback">Safe fallback URL</SelectItem>
              <SelectItem value="block_page">Show block page (403)</SelectItem>
              <SelectItem value="notfound">Return 404</SelectItem>
              <SelectItem value="redirect">Redirect to custom URL</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Block redirect URL (fallback/redirect)</Label>
          <Input value={p.block_redirect_url || ""} onChange={(e) => set("block_redirect_url", e.target.value)} placeholder="https://…" data-testid="prot-redirect-url" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Block countries (comma sep, e.g. RU,CN)</Label>
          <Input value={(p.block_countries || []).join(",")} onChange={(e) => set("block_countries", e.target.value.split(",").map((x) => x.trim()).filter(Boolean))} data-testid="prot-block-countries" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Rate limit / min per IP (0 = off)</Label>
          <Input type="number" value={p.rate_limit_per_min || 0} onChange={(e) => set("rate_limit_per_min", Number(e.target.value))} data-testid="prot-rate-limit" />
        </div>
      </div>
      <Button className="mt-5" onClick={() => save.mutate()} disabled={save.isPending} data-testid="prot-save-btn">
        {save.isPending ? "Saving…" : "Save protection"}
      </Button>
    </Card>
  );
}

export default function LinkDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { workspace } = useAuth();
  const [range, setRange] = useState("30d");
  const [compare, setCompare] = useState(false);
  const { start, end } = useMemo(() => rangeToDates(range), [range]);

  const linkQ = useQuery({
    queryKey: ["link", id],
    queryFn: async () => (await api.get(`/links/${id}`)).data,
  });
  const statsQ = useQuery({
    queryKey: ["link-analytics", id, workspace?.id, range, compare],
    queryFn: async () => (await api.get(`/analytics/links/${id}`, { params: { start, end, compare } })).data,
    refetchInterval: 15000,
  });

  const link = linkQ.data;
  const stats = statsQ.data;

  const exportCsv = () => {
    const qs = new URLSearchParams();
    if (start) qs.set("start", start);
    if (end) qs.set("end", end);
    window.open(`${BACKEND}/api/analytics/links/${id}/export.csv?${qs.toString()}`, "_blank");
  };

  const copy = () => {
    if (link) {
      navigator.clipboard.writeText(shortUrl(link.alias));
      toast.success("Short URL copied");
    }
  };

  return (
    <DashboardLayout>
      <Button variant="ghost" size="sm" className="mb-4 gap-2" onClick={() => navigate("/app/links")} data-testid="back-to-links-btn">
        <ArrowLeft className="h-4 w-4" /> Back to links
      </Button>

      {linkQ.isLoading ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : (
        <Card className="mb-6 p-6" data-testid="link-detail-header">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="font-display text-2xl font-bold tracking-tight">{link?.name}</h1>
                <Badge variant={link?.status === "active" ? "default" : "secondary"} className="capitalize">{link?.status}</Badge>
              </div>
              <button onClick={copy} className="mt-2 flex items-center gap-1.5 font-mono text-sm text-primary hover:underline">
                /api/r/{link?.alias} <Copy className="h-3 w-3" />
              </button>
              <p className="mt-1 truncate text-sm text-muted-foreground">→ {link?.destination_url}</p>
            </div>
            <Button asChild variant="outline" className="gap-2">
              <a href={link ? shortUrl(link.alias) : "#"} target="_blank" rel="noreferrer" data-testid="open-link-btn">
                Open <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </Card>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <DateRangeFilter value={range} onChange={setRange} compare={compare} onCompareChange={setCompare} />
        <Button variant="outline" className="gap-2" onClick={exportCsv} data-testid="export-csv-btn">
          <Download className="h-4 w-4" /> Export CSV
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat icon={MousePointerClick} label="Total clicks" value={stats?.total_clicks ?? 0} />
        <Stat icon={Users} label="Unique visitors" value={stats?.unique_visitors ?? 0} />
        <Stat icon={ShieldAlert} label="Bot traffic" value={stats?.bot_clicks ?? 0} />
      </div>

      <Card className="mt-6 p-6" data-testid="link-trend-card">
        <h2 className="mb-6 font-display font-semibold">Clicks over time</h2>
        {(stats?.timeseries?.length ?? 0) === 0 ? (
          <div className="flex h-56 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
            No clicks recorded yet. Open the short link to generate data.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={stats.timeseries} margin={{ left: -20, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="clk2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="clicks" stroke="hsl(var(--chart-1))" strokeWidth={2} fill="url(#clk2)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Breakdown title="Countries" rows={stats?.countries} />
        <Breakdown title="Devices" rows={stats?.devices} />
        <Breakdown title="Browsers" rows={stats?.browsers} />
        <Breakdown title="Referrers" rows={stats?.referrers} />
      </div>

      <Card className="mt-6 p-6" data-testid="recent-clicks-card">
        <h2 className="mb-4 font-display font-semibold">Recent clicks</h2>
        {(stats?.recent?.length ?? 0) === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No clicks yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Country</TableHead>
                <TableHead>Device</TableHead>
                <TableHead>Browser</TableHead>
                <TableHead>Type</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stats.recent.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{new Date(r.occurred_at).toLocaleString()}</TableCell>
                  <TableCell>{r.country}</TableCell>
                  <TableCell>{r.device}</TableCell>
                  <TableCell>{r.browser}</TableCell>
                  <TableCell>
                    <Badge variant={r.is_bot ? "secondary" : "default"}>{r.is_bot ? "Bot" : "Human"}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <ProtectionSettings linkId={id} />
    </DashboardLayout>
  );
}
