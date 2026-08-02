import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus,
  Copy,
  Pause,
  Play,
  Trash2,
  ExternalLink,
  BarChart3,
  Link2,
  Search,
} from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { MoreVertical } from "lucide-react";
import api, { formatApiError, shortUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function CreateLinkDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState({ name: "", destination_url: "", alias: "", description: "" });
  const [loading, setLoading] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = { name: form.name, destination_url: form.destination_url };
      if (form.alias.trim()) payload.alias = form.alias.trim();
      if (form.description.trim()) payload.description = form.description.trim();
      const { data } = await api.post("/links", payload);
      toast.success("Smart Link created");
      setForm({ name: "", destination_url: "", alias: "", description: "" });
      onCreated(data);
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="create-link-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">New Smart Link</DialogTitle>
          <DialogDescription>Create a short, protected link with real-time analytics.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" required value={form.name} onChange={set("name")} data-testid="link-name-input" placeholder="Spring campaign" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="dest">Destination URL</Label>
            <Input id="dest" required value={form.destination_url} onChange={set("destination_url")} data-testid="link-destination-input" placeholder="https://example.com/page" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="alias">Custom alias <span className="text-muted-foreground">(optional)</span></Label>
            <Input id="alias" value={form.alias} onChange={set("alias")} data-testid="link-alias-input" placeholder="spring24" className="font-mono" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="desc">Description <span className="text-muted-foreground">(optional)</span></Label>
            <Textarea id="desc" value={form.description} onChange={set("description")} data-testid="link-description-input" rows={2} />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={loading} data-testid="link-create-submit-btn">
              {loading ? "Creating…" : "Create link"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function LinksPage() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState(false);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["links", workspace?.id, search],
    queryFn: async () => (await api.get("/links", { params: search ? { search } : {} })).data,
    enabled: !!workspace,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["links"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const mutate = useMutation({
    mutationFn: async ({ action, id }) => {
      if (action === "delete") return api.delete(`/links/${id}`);
      return api.post(`/links/${id}/${action}`);
    },
    onSuccess: (_res, vars) => {
      toast.success(`Link ${vars.action}d`);
      invalidate();
    },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  const copy = (alias) => {
    navigator.clipboard.writeText(shortUrl(alias));
    toast.success("Short URL copied");
  };

  const items = data?.items || [];

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Smart Links</h1>
          <p className="mt-1 text-sm text-muted-foreground">{data?.total ?? 0} links in this workspace.</p>
        </div>
        <Button onClick={() => setDialog(true)} className="gap-2" data-testid="new-link-btn">
          <Plus className="h-4 w-4" /> New Smart Link
        </Button>
      </div>

      <div className="mb-4 relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search links…"
          className="pl-9"
          data-testid="links-search-input"
        />
      </div>

      {isLoading ? (
        <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>
      ) : items.length === 0 ? (
        <Card className="flex flex-col items-center justify-center gap-4 border-dashed py-16 text-center" data-testid="links-empty-state">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10">
            <Link2 className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h3 className="font-display font-semibold">No smart links yet</h3>
            <p className="text-sm text-muted-foreground">Create your first protected short link.</p>
          </div>
          <Button onClick={() => setDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> New Smart Link</Button>
        </Card>
      ) : (
        <div className="space-y-3" data-testid="links-list">
          {items.map((l) => (
            <Card key={l.id} className="card-lift p-4" data-testid={`link-row-${l.alias}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-semibold">{l.name}</p>
                    <Badge variant={l.status === "active" ? "default" : "secondary"} className="capitalize">
                      {l.status}
                    </Badge>
                  </div>
                  <button
                    onClick={() => copy(l.alias)}
                    className="mt-1 flex items-center gap-1.5 font-mono text-sm text-primary hover:underline"
                    data-testid={`link-shorturl-${l.alias}`}
                  >
                    /api/r/{l.alias} <Copy className="h-3 w-3" />
                  </button>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{l.destination_url}</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <p className="font-mono text-lg font-bold">{l.click_count}</p>
                    <p className="text-xs text-muted-foreground">clicks</p>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => copy(l.alias)} data-testid={`copy-btn-${l.alias}`}>
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => navigate(`/app/links/${l.id}`)} data-testid={`analytics-btn-${l.alias}`}>
                    <BarChart3 className="h-4 w-4" />
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" data-testid={`menu-btn-${l.alias}`}>
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild>
                        <a href={shortUrl(l.alias)} target="_blank" rel="noreferrer" data-testid={`open-btn-${l.alias}`}>
                          <ExternalLink className="mr-2 h-4 w-4" /> Open link
                        </a>
                      </DropdownMenuItem>
                      {l.status === "active" ? (
                        <DropdownMenuItem onClick={() => mutate.mutate({ action: "pause", id: l.id })} data-testid={`pause-btn-${l.alias}`}>
                          <Pause className="mr-2 h-4 w-4" /> Pause
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => mutate.mutate({ action: "resume", id: l.id })} data-testid={`resume-btn-${l.alias}`}>
                          <Play className="mr-2 h-4 w-4" /> Resume
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => mutate.mutate({ action: "delete", id: l.id })}
                        data-testid={`delete-btn-${l.alias}`}
                      >
                        <Trash2 className="mr-2 h-4 w-4" /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <CreateLinkDialog open={dialog} onOpenChange={setDialog} onCreated={invalidate} />
    </DashboardLayout>
  );
}
