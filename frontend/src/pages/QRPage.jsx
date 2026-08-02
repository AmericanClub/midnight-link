import React, { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus, Copy, Pause, Play, Trash2, Download, Pencil, BarChart3, QrCode as QrIcon, MoreVertical,
} from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import QRPreview from "@/components/QRPreview";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import api, { formatApiError, shortUrl, BACKEND } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const DOTS = ["square", "rounded", "dots", "classy", "classy-rounded", "extra-rounded"];
const CORNERS = ["square", "dot", "extra-rounded"];
const ECC = ["L", "M", "Q", "H"];

function StyleControls({ style, setStyle }) {
  const set = (k) => (v) => setStyle((s) => ({ ...s, [k]: v }));
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Foreground</Label>
        <input type="color" value={style.fg_color} onChange={(e) => set("fg_color")(e.target.value)}
          className="h-9 w-full cursor-pointer rounded-md border border-border bg-transparent" data-testid="qr-fg-color" />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Background</Label>
        <input type="color" value={style.bg_color} onChange={(e) => set("bg_color")(e.target.value)}
          className="h-9 w-full cursor-pointer rounded-md border border-border bg-transparent" data-testid="qr-bg-color" />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Dot style</Label>
        <Select value={style.dots_style} onValueChange={set("dots_style")}>
          <SelectTrigger data-testid="qr-dots-style"><SelectValue /></SelectTrigger>
          <SelectContent>{DOTS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Corner style</Label>
        <Select value={style.corners_style} onValueChange={set("corners_style")}>
          <SelectTrigger data-testid="qr-corners-style"><SelectValue /></SelectTrigger>
          <SelectContent>{CORNERS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Error correction</Label>
        <Select value={style.error_correction} onValueChange={set("error_correction")}>
          <SelectTrigger data-testid="qr-ecc"><SelectValue /></SelectTrigger>
          <SelectContent>{ECC.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Margin</Label>
        <Input type="number" min={0} max={40} value={style.margin}
          onChange={(e) => set("margin")(Number(e.target.value))} data-testid="qr-margin" />
      </div>
      <div className="col-span-2 space-y-1.5">
        <Label className="text-xs">Logo URL (optional)</Label>
        <Input value={style.logo_url} onChange={(e) => set("logo_url")(e.target.value)}
          placeholder="https://…/logo.png" data-testid="qr-logo-url" />
      </div>
    </div>
  );
}

const DEFAULT_STYLE = {
  fg_color: "#4338CA", bg_color: "#FFFFFF", dots_style: "rounded",
  corners_style: "extra-rounded", error_correction: "M", margin: 8, logo_url: "",
};

function QRDialog({ open, onOpenChange, onSaved, existing }) {
  const editing = !!existing;
  const [form, setForm] = useState({ name: "", destination_url: "", alias: "", protection_preset: "off" });
  const [style, setStyle] = useState(DEFAULT_STYLE);
  const [loading, setLoading] = useState(false);
  const previewRef = useRef(null);

  React.useEffect(() => {
    if (open) {
      if (existing) {
        setForm({ name: existing.name, destination_url: existing.destination_url, alias: existing.alias, protection_preset: "off" });
        setStyle({ ...DEFAULT_STYLE, ...existing.style });
      } else {
        setForm({ name: "", destination_url: "", alias: "", protection_preset: "off" });
        setStyle(DEFAULT_STYLE);
      }
    }
  }, [open, existing]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (editing) {
        await api.patch(`/qr/${existing.id}`, { name: form.name, destination_url: form.destination_url, style });
        toast.success("QR updated — same code, new destination");
      } else {
        const payload = { name: form.name, destination_url: form.destination_url, style, protection_preset: form.protection_preset };
        if (form.alias.trim()) payload.alias = form.alias.trim();
        await api.post("/qr", payload);
        toast.success("Dynamic QR created");
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const previewValue = editing ? `${BACKEND}${existing.short_path}` : (form.destination_url || "https://midgate.io");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" data-testid="qr-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{editing ? "Edit Dynamic QR" : "New Dynamic QR"}</DialogTitle>
          <DialogDescription>
            The QR encodes a MidGate short URL, so you can change the destination anytime without reprinting.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-6 md:grid-cols-[1fr_auto]">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="qr-name-input" placeholder="Restaurant menu" />
            </div>
            <div className="space-y-2">
              <Label>Destination URL</Label>
              <Input required value={form.destination_url} onChange={(e) => setForm((f) => ({ ...f, destination_url: e.target.value }))} data-testid="qr-destination-input" placeholder="https://example.com/menu" />
            </div>
            {!editing && (
              <div className="space-y-2">
                <Label>Custom alias <span className="text-muted-foreground">(optional)</span></Label>
                <Input value={form.alias} onChange={(e) => setForm((f) => ({ ...f, alias: e.target.value }))} data-testid="qr-alias-input" className="font-mono" placeholder="menu24" />
              </div>
            )}
            {!editing && (
              <div className="space-y-2">
                <Label>Protection preset</Label>
                <Select value={form.protection_preset} onValueChange={(v) => setForm((f) => ({ ...f, protection_preset: v }))}>
                  <SelectTrigger data-testid="qr-preset-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="off" data-testid="qr-preset-off">Off — log only, nothing blocked</SelectItem>
                    <SelectItem value="moderate" data-testid="qr-preset-moderate">Moderate — block bots + Tor</SelectItem>
                    <SelectItem value="strict" data-testid="qr-preset-strict">Strict — block bots, Tor, datacenter & proxy/VPN</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">One-click security. Fine-tune later from the QR's Stats page.</p>
              </div>
            )}
            <StyleControls style={style} setStyle={setStyle} />
          </div>
          <div className="flex flex-col items-center gap-3">
            <QRPreview ref={previewRef} value={previewValue} style={style} size={200} />
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => previewRef.current?.download("png")} data-testid="qr-download-png"><Download className="mr-1 h-4 w-4" />PNG</Button>
              <Button type="button" variant="outline" size="sm" onClick={() => previewRef.current?.download("svg")} data-testid="qr-download-svg"><Download className="mr-1 h-4 w-4" />SVG</Button>
            </div>
          </div>
          <DialogFooter className="md:col-span-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={loading} data-testid="qr-save-btn">
              {loading ? "Saving…" : editing ? "Save changes" : "Create QR"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function QRCard({ qr, onEdit, onAction, primaryDomain }) {
  const navigate = useNavigate();
  const ref = useRef(null);
  const value = `${BACKEND}${qr.short_path}`;
  const display = primaryDomain ? `${primaryDomain}/${qr.alias}` : `/api/r/${qr.alias}`;
  const copy = () => {
    navigator.clipboard.writeText(primaryDomain ? `https://${primaryDomain}/${qr.alias}` : value);
    toast.success(primaryDomain ? "Branded URL copied" : "Short URL copied");
  };
  return (
    <Card className="card-lift p-5" data-testid={`qr-card-${qr.alias}`}>
      <div className="flex gap-4">
        <QRPreview ref={ref} value={value} style={qr.style} size={110} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate font-semibold">{qr.name}</p>
            <Badge variant={qr.status === "active" ? "default" : "secondary"} className="capitalize">{qr.status}</Badge>
          </div>
          <button onClick={copy} className="mt-1 flex items-center gap-1 font-mono text-xs text-primary hover:underline">
            {display} <Copy className="h-3 w-3" />
          </button>
          <p className="mt-1 truncate text-xs text-muted-foreground">→ {qr.destination_url}</p>
          <p className="mt-2 font-mono text-sm"><span className="font-bold">{qr.click_count}</span> <span className="text-muted-foreground">scans</span></p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Button size="sm" variant="outline" onClick={() => onEdit(qr)} data-testid={`qr-edit-${qr.alias}`}><Pencil className="mr-1 h-3.5 w-3.5" />Edit</Button>
            <Button size="sm" variant="outline" onClick={() => ref.current?.download("png")} data-testid={`qr-png-${qr.alias}`}><Download className="mr-1 h-3.5 w-3.5" />PNG</Button>
            <Button size="sm" variant="outline" onClick={() => navigate(`/app/links/${qr.id}`)} data-testid={`qr-analytics-${qr.alias}`}><BarChart3 className="mr-1 h-3.5 w-3.5" />Stats</Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button size="sm" variant="ghost" data-testid={`qr-menu-${qr.alias}`}><MoreVertical className="h-4 w-4" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => ref.current?.download("svg")}><Download className="mr-2 h-4 w-4" />Download SVG</DropdownMenuItem>
                {qr.status === "active" ? (
                  <DropdownMenuItem onClick={() => onAction("pause", qr.id)}><Pause className="mr-2 h-4 w-4" />Pause</DropdownMenuItem>
                ) : (
                  <DropdownMenuItem onClick={() => onAction("resume", qr.id)}><Play className="mr-2 h-4 w-4" />Resume</DropdownMenuItem>
                )}
                <DropdownMenuItem className="text-destructive" onClick={() => onAction("delete", qr.id)} data-testid={`qr-delete-${qr.alias}`}><Trash2 className="mr-2 h-4 w-4" />Delete</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function QRPage() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const [editing, setEditing] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["qr", workspace?.id],
    queryFn: async () => (await api.get("/qr")).data,
    enabled: !!workspace,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["qr"] });

  const mutate = useMutation({
    mutationFn: async ({ action, id }) => action === "delete" ? api.delete(`/qr/${id}`) : api.post(`/qr/${id}/${action}`),
    onSuccess: (_r, v) => { toast.success(`QR ${v.action}d`); refresh(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  const items = data?.items || [];

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Dynamic QR Codes</h1>
          <p className="mt-1 text-sm text-muted-foreground">{data?.total ?? 0} QR codes. Change destinations without reprinting.</p>
        </div>
        <Button onClick={() => { setEditing(null); setDialog(true); }} className="gap-2" data-testid="new-qr-btn">
          <Plus className="h-4 w-4" /> New Dynamic QR
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-xl" />)}</div>
      ) : items.length === 0 ? (
        <Card className="flex flex-col items-center justify-center gap-4 border-dashed py-16 text-center" data-testid="qr-empty-state">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10"><QrIcon className="h-6 w-6 text-primary" /></div>
          <div>
            <h3 className="font-display font-semibold">No QR codes yet</h3>
            <p className="text-sm text-muted-foreground">Create a dynamic QR you can restyle and redirect anytime.</p>
          </div>
          <Button onClick={() => { setEditing(null); setDialog(true); }} className="gap-2"><Plus className="h-4 w-4" /> New Dynamic QR</Button>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2" data-testid="qr-list">
          {items.map((qr) => (
            <QRCard key={qr.id} qr={qr} primaryDomain={workspace?.primary_domain} onEdit={(q) => { setEditing(q); setDialog(true); }} onAction={(action, id) => mutate.mutate({ action, id })} />
          ))}
        </div>
      )}

      <QRDialog open={dialog} onOpenChange={setDialog} onSaved={refresh} existing={editing} />
    </DashboardLayout>
  );
}
