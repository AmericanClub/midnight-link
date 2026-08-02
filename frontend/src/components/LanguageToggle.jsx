import React from "react";
import { Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/context/I18nContext";

export default function LanguageToggle() {
  const { lang, changeLang } = useI18n();
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => changeLang(lang === "en" ? "id" : "en")}
      data-testid="language-toggle-btn"
      className="gap-1.5 font-mono text-xs"
    >
      <Languages className="h-4 w-4" />
      {lang.toUpperCase()}
    </Button>
  );
}
