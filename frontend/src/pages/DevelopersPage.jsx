import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2, Copy, KeyRound, Code2, Check } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import WebhooksSection from "@/components/WebhooksSection";
import WebhookDocs from "@/components/WebhookDocs";
import api, { formatApiError, BACKEND } from "@/lib/api";

const ENDPOINT = `${BACKEND}/api/v1/blocker`;

function CodeBlock({ code, id }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div className="relative">
      <Button size="sm" variant="ghost" className="absolute right-2 top-2 h-7 gap-1" onClick={copy} data-testid={`copy-code-${id}`}>
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </Button>
      <pre className="overflow-x-auto rounded-lg border border-border bg-muted/50 p-4 font-mono text-xs leading-relaxed"><code>{code}</code></pre>
    </div>
  );
}

const snippets = {
  curl: `curl "${ENDPOINT}?apikey=YOUR_API_KEY&ip=1.2.3.4&ua=Mozilla/5.0"`,
  php: `<?php
$apikey = "YOUR_API_KEY";
$ip  = $_SERVER['REMOTE_ADDR'];
$ua  = $_SERVER['HTTP_USER_AGENT'] ?? '';
$q   = http_build_query(["apikey"=>$apikey, "ip"=>$ip, "ua"=>$ua]);
$res = json_decode(file_get_contents("${ENDPOINT}?".$q), true);

if ($res["block"] === true) {
    http_response_code(403);
    exit("Access denied");
}
// ...continue serving the page`,
  js: `// Node.js / server-side (never call from the browser with your key)
const params = new URLSearchParams({
  apikey: process.env.MIDGATE_KEY,
  ip: req.ip,
  ua: req.headers["user-agent"] || "",
});
const r = await fetch("${ENDPOINT}?" + params);
const data = await r.json();
if (data.block) return res.status(403).send("Access denied");`,
  worker: `// Cloudflare Worker
export default {
  async fetch(request, env) {
    const ip = request.headers.get("CF-Connecting-IP");
    const ua = request.headers.get("User-Agent") || "";
    const q = new URLSearchParams({ apikey: env.MIDGATE_KEY, ip, ua });
    const res = await fetch("${ENDPOINT}?" + q).then(r => r.json());
    if (res.block) return new Response("Access denied", { status: 403 });
    return fetch(request);
  }
}`,
};

const RESPONSE_EXAMPLE = `{
  "block": true,
  "decision": "block",
  "risk_score": 80,
  "reasons": ["Datacenter / hosting IP"],
  "ip": "3.5.1.1",
  "is_bot": false,
  "is_tor": false,
  "is_datacenter": true,
  "is_proxy": true,
  "country": "Unknown"
}`;

function CreateKeyDialog({ open, onOpenChange, onCreated }) {
  const [name, setName] = useState("");
  const [created, setCreated] = useState(null);
  const [loading, setLoading] = useState(false);

  React.useEffect(() => { if (open) { setName(""); setCreated(null); } }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post("/apikeys", { name: name || "Default key" });
      setCreated(data);
      onCreated();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="create-key-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Create API key</DialogTitle>
          <DialogDescription>The secret is shown only once. Store it securely.</DialogDescription>
        </DialogHeader>
        {created ? (
          <div className="space-y-3">
            <Label>Your new API key</Label>
            <div className="flex items-center gap-2">
              <Input readOnly value={created.key} className="font-mono text-xs" data-testid="new-key-value" />
              <Button size="icon" variant="outline" onClick={() => { navigator.clipboard.writeText(created.key); toast.success("Copied"); }} data-testid="copy-new-key">
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-amber-600 dark:text-amber-400">Copy it now — you won't be able to see it again.</p>
            <Button className="w-full" onClick={() => onOpenChange(false)} data-testid="key-done-btn">Done</Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2"><Label>Key name</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Production site" data-testid="key-name-input" /></div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="key-create-btn">{loading ? "Creating…" : "Create key"}</Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function DevelopersPage() {
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["apikeys"], queryFn: async () => (await api.get("/apikeys")).data });
  const revoke = useMutation({
    mutationFn: async (id) => api.delete(`/apikeys/${id}`),
    onSuccess: () => { toast.success("Key revoked"); qc.invalidateQueries({ queryKey: ["apikeys"] }); },
  });
  const keys = data?.items || [];

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Developers</h1>
          <p className="mt-1 text-sm text-muted-foreground">API keys and the Blocker API to protect any site.</p>
        </div>
        <Button onClick={() => setDialog(true)} className="gap-2" data-testid="new-key-btn"><Plus className="h-4 w-4" />New API key</Button>
      </div>

      <Card className="mb-8 p-6" data-testid="apikeys-card">
        <div className="mb-4 flex items-center gap-2"><KeyRound className="h-4 w-4 text-primary" /><h2 className="font-display font-semibold">API keys</h2></div>
        {isLoading ? <Skeleton className="h-24 w-full" /> : keys.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No API keys yet.</p>
        ) : (
          <ul className="divide-y divide-border">
            {keys.map((k) => (
              <li key={k.id} className="flex items-center justify-between py-3" data-testid={`apikey-${k.id}`}>
                <div>
                  <p className="font-medium">{k.name} {k.revoked && <Badge variant="secondary">revoked</Badge>}</p>
                  <p className="font-mono text-xs text-muted-foreground">{k.prefix} · {k.request_count} requests · last used {k.last_used ? new Date(k.last_used).toLocaleString() : "never"}</p>
                </div>
                {!k.revoked && <Button variant="ghost" size="icon" className="text-destructive" onClick={() => revoke.mutate(k.id)} data-testid={`revoke-${k.id}`}><Trash2 className="h-4 w-4" /></Button>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <WebhooksSection />

      <WebhookDocs />

      <Card className="p-6" data-testid="blocker-docs-card">
        <div className="mb-4 flex items-center gap-2"><Code2 className="h-4 w-4 text-primary" /><h2 className="font-display font-semibold">Blocker API</h2></div>
        <p className="mb-3 text-sm text-muted-foreground">Send a visitor's IP + user-agent; get an allow/block decision. Call it server-side from any site.</p>
        <div className="mb-4">
          <Label className="text-xs">Endpoint</Label>
          <CodeBlock id="endpoint" code={`GET ${ENDPOINT}?apikey=YOUR_API_KEY&ip=1.2.3.4&ua=<user-agent>&url=<optional>&reff=<optional>`} />
        </div>

        <Tabs defaultValue="curl">
          <TabsList data-testid="snippet-tabs">
            <TabsTrigger value="curl" data-testid="snip-curl">cURL</TabsTrigger>
            <TabsTrigger value="php" data-testid="snip-php">PHP</TabsTrigger>
            <TabsTrigger value="js" data-testid="snip-js">Node.js</TabsTrigger>
            <TabsTrigger value="worker" data-testid="snip-worker">CF Worker</TabsTrigger>
          </TabsList>
          <TabsContent value="curl" className="mt-3"><CodeBlock id="curl" code={snippets.curl} /></TabsContent>
          <TabsContent value="php" className="mt-3"><CodeBlock id="php" code={snippets.php} /></TabsContent>
          <TabsContent value="js" className="mt-3"><CodeBlock id="js" code={snippets.js} /></TabsContent>
          <TabsContent value="worker" className="mt-3"><CodeBlock id="worker" code={snippets.worker} /></TabsContent>
        </Tabs>

        <div className="mt-4">
          <Label className="text-xs">Example response</Label>
          <CodeBlock id="response" code={RESPONSE_EXAMPLE} />
        </div>
      </Card>

      <CreateKeyDialog open={dialog} onOpenChange={setDialog} onCreated={() => qc.invalidateQueries({ queryKey: ["apikeys"] })} />
    </DashboardLayout>
  );
}
