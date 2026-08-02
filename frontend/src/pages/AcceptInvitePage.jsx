import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { Users, CheckCircle2, XCircle, LogIn } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const { user, refreshSession } = useAuth();
  const [invite, setInvite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    if (token) localStorage.setItem("midgate_invite", token);
    (async () => {
      try {
        const { data } = await api.get(`/team/invitations/lookup/${token}`);
        setInvite(data);
      } catch (err) {
        setError(formatApiError(err.response?.data?.detail) || "Invitation not found");
      } finally { setLoading(false); }
    })();
  }, [token]);

  const accept = async () => {
    setAccepting(true);
    try {
      await api.post("/team/invitations/accept", { token });
      localStorage.removeItem("midgate_invite");
      toast.success(`You've joined ${invite.workspace_name}!`);
      await refreshSession();
      navigate("/app");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setAccepting(false); }
  };

  const emailMatches = user && invite && user.email?.toLowerCase() === invite.email?.toLowerCase();
  const badStatus = invite && invite.status !== "pending";

  return (
    <AuthShell title="Workspace invitation" subtitle="Join a MidGate workspace">
      {loading || user === null ? (
        <Skeleton className="h-40 w-full rounded-xl" data-testid="invite-loading" />
      ) : error ? (
        <div className="text-center" data-testid="invite-error">
          <XCircle className="mx-auto mb-3 h-10 w-10 text-red-500" />
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button asChild variant="outline" className="mt-4"><Link to="/login">Go to login</Link></Button>
        </div>
      ) : (
        <div className="space-y-5" data-testid="invite-panel">
          <div className="rounded-xl border border-border bg-card p-5 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Users className="h-6 w-6 text-primary" />
            </div>
            <p className="text-sm text-muted-foreground">You've been invited to join</p>
            <p className="font-display text-lg font-bold">{invite.workspace_name}</p>
            <p className="mt-1 text-sm">as <span className="font-semibold">{invite.role_label}</span></p>
            <p className="mt-2 text-xs text-muted-foreground">Invitation for {invite.email}</p>
          </div>

          {badStatus ? (
            <p className="rounded-lg bg-muted p-3 text-center text-sm text-muted-foreground" data-testid="invite-bad-status">
              This invitation is <span className="font-medium">{invite.status}</span> and can no longer be used.
            </p>
          ) : user === false ? (
            <div className="space-y-3" data-testid="invite-need-auth">
              <p className="text-center text-sm text-muted-foreground">
                Sign in or create an account with <span className="font-medium text-foreground">{invite.email}</span> to accept.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Button asChild variant="outline" data-testid="invite-login-btn"><Link to="/login"><LogIn className="mr-1.5 h-4 w-4" />Log in</Link></Button>
                <Button asChild data-testid="invite-register-btn"><Link to="/register">Create account</Link></Button>
              </div>
            </div>
          ) : emailMatches ? (
            <Button className="w-full gap-2" onClick={accept} disabled={accepting} data-testid="invite-accept-btn">
              <CheckCircle2 className="h-4 w-4" />{accepting ? "Joining…" : `Accept & join`}
            </Button>
          ) : (
            <div className="space-y-3 text-center" data-testid="invite-mismatch">
              <p className="text-sm text-muted-foreground">
                You're signed in as <span className="font-medium text-foreground">{user.email}</span>, but this invite is for <span className="font-medium text-foreground">{invite.email}</span>.
              </p>
              <Button asChild variant="outline"><Link to="/login">Switch account</Link></Button>
            </div>
          )}
        </div>
      )}
    </AuthShell>
  );
}
