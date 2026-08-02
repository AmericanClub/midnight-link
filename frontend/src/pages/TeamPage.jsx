import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Users, UserPlus, Trash2, Copy, Crown, Mail, Lock, Clock,
} from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const ROLES = [
  { v: "admin", label: "Admin" },
  { v: "member", label: "Member" },
  { v: "billing_manager", label: "Billing" },
];
const roleLabel = (r) => ({ owner: "Owner", admin: "Admin", member: "Member", billing_manager: "Billing" }[r] || r);
const initials = (s) => (s || "?").slice(0, 2).toUpperCase();

function InviteDialog({ open, onOpenChange, onInvited }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [loading, setLoading] = useState(false);
  const [invited, setInvited] = useState(null);

  React.useEffect(() => { if (open) { setEmail(""); setRole("member"); setInvited(null); } }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post("/team/invitations", { email, role });
      setInvited({ ...data, link: `${window.location.origin}${data.accept_path}` });
      onInvited();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="invite-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Invite a teammate</DialogTitle>
          <DialogDescription>They'll get an email with a link to join this workspace.</DialogDescription>
        </DialogHeader>
        {invited ? (
          <div className="space-y-3" data-testid="invite-success">
            <p className="text-sm text-muted-foreground">Invitation sent to <span className="font-medium text-foreground">{invited.email}</span> as {roleLabel(invited.role)}. Share this link:</p>
            <div className="flex items-center gap-2">
              <Input readOnly value={invited.link} className="font-mono text-xs" data-testid="invite-link-value" />
              <Button size="icon" variant="outline" onClick={() => { navigator.clipboard.writeText(invited.link); toast.success("Copied"); }} data-testid="copy-invite-link">
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <Button className="w-full" onClick={() => onOpenChange(false)} data-testid="invite-done-btn">Done</Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label>Email</Label>
              <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" data-testid="invite-email-input" />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger data-testid="invite-role-select"><SelectValue /></SelectTrigger>
                <SelectContent>{ROLES.map((r) => <SelectItem key={r.v} value={r.v} data-testid={`invite-role-${r.v}`}>{r.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="invite-send-btn">
              {loading ? "Sending…" : "Send invitation"}
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function TeamPage() {
  const { workspace } = useAuth();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState(false);
  const isManager = ["owner", "admin"].includes(workspace?.role);

  const { data, isLoading } = useQuery({
    queryKey: ["team", workspace?.id],
    queryFn: async () => (await api.get("/team/members")).data,
    enabled: !!workspace,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["team"] });

  const changeRole = useMutation({
    mutationFn: async ({ userId, role }) => api.patch(`/team/members/${userId}`, { role }),
    onSuccess: () => { toast.success("Role updated"); refresh(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const removeMember = useMutation({
    mutationFn: async (userId) => api.delete(`/team/members/${userId}`),
    onSuccess: () => { toast.success("Member removed"); refresh(); },
    onError: (err) => toast.error(formatApiError(err.response?.data?.detail) || err.message),
  });
  const revoke = useMutation({
    mutationFn: async (id) => api.delete(`/team/invitations/${id}`),
    onSuccess: () => { toast.success("Invitation revoked"); refresh(); },
  });

  const members = data?.members || [];
  const invitations = data?.invitations || [];

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Team</h1>
          <p className="mt-1 text-sm text-muted-foreground">Invite people to this workspace and manage their roles.</p>
        </div>
        {isManager && (
          <Button onClick={() => setDialog(true)} className="gap-2" data-testid="invite-btn">
            <UserPlus className="h-4 w-4" /> Invite member
          </Button>
        )}
      </div>

      <Card className="p-6" data-testid="members-card">
        <div className="mb-4 flex items-center gap-2"><Users className="h-4 w-4 text-primary" /><h2 className="font-display font-semibold">Members <span className="font-normal text-muted-foreground">({members.length})</span></h2></div>
        {isLoading ? <Skeleton className="h-24 w-full" /> : (
          <ul className="divide-y divide-border" data-testid="members-list">
            {members.map((m) => (
              <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-3 py-3" data-testid={`member-${m.email}`}>
                <div className="flex min-w-0 items-center gap-3">
                  <Avatar className="h-9 w-9"><AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">{initials(m.name)}</AvatarFallback></Avatar>
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 truncate font-medium">
                      {m.name}
                      {m.is_owner && <Crown className="h-3.5 w-3.5 text-amber-500" />}
                      {m.is_you && <span className="text-xs text-muted-foreground">(you)</span>}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{m.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {m.is_owner || !isManager ? (
                    <Badge variant={m.is_owner ? "default" : "secondary"} className="gap-1">
                      {m.is_owner && <Lock className="h-3 w-3" />}{roleLabel(m.role)}
                    </Badge>
                  ) : (
                    <>
                      <Select value={m.role} onValueChange={(role) => changeRole.mutate({ userId: m.user_id, role })}>
                        <SelectTrigger className="h-8 w-[130px]" data-testid={`member-role-${m.email}`}><SelectValue /></SelectTrigger>
                        <SelectContent>{ROLES.map((r) => <SelectItem key={r.v} value={r.v}>{r.label}</SelectItem>)}</SelectContent>
                      </Select>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => removeMember.mutate(m.user_id)} data-testid={`member-remove-${m.email}`}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {isManager && invitations.length > 0 && (
        <Card className="mt-6 p-6" data-testid="invitations-card">
          <div className="mb-4 flex items-center gap-2"><Mail className="h-4 w-4 text-primary" /><h2 className="font-display font-semibold">Pending invitations</h2></div>
          <ul className="divide-y divide-border" data-testid="invitations-list">
            {invitations.map((inv) => (
              <li key={inv.id} className="flex items-center justify-between gap-3 py-3" data-testid={`invite-${inv.email}`}>
                <div className="min-w-0">
                  <p className="truncate font-medium">{inv.email}</p>
                  <p className="flex items-center gap-1 text-xs text-muted-foreground"><Clock className="h-3 w-3" />Invited as {inv.role_label}</p>
                </div>
                <Button size="sm" variant="outline" className="gap-1.5 text-destructive" onClick={() => revoke.mutate(inv.id)} data-testid={`invite-revoke-${inv.email}`}>
                  <Trash2 className="h-3.5 w-3.5" />Revoke
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <InviteDialog open={dialog} onOpenChange={setDialog} onInvited={refresh} />
    </DashboardLayout>
  );
}
