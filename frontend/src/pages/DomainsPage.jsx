import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Globe, Plus, Trash2, Copy, CheckCircle2, ShieldCheck, Star, Lock, RefreshCw,
} from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function DnsRow({ record }) {
  const copy = (v) => { navigator.clipboard.writeText(v); toast.success("Copied"); };
  return (
    <div className="grid grid-cols-[70px_1fr] items-center gap-2 rounded-md border border-border bg-muted/40 p-2 text-xs sm:grid-cols-[70px_1fr_1fr]">
      <Badge variant="outline" className="justify-center font-mono">{record.type}</Badge>
      <button onClick={() => copy(record.host)} className="flex items-center gap-1 truncate font-mono hover:text-primary" title="Copy host">
        <span className="truncate">{record.host}</span><Copy className="h-3 w-3 shrink-0" />
      </button>
      <button onClick={() => copy(record.value)} className="flex items-center gap-1 truncate font-mono hover:text-primary" title="Copy value">
        <span className="truncate">{record.value}</span><Copy className="h-3 w-3 shrink-0" />
      </button>
    </div>
  );
}

function AddDomainDialog({ open, onOpenChange, onAdded }) {
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);
  React.useEffect(() => { if (open) setDomain(""); }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/domains", { domain });
      toast.success("Domain added — add the DNS records to verify");
      onAdded();
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="add-domain-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Connect a domain</DialogTitle>
          <DialogDescription>Use your own domain for branded short links and QR codes.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label>Domain</Label>
            <Input required value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="go.yourbrand.com" className="font-mono" data-testid="domain-input" />
          </div>
          <Button type="submit" className="w-full" disabled={loading} data-testid="domain-add-btn">
            {loading ? "Adding…" : "Add domain"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DomainCard({ d, onChanged }) {
  const verify = useMutation({
    mutationFn: async () => (await api.post(`/domains/${d.id}/verify`)).data,
    onSuccess: (res) => {
      if (res.verified) { toast.success("Domain verified!"); onChanged(); }
      else toast.error(res.message || "TXT record not found yet");
    },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const primary = useMutation({
    mutationFn: async () => api.post(`/domains/${d.id}/primary`),
    onSuccess: () => { toast.success("Primary domain set"); onChanged(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const del = useMutation({
    mutationFn: async () => api.delete(`/domains/${d.id}`),
    onSuccess: () => { toast.success("Domain removed"); onChanged(); },
  });

  const verified = d.status === "verified";
  return (
    <Card className="p-5" data-testid={`domain-card-${d.domain}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-primary" />
            <p className="truncate font-display font-semibold">{d.domain}</p>
            {verified
              ? <Badge className="gap-1" data-testid={`domain-status-${d.domain}`}><CheckCircle2 className="h-3 w-3" />Verified</Badge>
              : <Badge variant="secondary" data-testid={`domain-status-${d.domain}`}>Pending</Badge>}
            {d.is_primary && <Badge variant="outline" className="gap-1"><Star className="h-3 w-3" />Primary</Badge>}
          </div>
          {verified && (
            <p className="mt-1.5 font-mono text-xs text-muted-foreground">
              Links resolve at <span className="text-foreground">https://{d.domain}/&lt;alias&gt;</span>
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {!verified && (
            <Button size="sm" variant="outline" className="gap-1.5" onClick={() => verify.mutate()} disabled={verify.isPending} data-testid={`domain-verify-${d.domain}`}>
              <RefreshCw className={`h-3.5 w-3.5 ${verify.isPending ? "animate-spin" : ""}`} />Verify
            </Button>
          )}
          {verified && !d.is_primary && (
            <Button size="sm" variant="outline" className="gap-1.5" onClick={() => primary.mutate()} disabled={primary.isPending} data-testid={`domain-primary-${d.domain}`}>
              <Star className="h-3.5 w-3.5" />Make primary
            </Button>
          )}
          <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => del.mutate()} data-testid={`domain-delete-${d.domain}`}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {!verified && (
        <div className="mt-4 space-y-2" data-testid={`domain-dns-${d.domain}`}>
          <p className="text-xs font-medium text-muted-foreground">Add these DNS records at your registrar, then click Verify:</p>
          <DnsRow record={d.instructions.txt} />
          <DnsRow record={d.instructions.cname} />
          <p className="text-[11px] text-muted-foreground">The TXT record proves ownership. The CNAME points traffic to MidGate's edge.</p>
        </div>
      )}
    </Card>
  );
}

export default function DomainsPage() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const isAdmin = ["owner", "admin"].includes(workspace?.role);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["domains", workspace?.id],
    queryFn: async () => (await api.get("/domains")).data,
    enabled: !!workspace && isAdmin,
    retry: false,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["domains"] });
  const items = data?.items || [];

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Custom Domains</h1>
          <p className="mt-1 text-sm text-muted-foreground">Serve short links and QR codes from your own branded domain.</p>
        </div>
        {isAdmin && (
          <Button onClick={() => setDialog(true)} className="gap-2" data-testid="new-domain-btn">
            <Plus className="h-4 w-4" /> Connect domain
          </Button>
        )}
      </div>

      {!isAdmin ? (
        <Card className="flex flex-col items-center gap-3 border-dashed py-16 text-center" data-testid="domains-restricted">
          <Lock className="h-8 w-8 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">Only workspace owners or admins can manage custom domains.</p>
        </Card>
      ) : isLoading ? (
        <div className="space-y-3">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}</div>
      ) : items.length === 0 ? (
        <Card className="flex flex-col items-center gap-4 border-dashed py-16 text-center" data-testid="domains-empty-state">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10"><ShieldCheck className="h-6 w-6 text-primary" /></div>
          <div>
            <h3 className="font-display font-semibold">No domains connected</h3>
            <p className="text-sm text-muted-foreground">Add a domain like <span className="font-mono">go.yourbrand.com</span> for branded links.</p>
          </div>
          <Button onClick={() => setDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> Connect domain</Button>
        </Card>
      ) : (
        <div className="space-y-3" data-testid="domains-list">
          {items.map((d) => <DomainCard key={d.id} d={d} onChanged={refresh} />)}
        </div>
      )}

      <AddDomainDialog open={dialog} onOpenChange={setDialog} onAdded={refresh} />
    </DashboardLayout>
  );
}
