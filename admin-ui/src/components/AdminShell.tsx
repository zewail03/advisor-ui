"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Users,
  BookOpen,
  CalendarDays,
  Inbox,
  Megaphone,
  SlidersHorizontal,
  ScrollText,
  Sparkles,
  UserCog,
  LogOut,
  type LucideIcon,
} from "lucide-react";
import { getToken, getName, getRole, clearSession } from "@/lib/api";

type NavItem = { href: string; label: string; icon: LucideIcon; superAdminOnly?: boolean };

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/assistant", label: "AI Assistant", icon: Sparkles },
  { href: "/students", label: "Students", icon: Users },
  { href: "/courses", label: "Courses", icon: BookOpen },
  { href: "/offerings", label: "Offerings", icon: CalendarDays },
  { href: "/approvals", label: "Approvals", icon: Inbox },
  { href: "/announcements", label: "Announcements", icon: Megaphone },
  { href: "/rules", label: "Business Rules", icon: SlidersHorizontal },
  { href: "/staff", label: "Staff", icon: UserCog, superAdminOnly: true },
  { href: "/audit", label: "Audit Trail", icon: ScrollText },
];

export default function AdminShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) return null;

  const navItems = NAV.filter((item) => !item.superAdminOnly || getRole() === "super_admin");

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <motion.aside
        initial={{ x: -24, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="flex w-60 shrink-0 flex-col border-r border-zinc-200 bg-white"
      >
        <div className="flex flex-col gap-1.5 border-b border-zinc-100 px-5 py-4">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            <Image src="/aiu-logo.png" alt="AIU" width={104} height={42} priority className="h-auto w-[104px]" />
          </motion.div>
          <span className="text-xs font-medium tracking-wide text-zinc-400">Admin Portal</span>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item, i) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <motion.div
                key={item.href}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.12 + i * 0.04, duration: 0.3 }}
              >
                <Link
                  href={item.href}
                  className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    active ? "text-[#b8001f]" : "text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-lg bg-[#b8001f]/10 ring-1 ring-[#b8001f]/15"
                      transition={{ type: "spring", stiffness: 450, damping: 35 }}
                    />
                  )}
                  <Icon
                    size={18}
                    className="relative z-10 transition-transform duration-200 group-hover:scale-110"
                  />
                  <span className="relative z-10">{item.label}</span>
                </Link>
              </motion.div>
            );
          })}
        </nav>
      </motion.aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <motion.header
          initial={{ y: -16, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="flex items-center justify-end gap-3 border-b border-zinc-200 bg-white/80 px-6 py-3 backdrop-blur"
        >
          <div className="text-right">
            <div className="text-sm font-semibold text-zinc-800">{getName() ?? "Admin"}</div>
            <div className="text-xs capitalize text-zinc-400">{(getRole() ?? "").replace("_", " ")}</div>
          </div>
          <motion.button
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => {
              clearSession();
              router.replace("/");
            }}
            className="flex items-center gap-1 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-600 transition hover:border-[#b8001f]/40 hover:text-[#b8001f]"
          >
            <LogOut size={15} /> Sign out
          </motion.button>
        </motion.header>
        <main className="flex-1 overflow-x-hidden p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

export function canWrite(): boolean {
  const r = getRole();
  return r === "super_admin" || r === "registrar";
}
