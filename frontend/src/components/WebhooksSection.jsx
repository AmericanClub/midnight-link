import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Webhook, Plus, Trash2, Copy, Send, RotateCw, ScrollText, Check, CheckCircle2, XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";

const EVENT_META = {
  "click.recorded": "Every click / scan",
  "click.blocked": "A visitor was blocked",
  "click.challenged": "A visitor was challenged",
};
const ALL_EVENTS = Object.keys(EVENT_META);

function SecretReveal({ secret, onDone }) {
  return (
    <div className="space-y-3" data-testid="webhook-secret-reveal">
      <Label>Signing secret</Label>
      <div className="flex items-center gap-2">
        <Input readOnly value={secret} className="font-mono text-xs" data-testid="webhook-secret-value" />
        <Button size="icon" variant="outline" onClick={() => { navigator.clipboard.writeText(secret); toast.success("Copied"); }} data-testid="copy-webhook-secret">
          <Copy className="h-4 w-4" />
        </Button>
      </div>
      <p className="text-xs text-amber-600 dark:text-amber-400">
        Copy it now — it won't be shown again. Use it to verify the <code>X-MidGate-Signature</code> header.
      </p>
      <Button className="w-full" onClick={onDone} data-testid="webhook-secret-done">Done</Button>
    </div>
  );
}

function CreateWebhookDialog({ open, onOpenChange, onCreated }) {
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState(ALL_EVENTS);
  const [loading, setLoading] = useState(false);
  const [created, setCreated] = useState(null);

  React.useEffect(() => {
    if (open) { setUrl(""); setDescription(""); setEvents(ALL_EVENTS); setCreated(null); }
  }, [open]);

  const toggleEvent = (e) =>
    setEvents((cur) => cur.includes(e) ? cur.filter((x) => x !== e) : [...cur, e]);

  const submit = async (ev) => {
    ev.preventDefault();
    if (events.length === 0) { toast.error("Select at least one event"); return; }
    setLoading(true);
    try {
      const { data } = await api.post("/webhooks", { url, description: description || null, events });
      setCreated(data);
      onCreated();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="create-webhook-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Add webhook endpoint</DialogTitle>
          <DialogDescription>We'll POST a signed JSON payload to your URL when subscribed events happen.</DialogDescription>
        </DialogHeader>
        {created ? (
          <SecretReveal secret={created.secret} onDone={() => onOpenChange(false)} />
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label>Endpoint URL</Label>
              <Input required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://api.yoursite.com/midgate/webhook" data-testid="webhook-url-input" />
            </div>
            <div className="space-y-2">
              <Label>Description <span className="text-muted-foreground">(optional)</span></Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Production ingest" data-testid="webhook-desc-input" />
            </div>
            <div className="space-y-2">
              <Label>Events</Label>
              <div className="space-y-2">
                {ALL_EVENTS.map((e) => (
                  <button
                    type="button"
                    key={e}
                    onClick={() => toggleEvent(e)}
                    data-testid={`webhook-event-${e}`}
                    className={`flex w-full items-center justify-between rounded-lg border p-3 text-left transition-colors ${events.includes(e) ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`}
                  >
                    <div>
                      <p className="font-mono text-sm">{e}</p>
                      <p className="text-xs text-muted-foreground">{EVENT_META[e]}</p>
                    </div>
                    {events.includes(e) && <Check className="h-4 w-4 text-primary" />}
                  </button>
                ))}
              </div>
            </div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="webhook-create-btn">
              {loading ? "Creating…" : "Create webhook"}
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DeliveriesDialog({ webhook, open, onOpenChange }) {
  const { data, isLoading } = useQuery({
    queryKey: ["webhook-deliveries", webhook?.id],
    queryFn: async () => (await api.get(`/webhooks/${webhook.id}/deliveries`)).data,
    enabled: !!webhook && open,
  });
  const items = data?.items || [];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="deliveries-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Recent deliveries</DialogTitle>
          <DialogDescription className="truncate">{webhook?.url}</DialogDescription>
        </DialogHeader>
        {isLoading ? <Skeleton className="h-32 w-full" /> : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No deliveries yet. Send a test event.</p>
        ) : (
          <ul className="max-h-80 space-y-2 overflow-y-auto">
            {items.map((d) => (
              <li key={d.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2" data-testid={`delivery-${d.id}`}>
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 text-sm font-medium">
                    {d.status === "success" ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <XCircle className="h-4 w-4 text-red-500" />}
                    <span className="font-mono">{d.event_type}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">{new Date(d.created_at).toLocaleString()} · {d.attempts} attempt(s){d.error ? ` · ${d.error}` : ""}</p>
                </div>
                <Badge variant={d.status === "success" ? "default" : "secondary"}>{d.status_code || d.status}</Badge>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function WebhooksSection() {
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const [deliveriesFor, setDeliveriesFor] = useState(null);
  const [rotated, setRotated] = useState(null);

  const { data, isLoading } = useQuery({ queryKey: ["webhooks"], queryFn: async () => (await api.get("/webhooks")).data });
  const refresh = () => qc.invalidateQueries({ queryKey: ["webhooks"] });

  const toggle = useMutation({
    mutationFn: async (w) => api.patch(`/webhooks/${w.id}`, { enabled: !w.enabled }),
    onSuccess: refresh,
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const del = useMutation({
    mutationFn: async (id) => api.delete(`/webhooks/${id}`),
    onSuccess: () => { toast.success("Webhook deleted"); refresh(); },
  });
  const test = useMutation({
    mutationFn: async (id) => (await api.post(`/webhooks/${id}/test`)).data,
    onSuccess: (res) => {
      const d = res.delivery;
      d.status === "success" ? toast.success(`Test delivered (HTTP ${d.status_code})`) : toast.error(`Test failed: ${d.error || "no response"}`);
      refresh();
    },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const rotate = useMutation({
    mutationFn: async (id) => (await api.post(`/webhooks/${id}/rotate-secret`)).data,
    onSuccess: (res) => setRotated(res.secret),
  });

  const items = data?.items || [];

  return (
    <Card className="mb-8 p-6" data-testid="webhooks-card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2"><Webhook className="h-4 w-4 text-primary" /><h2 className="font-display font-semibold">Webhooks</h2></div>
        <Button size="sm" onClick={() => setDialog(true)} className="gap-2" data-testid="new-webhook-btn"><Plus className="h-4 w-4" />Add endpoint</Button>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Get real-time events delivered to your server. Each request is signed with HMAC-SHA256 in the <code>X-MidGate-Signature</code> header.
      </p>

      {isLoading ? <Skeleton className="h-24 w-full" /> : items.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground" data-testid="webhooks-empty">No webhooks yet. Add an endpoint to start receiving events.</p>
      ) : (
        <ul className="space-y-3" data-testid="webhooks-list">
          {items.map((w) => (
            <li key={w.id} className="rounded-lg border border-border p-4" data-testid={`webhook-${w.id}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-sm">{w.url}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {w.events.map((e) => <Badge key={e} variant="secondary" className="font-mono text-[11px]">{e}</Badge>)}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {w.secret_prefix} · <span className="text-emerald-600">{w.success_count} ok</span> · <span className="text-red-500">{w.failure_count} failed</span>
                    {w.last_delivery_at ? ` · last ${new Date(w.last_delivery_at).toLocaleString()}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <Switch checked={w.enabled} onCheckedChange={() => toggle.mutate(w)} data-testid={`webhook-toggle-${w.id}`} />
                  <Button size="icon" variant="ghost" className="h-8 w-8" title="Send test event" onClick={() => test.mutate(w.id)} data-testid={`webhook-test-${w.id}`}><Send className="h-4 w-4" /></Button>
                  <Button size="icon" variant="ghost" className="h-8 w-8" title="View deliveries" onClick={() => setDeliveriesFor(w)} data-testid={`webhook-deliveries-${w.id}`}><ScrollText className="h-4 w-4" /></Button>
                  <Button size="icon" variant="ghost" className="h-8 w-8" title="Rotate secret" onClick={() => rotate.mutate(w.id)} data-testid={`webhook-rotate-${w.id}`}><RotateCw className="h-4 w-4" /></Button>
                  <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" title="Delete" onClick={() => del.mutate(w.id)} data-testid={`webhook-delete-${w.id}`}><Trash2 className="h-4 w-4" /></Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <CreateWebhookDialog open={dialog} onOpenChange={setDialog} onCreated={refresh} />
      <DeliveriesDialog webhook={deliveriesFor} open={!!deliveriesFor} onOpenChange={(v) => !v && setDeliveriesFor(null)} />

      <Dialog open={!!rotated} onOpenChange={(v) => !v && setRotated(null)}>
        <DialogContent data-testid="rotate-secret-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">New signing secret</DialogTitle>
            <DialogDescription>Update your endpoint to verify with this secret.</DialogDescription>
          </DialogHeader>
          {rotated && <SecretReveal secret={rotated} onDone={() => setRotated(null)} />}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
