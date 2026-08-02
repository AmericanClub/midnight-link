import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { LifeBuoy, Send } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import api, { formatApiError } from "@/lib/api";
import { TicketMessages, STATUS_VARIANT, PRIORITIES } from "@/components/TicketThread";

const STATUS_FILTERS = ["all", "open", "pending", "resolved", "closed"];

function AdminTicketPanel({ ticketId }) {
  const qc = useQueryClient();
  const [reply, setReply] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["admin-ticket", ticketId],
    queryFn: async () => (await api.get(`/support/admin/tickets/${ticketId}`)).data,
    enabled: !!ticketId,
  });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-ticket", ticketId] });
    qc.invalidateQueries({ queryKey: ["admin-tickets"] });
  };
  const send = useMutation({
    mutationFn: async () => api.post(`/support/admin/tickets/${ticketId}/reply`, { body: reply }),
    onSuccess: () => { setReply(""); toast.success("Reply sent"); invalidate(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const update = useMutation({
    mutationFn: async (patch) => api.patch(`/support/admin/tickets/${ticketId}`, patch),
    onSuccess: () => { toast.success("Ticket updated"); invalidate(); },
  });

  if (isLoading || !data) return <Skeleton className="h-[520px] w-full rounded-xl" />;
  return (
    <Card className="flex h-[520px] flex-col p-5" data-testid="admin-ticket-thread">
      <div className="mb-3 border-b border-border pb-3">
        <p className="truncate font-display font-semibold">{data.subject}</p>
        <p className="text-xs text-muted-foreground">{data.requester_name} · <span className="font-mono">{data.requester_email}</span>{data.is_public ? " · (public)" : ""}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Select value={data.status} onValueChange={(v) => update.mutate({ status: v })}>
            <SelectTrigger className="h-8 w-[130px]" data-testid="admin-ticket-status"><SelectValue /></SelectTrigger>
            <SelectContent>{STATUS_FILTERS.filter((s) => s !== "all").map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={data.priority} onValueChange={(v) => update.mutate({ priority: v })}>
            <SelectTrigger className="h-8 w-[120px]" data-testid="admin-ticket-priority"><SelectValue /></SelectTrigger>
            <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p.v} value={p.v}>{p.label}</SelectItem>)}</SelectContent>
          </Select>
          <Badge variant="outline" className="capitalize">{data.category}</Badge>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto pr-1"><TicketMessages messages={data.messages} mySide="admin" /></div>
      <div className="mt-3 flex items-end gap-2 border-t border-border pt-3">
        <Textarea rows={2} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Reply to customer…" className="resize-none" data-testid="admin-reply-input" />
        <Button size="icon" onClick={() => reply.trim() && send.mutate()} disabled={send.isPending || !reply.trim()} data-testid="admin-reply-send"><Send className="h-4 w-4" /></Button>
      </div>
    </Card>
  );
}

export default function SupportTicketsAdmin() {
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["admin-tickets", filter],
    queryFn: async () => (await api.get("/support/admin/tickets", { params: filter === "all" ? {} : { status: filter } })).data,
  });
  const items = data?.items || [];

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Select value={filter} onValueChange={(v) => { setFilter(v); setSelected(null); }}>
            <SelectTrigger className="h-9 w-[150px]" data-testid="ticket-filter-select"><SelectValue /></SelectTrigger>
            <SelectContent>{STATUS_FILTERS.map((s) => <SelectItem key={s} value={s} className="capitalize">{s === "all" ? "All tickets" : s}</SelectItem>)}</SelectContent>
          </Select>
          <Badge variant="secondary" data-testid="tickets-open-count">{data?.open_count ?? 0} open</Badge>
        </div>
        <div className="space-y-2" data-testid="admin-tickets-list">
          {isLoading ? [...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
            : items.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">No tickets.</p>
            : items.map((t) => (
              <button key={t.id} onClick={() => setSelected(t.id)} data-testid={`admin-ticket-item-${t.id}`}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${selected === t.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate font-medium">{t.subject}</p>
                  <Badge variant={STATUS_VARIANT[t.status]} className="shrink-0 capitalize">{t.status}</Badge>
                </div>
                <p className="mt-1 truncate text-xs text-muted-foreground">{t.requester_email} · {t.category} · {t.priority}</p>
              </button>
            ))}
        </div>
      </div>
      <div>
        {selected ? <AdminTicketPanel ticketId={selected} />
          : <Card className="flex h-[520px] flex-col items-center justify-center gap-3 border-dashed text-center" data-testid="admin-no-ticket"><LifeBuoy className="h-10 w-10 text-muted-foreground/30" /><p className="text-sm text-muted-foreground">Select a ticket to view &amp; reply.</p></Card>}
      </div>
    </div>
  );
}
