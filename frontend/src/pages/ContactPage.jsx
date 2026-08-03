import React, { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Mail, CheckCircle2, Send, MessageCircle } from "lucide-react";
import Logo from "@/components/Logo";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import api, { formatApiError } from "@/lib/api";
import { CATEGORIES } from "@/components/TicketThread";

const SUPPORT_EMAIL = "support@midgate.co";
const WHATSAPP_DISPLAY = "+62 851-1121-9661";
const WHATSAPP_LINK = "https://wa.me/6285111219661?text=" + encodeURIComponent("Halo MidGate, saya ingin bertanya.");

export default function ContactPage() {
  const [form, setForm] = useState({ name: "", email: "", subject: "", category: "other", message: "" });
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/support/public", form);
      setSent(true);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" data-testid="contact-logo-link"><Logo /></Link>
          <Button asChild variant="ghost" size="sm" className="gap-2"><Link to="/" data-testid="contact-back-home"><ArrowLeft className="h-4 w-4" />Home</Link></Button>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:py-16">
        <div className="mb-8 text-center">
          <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Contact us</h1>
          <p className="mt-3 text-muted-foreground">
            Questions, bugs, or abuse reports? Reach us by email or WhatsApp — or send a message below.
          </p>
        </div>

        <div className="mb-8 grid gap-4 sm:grid-cols-2">
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            data-testid="contact-email-card"
            className="group flex items-center gap-4 rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/50"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Mail className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Email</p>
              <p className="truncate font-medium text-foreground group-hover:text-primary" data-testid="contact-email">{SUPPORT_EMAIL}</p>
            </div>
          </a>
          <a
            href={WHATSAPP_LINK}
            target="_blank"
            rel="noreferrer"
            data-testid="contact-whatsapp-card"
            className="group flex items-center gap-4 rounded-xl border border-border bg-card p-4 transition-colors hover:border-emerald-500/50"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <MessageCircle className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">WhatsApp</p>
              <p className="truncate font-medium text-foreground group-hover:text-emerald-600" data-testid="contact-whatsapp">{WHATSAPP_DISPLAY}</p>
            </div>
          </a>
        </div>

        <Card className="p-6 sm:p-8">
          {sent ? (
            <div className="flex flex-col items-center gap-3 py-8 text-center" data-testid="contact-success">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10"><CheckCircle2 className="h-7 w-7 text-emerald-500" /></div>
              <h2 className="font-display text-xl font-semibold">Message received</h2>
              <p className="text-sm text-muted-foreground">Thanks for reaching out. Our team will reply to your email shortly.</p>
              <Button asChild variant="outline" className="mt-2"><Link to="/">Back to home</Link></Button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="contact-name-input" />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input required type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} data-testid="contact-email-input" />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
                <div className="space-y-2">
                  <Label>Subject</Label>
                  <Input required value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))} data-testid="contact-subject-input" />
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                    <SelectTrigger data-testid="contact-category-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c.v} value={c.v}>{c.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Message</Label>
                <Textarea required rows={5} value={form.message} onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))} data-testid="contact-message-input" placeholder="How can we help?" />
              </div>
              <Button type="submit" className="w-full gap-2" disabled={loading} data-testid="contact-submit-btn">
                <Send className="h-4 w-4" />{loading ? "Sending…" : "Send message"}
              </Button>
            </form>
          )}
        </Card>
      </main>
    </div>
  );
}
