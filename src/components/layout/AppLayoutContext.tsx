"use client";

import { createContext, useContext } from "react";

type AppLayoutContextValue = {
  isDark: boolean;
  token: string | null;
  signOut: () => void;
};

export const AppLayoutContext = createContext<AppLayoutContextValue>({
  isDark: false,
  token: null,
  signOut: () => {},
});

export function useAppLayout() {
  return useContext(AppLayoutContext);
}
