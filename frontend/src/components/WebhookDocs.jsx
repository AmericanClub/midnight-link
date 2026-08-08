import React, { useState } from "react";
import { toast } from "sonner";
import { BookOpen, Copy, Check } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const EVENTS = [
  { name: "click.recorded", desc: "Fires on every click / QR scan" },
  { name: "click.blocked", desc: "A visitor was blocked by protection rules" },
  { name: "click.challenged", desc: "A visitor was challenged" },
  { name: "ping", desc: "Sent when you click “Test” on a webhook" },
];

const PAYLOAD = `{
  "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
  "type": "click.blocked",
  "created_at": "2026-08-02T17:30:00.000000+00:00",
  "data": {
    "alias": "summer-sale",
    "link_id": "a0995339-b8b5-4ef9-8e0b-bc9f743d4f96",
    "event_type": "click",
    "country": "ID",
    "device": "desktop",
    "browser": "Chrome",
    "os": "Windows",
    "referrer": "Direct",
    "is_bot": true,
    "bot_category": "datacenter",
    "risk_score": 82,
    "decision": "block",
    "risk_reasons": ["Datacenter IP", "Bot user-agent"],
    "occurred_at": "2026-08-02T17:30:00.000000+00:00"
  }
}`;

const NODE = `const crypto = require("crypto");
const express = require("express");
const app = express();

// Verify the HMAC-SHA256 signature over "\${timestamp}.\${rawBody}".
function verifyMidgate(rawBody, header, secret) {
  const parts = Object.fromEntries(
    header.split(",").map((p) => p.split("="))
  ); // { t, v1 }
  const expected = crypto
    .createHmac("sha256", secret)
    .update(parts.t + "." + rawBody)
    .digest("hex");
  return crypto.timingSafeEqual(
    Buffer.from(expected), Buffer.from(parts.v1 || "")
  );
}

// IMPORTANT: use the RAW body, not the parsed JSON.
app.post("/webhook", express.raw({ type: "application/json" }), (req, res) => {
  const ok = verifyMidgate(
    req.body.toString(),
    req.get("X-MidnightLink-Signature"),
    process.env.MIDGATE_SECRET
  );
  if (!ok) return res.status(400).send("bad signature");

  const event = JSON.parse(req.body.toString());
  console.log(event.type, event.data);
  res.sendStatus(200); // acknowledge with 2xx
});`;

const PHP = `<?php
$secret = getenv('MIDGATE_SECRET');
$raw    = file_get_contents('php://input');           // raw body
$header = $_SERVER['HTTP_X_MIDGATE_SIGNATURE'] ?? '';  // "t=..,v1=.."

parse_str(str_replace(',', '&', $header), $parts);     // -> $parts['t'], $parts['v1']
$expected = hash_hmac('sha256', $parts['t'] . '.' . $raw, $secret);

if (!hash_equals($expected, $parts['v1'] ?? '')) {
    http_response_code(400);
    exit('bad signature');
}

$event = json_decode($raw, true);
// handle $event['type'] and $event['data']
http_response_code(200); // acknowledge with 2xx`;

function CodeBlock({ code, testid }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    toast.success("Copied");
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="relative">
      <Button size="icon" variant="ghost" className="absolute right-2 top-2 h-7 w-7" onClick={copy} data-testid={`copy-${testid}`}>
        {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
      </Button>
      <pre className="overflow-x-auto rounded-lg border border-border bg-muted/50 p-4 text-xs leading-relaxed" data-testid={testid}>
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function WebhookDocs() {
  return (
    <Card className="mb-8 p-6" data-testid="webhook-docs-card">
      <div className="mb-4 flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-primary" />
        <h2 className="font-display font-semibold">Webhook docs</h2>
      </div>

      <div className="mb-5">
        <p className="mb-2 text-sm font-medium">Events</p>
        <ul className="space-y-1.5">
          {EVENTS.map((e) => (
            <li key={e.name} className="flex items-center gap-2 text-sm">
              <Badge variant="secondary" className="font-mono text-[11px]">{e.name}</Badge>
              <span className="text-muted-foreground">{e.desc}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mb-5">
        <p className="mb-2 text-sm font-medium">Headers on every request</p>
        <ul className="space-y-1 font-mono text-xs text-muted-foreground">
          <li><span className="text-foreground">X-MidnightLink-Event</span> — the event type</li>
          <li><span className="text-foreground">X-MidnightLink-Delivery</span> — unique delivery id</li>
          <li><span className="text-foreground">X-MidnightLink-Signature</span> — <span className="text-foreground">t=&lt;unix_ts&gt;,v1=&lt;hmac_sha256&gt;</span></li>
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">
          Signature = HMAC-SHA256 of <code className="text-foreground">{"`${t}.${rawBody}`"}</code> using your webhook's signing secret.
          Respond with any <span className="text-foreground">2xx</span> to acknowledge; otherwise we retry 3× (immediately, +2s, +5s).
        </p>
      </div>

      <Tabs defaultValue="payload">
        <TabsList data-testid="webhook-docs-tabs">
          <TabsTrigger value="payload" data-testid="docs-tab-payload">Example payload</TabsTrigger>
          <TabsTrigger value="node" data-testid="docs-tab-node">Verify · Node.js</TabsTrigger>
          <TabsTrigger value="php" data-testid="docs-tab-php">Verify · PHP</TabsTrigger>
        </TabsList>
        <TabsContent value="payload" className="mt-3"><CodeBlock code={PAYLOAD} testid="docs-payload" /></TabsContent>
        <TabsContent value="node" className="mt-3"><CodeBlock code={NODE} testid="docs-node" /></TabsContent>
        <TabsContent value="php" className="mt-3"><CodeBlock code={PHP} testid="docs-php" /></TabsContent>
      </Tabs>
    </Card>
  );
}
