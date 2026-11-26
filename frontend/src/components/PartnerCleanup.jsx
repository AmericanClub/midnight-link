import React, { useState } from "react";
import { toast } from "sonner";
import { Eraser, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import api, { formatApiError } from "@/lib/api";

const DAYS = 30;
const idr = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString("id-ID") : "—");

/** Permanently removes a partner's charges + webhook logs older than 30 days (after a preview + confirm). */
export default function PartnerCleanup({ partnerId, onDone }) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const openPreview = async () => {
    setOpen(true);
    setPreview(null);
    setLoading(true);
    try {
      const r = await api.get(`/admin/partners/${partnerId}/cleanup-preview`, { params: { older_than_days: DAYS } });
      setPreview(r.data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
      setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  const confirm = async () => {
    setDeleting(true);
    try {
      const r = await api.post(`/admin/partners/${partnerId}/cleanup`, { older_than_days: DAYS, confirm: true });
      toast.success(`Removed ${r.data.charges_deleted} charge(s) and ${r.data.deliveries_deleted} webhook log(s)`);
      setOpen(false);
      onDone?.(r.data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setDeleting(false);
    }
  };

  const nothing = preview && preview.charges === 0 && preview.deliveries === 0;
  const bs = preview?.by_status || {};

  return (
    <div className="space-y-2 border-t pt-4" data-testid="partner-cleanup-section">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Clean up old data</p>
          <p className="text-xs text-muted-foreground">
            Permanently deletes the charges (top-up history, every status) and webhook logs older than {DAYS} days.
            The partner, its API key and the last {DAYS} days stay untouched.
          </p>
        </div>
        <Button size="sm" variant="outline" className="gap-1" onClick={openPreview} data-testid="partner-cleanup-open">
          <Eraser className="h-3.5 w-3.5" /> Clean up &gt; {DAYS} days
        </Button>
      </div>

      <Dialog open={open} onOpenChange={(v) => !deleting && setOpen(v)}>
        <DialogContent data-testid="partner-cleanup-dialog">
          <DialogHeader>
            <DialogTitle>Clean up data older than {DAYS} days</DialogTitle>
            <DialogDescription>
              Everything created before <b>{fmtDate(preview?.cutoff)}</b> will be deleted permanently. This cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {loading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Counting old records…</div>
          ) : preview && (
            <div className="space-y-3 text-sm" data-testid="partner-cleanup-preview">
              {nothing ? (
                <p className="rounded-md border p-3 text-muted-foreground" data-testid="partner-cleanup-nothing">Nothing older than {DAYS} days — no data to clean up.</p>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Charges</p>
                      <p className="font-mono text-lg font-bold" data-testid="partner-cleanup-charges">{preview.charges}</p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Webhook logs</p>
                      <p className="font-mono text-lg font-bold" data-testid="partner-cleanup-deliveries">{preview.deliveries}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Paid: <b>{bs.paid || 0}</b> · Pending: <b>{bs.pending || 0}</b> · Expired: <b>{bs.expired || 0}</b>
                  </p>
                  {(bs.paid || 0) > 0 && (
                    <p className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs" data-testid="partner-cleanup-paid-warning">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                      Includes {bs.paid} paid charge(s) worth {idr(preview.paid_amount)}. The Paid and Collected totals for this partner will go down accordingly.
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={deleting} data-testid="partner-cleanup-cancel">Cancel</Button>
            <Button variant="destructive" className="gap-1" onClick={confirm} disabled={loading || deleting || !preview || nothing} data-testid="partner-cleanup-confirm">
              {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eraser className="h-3.5 w-3.5" />} Delete permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
