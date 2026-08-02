import React, { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import AuthShell from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import api, { formatApiError } from "@/lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Forgot password" subtitle="We'll send you a reset link if the account exists.">
      {sent ? (
        <div className="rounded-lg border border-border bg-muted/40 p-4 text-sm" data-testid="forgot-sent-message">
          If an account exists for <span className="font-medium">{email}</span>, a reset link has been sent.
          (In this preview, the link is written to the server logs.)
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="forgot-email-input"
              placeholder="you@company.com"
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading} data-testid="forgot-submit-btn">
            {loading ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        <Link to="/login" className="font-medium text-primary hover:underline">Back to log in</Link>
      </p>
    </AuthShell>
  );
}
