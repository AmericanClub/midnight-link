import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { LifeBuoy, Plus, Send, Mail, MessageSquare } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { TicketMessages, STATUS_VARIANT, CATEGORIES, PRIORITIES } from "@/components/TicketThread";

const SUPPORT_EMAIL = "support@midnightlink.link";

function NewTicketDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState({ subject: "", category: "bug", priority: "medium", message: "" });
  const [loading, setLoading] = useState(false);
  React.useEffect(() => { if (open) setForm({ subject: "", category: "bug", priority: "medium", message: "" }); }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post("/support/tickets", form);
      toast.success("Ticket created");
      onCreated(data);
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="new-ticket-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">New support ticket</DialogTitle>
          <DialogDescription>Tell us what's going on and we'll get back to you.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label>Subject</Label>
            <Input required value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))} data-testid="ticket-subject-input" placeholder="Short summary" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Category</Label>
              <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                <SelectTrigger data-testid="ticket-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c.v} value={c.v}>{c.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Priority</Label>
              <Select value={form.priority} onValueChange={(v) => setForm((f) => ({ ...f, priority: v }))}>
                <SelectTrigger data-testid="ticket-priority-select"><SelectValue /></SelectTrigger>
                <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p.v} value={p.v}>{p.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label>Message</Label>
            <Textarea required rows={4} value={form.message} onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))} data-testid="ticket-message-input" placeholder="Describe the issue…" />
          </div>
          <Button type="submit" className="w-full" disabled={loading} data-testid="ticket-submit-btn">
            {loading ? "Sending…" : "Create ticket"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TicketThreadPanel({ ticketId }) {
  const qc = useQueryClient();
  const [reply, setReply] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["my-ticket", ticketId],
    queryFn: async () => (await api.get(`/support/tickets/${ticketId}`)).data,
    enabled: !!ticketId,
  });
  const send = useMutation({
    mutationFn: async () => api.post(`/support/tickets/${ticketId}/reply`, { body: reply }),
    onSuccess: () => { setReply(""); qc.invalidateQueries({ queryKey: ["my-ticket", ticketId] }); qc.invalidateQueries({ queryKey: ["my-tickets"] }); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });

  if (isLoading || !data) return <Skeleton className="h-96 w-full rounded-xl" />;
  const closed = ["resolved", "closed"].includes(data.status);
  return (
    <Card className="flex h-[560px] flex-col p-5" data-testid="ticket-thread">
      <div className="mb-3 flex items-start justify-between gap-3 border-b border-border pb-3">
        <div className="min-w-0">
          <p className="truncate font-display font-semibold">{data.subject}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge variant={STATUS_VARIANT[data.status]} className="capitalize">{data.status}</Badge>
            <Badge variant="outline" className="capitalize">{data.category}</Badge>
            <Badge variant="outline" className="capitalize">{data.priority}</Badge>
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto pr-1">
        <TicketMessages messages={data.messages} mySide="user" />
      </div>
      <div className="mt-3 border-t border-border pt-3">
        {closed ? (
          <p className="text-center text-xs text-muted-foreground">This ticket is {data.status}. Reply to reopen it.</p>
        ) : null}
        <div className="flex items-end gap-2">
          <Textarea rows={2} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Write a reply…" className="resize-none" data-testid="ticket-reply-input" />
          <Button size="icon" onClick={() => reply.trim() && send.mutate()} disabled={send.isPending || !reply.trim()} data-testid="ticket-reply-send"><Send className="h-4 w-4" /></Button>
        </div>
      </div>
    </Card>
  );
}

export default function SupportPage() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const [selected, setSelected] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["my-tickets", workspace?.id],
    queryFn: async () => (await api.get("/support/tickets")).data,
  });
  const items = data?.items || [];

  const onCreated = (t) => { qc.invalidateQueries({ queryKey: ["my-tickets"] }); setSelected(t.id); };

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Support</h1>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
            Need help? Email <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary hover:underline" data-testid="support-email">{SUPPORT_EMAIL}</a> or open a ticket.
          </p>
        </div>
        <Button onClick={() => setDialog(true)} className="gap-2" data-testid="new-ticket-btn"><Plus className="h-4 w-4" /> New ticket</Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <div className="space-y-2" data-testid="my-tickets-list">
          {isLoading ? [...Array(3)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
            : items.length === 0 ? (
              <Card className="flex flex-col items-center gap-2 border-dashed py-12 text-center" data-testid="tickets-empty">
                <MessageSquare className="h-8 w-8 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">No tickets yet.</p>
              </Card>
            ) : items.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelected(t.id)}
                data-testid={`ticket-item-${t.id}`}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${selected === t.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate font-medium">{t.subject}</p>
                  <Badge variant={STATUS_VARIANT[t.status]} className="shrink-0 capitalize">{t.status}</Badge>
                </div>
                <p className="mt-1 truncate text-xs text-muted-foreground">{t.last_message}</p>
              </button>
            ))}
        </div>
        <div>
          {selected ? <TicketThreadPanel ticketId={selected} /> : (
            <Card className="flex h-[560px] flex-col items-center justify-center gap-3 border-dashed text-center" data-testid="no-ticket-selected">
              <LifeBuoy className="h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">Select a ticket to view the conversation,<br />or create a new one.</p>
            </Card>
          )}
        </div>
      </div>

      <NewTicketDialog open={dialog} onOpenChange={setDialog} onCreated={onCreated} />
    </DashboardLayout>
  );
}
