import React from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Copy, ExternalLink, MousePointerClick, Users, ShieldAlert } from "lucide-react";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import api, { shortUrl } from "@/lib/api";
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

export default function LinkDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { workspace } = useAuth();

  const linkQ = useQuery({
    queryKey: ["link", id],
    queryFn: async () => (await api.get(`/links/${id}`)).data,
  });
  const statsQ = useQuery({
    queryKey: ["link-analytics", id, workspace?.id],
    queryFn: async () => (await api.get(`/analytics/links/${id}`)).data,
    refetchInterval: 15000,
  });

  const link = linkQ.data;
  const stats = statsQ.data;

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
    </DashboardLayout>
  );
}
