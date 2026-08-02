import React, { createContext, useContext, useState } from "react";
import { translations } from "@/i18n/translations";

const I18nContext = createContext();

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem("midgate-lang") || "en");

  const changeLang = (l) => {
    setLang(l);
    localStorage.setItem("midgate-lang", l);
  };

  const t = (key) => {
    const dict = translations[lang] || translations.en;
    return dict[key] ?? translations.en[key] ?? key;
  };

  return (
    <I18nContext.Provider value={{ lang, changeLang, t }}>{children}</I18nContext.Provider>
  );
}

export const useI18n = () => useContext(I18nContext);
