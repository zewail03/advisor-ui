"use client";

import { useCallback, useEffect, useState } from "react";
import { LANG_EVENT, LANG_LS_KEY, translate, type Lang, type TranslationKey } from "@/lib/i18n";

function readLang(): Lang {
  if (typeof window === "undefined") return "en";
  try {
    const saved = localStorage.getItem(LANG_LS_KEY);
    if (saved === "ar" || saved === "en") return saved;
  } catch {
    // ignore
  }
  return "en";
}

function applyLang(lang: Lang) {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
}

export function useLanguage() {
  const [lang, setLang] = useState<Lang>("en");

  useEffect(() => {
    const initial = readLang();
    setLang(initial);
    applyLang(initial);

    // Same live-sync pattern as useTheme: every mounted component updates
    // the moment any of them switches the language. Re-apply dir/lang too,
    // so cross-tab changes also flip the layout direction.
    const sync = () => {
      const next = readLang();
      setLang(next);
      applyLang(next);
    };
    window.addEventListener(LANG_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(LANG_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const setLanguage = useCallback((next: Lang) => {
    try {
      localStorage.setItem(LANG_LS_KEY, next);
    } catch {
      // ignore
    }
    applyLang(next);
    window.dispatchEvent(new Event(LANG_EVENT));
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage(readLang() === "en" ? "ar" : "en");
  }, [setLanguage]);

  const t = useCallback((key: TranslationKey) => translate(lang, key), [lang]);

  const isAr = lang === "ar";

  return { lang, isAr, dir: isAr ? "rtl" : "ltr", t, setLanguage, toggleLanguage };
}
