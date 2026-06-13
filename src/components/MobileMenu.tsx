"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/hooks/useLanguage";

type NavItem = {
  label: string;
  onClick: () => void;
  active?: boolean;
};

type Props = {
  items: NavItem[];
  isDark: boolean;
  onSignOut?: () => void;
};

export default function MobileMenu({ items, isDark, onSignOut }: Props) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  return (
    <div className="lg:hidden">
      {/* Hamburger button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex flex-col items-center justify-center gap-1.5 h-10 w-10 rounded-lg transition-colors ${
          isDark ? "hover:bg-zinc-800" : "hover:bg-zinc-100"
        }`}
        type="button"
        aria-label="Toggle menu"
      >
        <motion.span
          animate={open ? { rotate: 45, y: 6 } : { rotate: 0, y: 0 }}
          className={`block h-0.5 w-5 rounded-full ${isDark ? "bg-white" : "bg-zinc-800"}`}
        />
        <motion.span
          animate={open ? { opacity: 0, scaleX: 0 } : { opacity: 1, scaleX: 1 }}
          className={`block h-0.5 w-5 rounded-full ${isDark ? "bg-white" : "bg-zinc-800"}`}
        />
        <motion.span
          animate={open ? { rotate: -45, y: -6 } : { rotate: 0, y: 0 }}
          className={`block h-0.5 w-5 rounded-full ${isDark ? "bg-white" : "bg-zinc-800"}`}
        />
      </button>

      {/* Overlay + Menu */}
      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
              className="fixed inset-0 z-[998] bg-black/40 backdrop-blur-sm"
            />

            {/* Slide-in panel */}
            <motion.nav
              initial={{ x: "100%", opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: "100%", opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className={`fixed top-0 right-0 z-[999] h-full w-[280px] shadow-2xl ${
                isDark ? "bg-zinc-900" : "bg-white"
              }`}
            >
              {/* Close button */}
              <div className="flex justify-end p-4">
                <button
                  onClick={() => setOpen(false)}
                  className={`grid h-10 w-10 place-items-center rounded-full text-xl font-bold transition-colors ${
                    isDark
                      ? "text-white hover:bg-zinc-800"
                      : "text-zinc-700 hover:bg-zinc-100"
                  }`}
                  type="button"
                >
                  x
                </button>
              </div>

              {/* Nav items */}
              <div className="flex flex-col px-4 gap-1">
                {items.map((item, i) => (
                  <motion.button
                    key={item.label}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    onClick={() => {
                      item.onClick();
                      setOpen(false);
                    }}
                    className={`flex items-center gap-3 rounded-xl px-4 py-3 text-left text-sm font-semibold transition-all ${
                      item.active
                        ? "bg-[#B8001F]/10 text-[#B8001F]"
                        : isDark
                        ? "text-white hover:bg-zinc-800"
                        : "text-zinc-700 hover:bg-zinc-50"
                    }`}
                    type="button"
                  >
                    {item.active && (
                      <span className="h-2 w-2 rounded-full bg-[#B8001F]" />
                    )}
                    {item.label}
                  </motion.button>
                ))}
              </div>

              {/* Sign out */}
              {onSignOut && (
                <div className="absolute bottom-8 left-4 right-4">
                  <motion.button
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: items.length * 0.05 + 0.1 }}
                    onClick={() => {
                      onSignOut();
                      setOpen(false);
                    }}
                    className="w-full rounded-xl border-2 border-[#B8001F] py-3 text-sm font-bold text-[#B8001F] hover:bg-[#B8001F]/10 transition-colors"
                    type="button"
                  >
                    {t("common.signOut")}
                  </motion.button>
                </div>
              )}
            </motion.nav>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
