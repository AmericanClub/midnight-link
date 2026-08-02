import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bell, CheckCheck, X, Info, CheckCircle2, AlertTriangle, AlertOctagon, BellOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const LEVEL_ICON = {
  info: { Icon: Info, cls: "text-blue-500" },
  success: { Icon: CheckCircle2, cls: "text-emerald-500" },
  warning: { Icon: AlertTriangle, cls: "text-amber-500" },
  error: { Icon: AlertOctagon, cls: "text-red-500" },
};

function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function NotificationBell() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const countQ = useQuery({
    queryKey: ["notif-count", workspace?.id],
    queryFn: async () => (await api.get("/notifications/unread-count")).data,
    enabled: !!workspace,
    refetchInterval: 30000,
  });
  const listQ = useQuery({
    queryKey: ["notif-list", workspace?.id],
    queryFn: async () => (await api.get("/notifications")).data,
    enabled: !!workspace && open,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["notif-count"] });
    qc.invalidateQueries({ queryKey: ["notif-list"] });
  };
  const readOne = useMutation({ mutationFn: async (id) => api.post(`/notifications/${id}/read`), onSuccess: refresh });
  const readAll = useMutation({ mutationFn: async () => api.post("/notifications/read-all"), onSuccess: refresh });
  const dismiss = useMutation({ mutationFn: async (id) => api.delete(`/notifications/${id}`), onSuccess: refresh });

  const unread = countQ.data?.count || 0;
  const items = listQ.data?.items || [];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button className="relative flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground outline-none transition-colors hover:bg-accent hover:text-foreground" data-testid="notification-bell">
          <Bell className="h-[18px] w-[18px]" />
          {unread > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white" data-testid="notification-badge">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[360px] p-0" data-testid="notification-panel">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="font-display text-sm font-semibold">Notifications</p>
          {unread > 0 && (
            <button onClick={() => readAll.mutate()} className="flex items-center gap-1 text-xs text-primary hover:underline" data-testid="notif-read-all">
              <CheckCheck className="h-3.5 w-3.5" /> Mark all read
            </button>
          )}
        </div>
        {listQ.isLoading ? (
          <div className="p-6 text-center text-sm text-muted-foreground">Loading…</div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 p-8 text-center" data-testid="notif-empty">
            <BellOff className="h-8 w-8 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">You're all caught up.</p>
          </div>
        ) : (
          <ScrollArea className="max-h-[380px]">
            <ul className="divide-y divide-border" data-testid="notif-list">
              {items.map((n) => {
                const { Icon, cls } = LEVEL_ICON[n.level] || LEVEL_ICON.info;
                return (
                  <li
                    key={n.id}
                    onClick={() => !n.read && readOne.mutate(n.id)}
                    className={`group flex gap-3 px-4 py-3 transition-colors hover:bg-accent/50 ${n.read ? "" : "bg-primary/5"}`}
                    data-testid={`notif-item-${n.id}`}
                  >
                    <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 text-sm font-medium">
                        {n.title}
                        {!n.read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />}
                      </p>
                      <p className="text-xs text-muted-foreground">{n.body}</p>
                      <p className="mt-0.5 text-[11px] text-muted-foreground/70">{timeAgo(n.created_at)}</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); dismiss.mutate(n.id); }}
                      className="opacity-0 transition-opacity group-hover:opacity-100"
                      data-testid={`notif-dismiss-${n.id}`}
                      title="Dismiss"
                    >
                      <X className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                    </button>
                  </li>
                );
              })}
            </ul>
          </ScrollArea>
        )}
      </PopoverContent>
    </Popover>
  );
}
