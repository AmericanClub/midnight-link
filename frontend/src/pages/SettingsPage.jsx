import React from "react";
import { toast } from "sonner";
import DashboardLayout from "@/components/DashboardLayout";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { useI18n } from "@/context/I18nContext";

export default function SettingsPage() {
  const { user, workspace } = useAuth();
  const { theme, toggle } = useTheme();
  const { lang, changeLang } = useI18n();

  return (
    <DashboardLayout>
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Manage your account and preferences.</p>
      </div>

      <div className="space-y-6">
        <Card className="p-6" data-testid="settings-account-card">
          <h2 className="mb-4 font-display font-semibold">Account</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={user?.name || ""} readOnly />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={user?.email || ""} readOnly />
            </div>
            <div className="space-y-2">
              <Label>Workspace</Label>
              <Input value={workspace?.name || ""} readOnly />
            </div>
            <div className="space-y-2">
              <Label>Plan</Label>
              <Input value={workspace?.plan || "free"} readOnly className="capitalize" />
            </div>
          </div>
        </Card>

        <Card className="p-6" data-testid="settings-appearance-card">
          <h2 className="mb-4 font-display font-semibold">Appearance & Language</h2>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">Theme</span>
              <Button variant="outline" onClick={toggle} className="capitalize" data-testid="settings-theme-btn">{theme} mode</Button>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">Language</span>
              <Button variant="outline" onClick={() => changeLang(lang === "en" ? "id" : "en")} data-testid="settings-lang-btn">
                {lang === "en" ? "English" : "Bahasa Indonesia"}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="p-6" data-testid="settings-api-card">
          <h2 className="mb-2 font-display font-semibold">Developer API</h2>
          <p className="text-sm text-muted-foreground">
            The versioned API, webhooks and custom domains arrive in a later milestone.
          </p>
          <Button className="mt-4" variant="outline" onClick={() => toast.info("Available in a later milestone")} data-testid="settings-api-btn">
            Generate API key
          </Button>
        </Card>
      </div>
    </DashboardLayout>
  );
}
