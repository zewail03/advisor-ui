"use client";

import { useEffect, useState, useCallback } from "react";
import { THEME_LS_KEY } from "@/lib/constants";

const THEME_EVENT = "aiu-theme-change";

function readTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  try {
    const saved = localStorage.getItem(THEME_LS_KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    // ignore
  }
  return "light";
}

function applyTheme(theme: "light" | "dark") {
  if (theme === "dark") document.documentElement.classList.add("dark");
  else document.documentElement.classList.remove("dark");
}

export function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const initial = readTheme();
    setTheme(initial);
    applyTheme(initial);

    // Re-sync when ANY component toggles the theme (same tab) or when
    // another tab changes it (storage event). This is what makes the
    // toggle take effect instantly across every mounted component.
    const sync = () => setTheme(readTheme());
    window.addEventListener(THEME_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(THEME_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const toggleTheme = useCallback(() => {
    const next = readTheme() === "light" ? "dark" : "light";
    try {
      localStorage.setItem(THEME_LS_KEY, next);
    } catch {
      // ignore
    }
    applyTheme(next);
    window.dispatchEvent(new Event(THEME_EVENT));
  }, []);

  const isDark = theme === "dark";

  return { theme, isDark, toggleTheme };
}
