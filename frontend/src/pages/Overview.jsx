import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  MousePointerClick, Users, ShieldAlert, Link2, TrendingUp, ArrowRight, ArrowUp, ArrowDown,
} from "lucide-react";
import {
  AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts";
import DashboardLayout from "@/components/DashboardLayout";
import DateRangeFilter, { rangeToDates } from "@/components/DateRangeFilter";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function Delta({ current, previous }) {
  if (previous == null) return null;
  const diff = current - previous;
  if (diff === 0) return <span className="text-xs text-muted-foreground" data-testid="stat-delta">no change</span>;
  const up = diff > 0;
  const pct = previous === 0 ? 100 : Math.round((diff / previous) * 100);
  return (
    <span className={`flex items-center gap-0.5 text-xs font-medium ${up ? "text-emerald-600" : "text-red-500"}`} data-testid="stat-delta">
      {up ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}{Math.abs(pct)}%
    </span>
  );
}

function StatCard({ icon: Icon, label, value, sub, prev, testid }) {
  return (
    <Card className="card-lift p-5" data-testid={testid}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-2 font-display text-3xl font-bold tracking-tight">{value}</p>
          <div className="mt-1 flex items-center gap-2">
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
            <Delta current={value} previous={prev} />
          </div>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
      </div>
    </Card>
  );
}

export default function Overview() {
  const { workspace } = useAuth();
  const [range, setRange] = useState("30d");
  const [compare, setCompare] = useState(false);
  const { start, end } = useMemo(() => rangeToDates(range), [range]);

  const { data, isLoading } = useQuery({
    queryKey: ["overview", workspace?.id, range, compare],
    queryFn: async () =>
      (await api.get("/analytics/overview", { params: { start, end, compare } })).data,
    enabled: !!workspace,
  });

  const prev = data?.previous;

  return (
    <DashboardLayout>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Overview</h1>
          <p className="mt-1 text-sm text-muted-foreground">Traffic and protection across your workspace.</p>
        </div>
        <div className="flex items-center gap-2">
          <DateRangeFilter value={range} onChange={setRange} compare={compare} onCompareChange={setCompare} />
          <Button asChild data-testid="overview-new-link-btn"><Link to="/app/links">New Link</Link></Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={MousePointerClick} label="Total clicks" value={data?.total_clicks ?? 0} prev={compare ? prev?.total_clicks : null} testid="stat-clicks" />
          <StatCard icon={Users} label="Unique visitors" value={data?.unique_visitors ?? 0} prev={compare ? prev?.unique_visitors : null} testid="stat-visitors" />
          <StatCard icon={ShieldAlert} label="Blocked" value={data?.blocked ?? 0} sub={`${data?.bot_clicks ?? 0} bots`} prev={compare ? prev?.blocked : null} testid="stat-blocked" />
          <StatCard icon={Link2} label="Active links" value={data?.active_links ?? 0} sub={`avg risk ${data?.avg_risk_score ?? 0}`} testid="stat-links" />
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2" data-testid="overview-trend-card">
          <div className="mb-6 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <h2 className="font-display font-semibold">Traffic trend</h2>
          </div>
          {isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (data?.timeseries?.length ?? 0) === 0 ? (
            <EmptyChart />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={data.timeseries} margin={{ left: -20, right: 8, top: 8 }}>
                <defs>
                  <linearGradient id="clk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="clicks" stroke="hsl(var(--chart-1))" strokeWidth={2} fill="url(#clk)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card className="p-6" data-testid="overview-top-links-card">
          <h2 className="mb-4 font-display font-semibold">Top links</h2>
          {(data?.top_links?.length ?? 0) === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No clicks yet.</p>
          ) : (
            <ul className="space-y-3">
              {data.top_links.map((l) => (
                <li key={l.alias} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{l.name}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">/{l.alias}</p>
                  </div>
                  <span className="shrink-0 font-mono text-sm font-semibold">{l.clicks}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <BreakdownCard title="Top countries" rows={data?.top_countries} testid="overview-countries-card" />
        <BreakdownCard title="Top devices" rows={data?.top_devices} testid="overview-devices-card" />
      </div>

      <Card className="mt-6 flex flex-col items-start gap-3 border-dashed p-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-display font-semibold">Create your first Smart Link</h3>
          <p className="text-sm text-muted-foreground">Short, branded and protected in seconds.</p>
        </div>
        <Button asChild variant="outline" className="gap-2">
          <Link to="/app/links">Go to Smart Links <ArrowRight className="h-4 w-4" /></Link>
        </Button>
      </Card>
    </DashboardLayout>
  );
}

function BreakdownCard({ title, rows, testid }) {
  const max = Math.max(1, ...(rows || []).map((r) => r.count));
  return (
    <Card className="p-6" data-testid={testid}>
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

function EmptyChart() {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border text-center">
      <TrendingUp className="h-8 w-8 text-muted-foreground/50" />
      <p className="text-sm text-muted-foreground">No traffic yet. Share a Smart Link to see data here.</p>
    </div>
  );
}
