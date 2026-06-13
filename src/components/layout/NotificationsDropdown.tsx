"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useAppLayout } from "./AppLayoutContext";
import { useNotifications, type Notification } from "@/hooks/useNotifications";
import { useLanguage } from "@/hooks/useLanguage";

type NotificationsDropdownProps = {
  isDark: boolean;
};

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (!then || Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export default function NotificationsDropdown({ isDark }: NotificationsDropdownProps) {
  const { token } = useAppLayout();
  const { t } = useLanguage();
  const router = useRouter();
  const { items, loading, refresh, markRead, markAllRead, unreadCount } = useNotifications(token);

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (!open) return;
      const t = e.target as Node;
      if (ref.current && ref.current.contains(t)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const badge = useMemo(() => (unreadCount > 9 ? "9+" : String(unreadCount)), [unreadCount]);

  function handleToggle() {
    setOpen((v) => {
      const next = !v;
      if (next) refresh();
      return next;
    });
  }

  function handleItemClick(n: Notification) {
    if (!n.read) markRead(n.id);
    if (n.link) {
      setOpen(false);
      router.push(n.link);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleToggle}
        className={`grid h-10 w-10 place-items-center rounded-full ${
          isDark ? "bg-zinc-800" : "bg-white"
        } shadow-sm hover:opacity-80 transition-opacity`}
        type="button"
        aria-label="Notifications"
      >
        <Image src="/bell.svg" alt="bell" width={18} height={18} />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[#B8001F] px-1 text-[10px] font-bold text-white">
            {badge}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className={`absolute right-0 top-full mt-3 w-[320px] rounded-xl border ${
              isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"
            } shadow-2xl z-[9999] max-h-[400px] overflow-y-auto`}
          >
            <div
              className={`flex items-center justify-between px-4 py-3 text-sm font-semibold border-b ${
                isDark ? "text-white border-zinc-800" : "text-zinc-900 border-zinc-200"
              }`}
            >
              <span>{t("notif.title")}</span>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={markAllRead}
                  className="text-xs font-medium text-[#B8001F] hover:underline"
                >{t("notif.markAll")}</button>
              )}
            </div>

            {loading && items.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-zinc-500">{t("common.loading")}</div>
            ) : items.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-zinc-500">{t("notif.empty")}</div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleItemClick(n)}
                  type="button"
                  className={`block w-full text-left border-b px-4 py-3 transition-colors ${
                    isDark ? "border-zinc-800 hover:bg-zinc-800" : "border-zinc-100 hover:bg-zinc-50"
                  } ${n.read ? "opacity-70" : ""}`}
                >
                  <div className="flex items-start gap-2">
                    {!n.read && (
                      <span className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full bg-[#B8001F]" />
                    )}
                    <div className="flex-1">
                      <div
                        className={`text-sm font-medium ${
                          isDark ? "text-white" : "text-zinc-900"
                        }`}
                      >
                        {n.title}
                      </div>
                      {n.message && (
                        <div
                          className={`mt-0.5 text-xs ${
                            isDark ? "text-zinc-400" : "text-zinc-600"
                          } line-clamp-2`}
                        >
                          {n.message}
                        </div>
                      )}
                      <div className="mt-1 text-xs text-zinc-500">
                        {formatRelative(n.created_at)}
                      </div>
                    </div>
                  </div>
                </button>
              ))
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
