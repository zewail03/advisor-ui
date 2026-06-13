"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Layers,
  CalendarDays,
  Lightbulb,
  Calculator,
  BookOpen,
  GraduationCap,
  Briefcase,
  Wallet,
  UserCircle,
  Settings as SettingsIcon,
  type LucideIcon,
} from "lucide-react";
import { NAV_ITEMS } from "@/lib/constants";
import { useLanguage } from "@/hooks/useLanguage";
import type { TranslationKey } from "@/lib/i18n";

type NavBarProps = {
  isDark: boolean;
  activePath: string;
};

const ICON_MAP: Record<string, LucideIcon> = {
  "/manage-classes/my-classes": Layers,
  "/schedule-generator": CalendarDays,
  "/course-recommendations": Lightbulb,
  "/gpa-simulator": Calculator,
  "/study-plan": BookOpen,
  "/academic-records": GraduationCap,
  "/career": Briefcase,
  "/financial-account": Wallet,
  "/profile": UserCircle,
  "/user-settings": SettingsIcon,
};

export default function NavBar({ isDark, activePath }: NavBarProps) {
  const router = useRouter();
  const { t } = useLanguage();

  return (
    <nav
      className={`hidden lg:flex flex-1 items-center justify-center gap-0.5 xl:gap-1 px-2 py-1.5 rounded-2xl ${
        isDark ? "bg-zinc-800/60" : "bg-white/40 backdrop-blur-sm"
      }`}
    >
      {NAV_ITEMS.map((item) => {
        const isActive = activePath === item.href || activePath.startsWith(item.href + "/");
        const Icon = ICON_MAP[item.href];
        const label = t(`navShort.${item.href}` as TranslationKey);
        return (
          <motion.button
            key={item.href}
            onClick={() => router.push(item.href)}
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.96 }}
            className={`relative px-2.5 xl:px-3 py-1.5 rounded-xl flex flex-col items-center gap-0.5 transition-colors focus:outline-none cursor-pointer ${
              isActive
                ? "text-white"
                : isDark
                ? "text-zinc-300 hover:text-white"
                : "text-zinc-700 hover:text-[#B8001F]"
            }`}
            type="button"
            title={t(`nav.${item.href}` as TranslationKey)}
          >
            {isActive && (
              <motion.span
                layoutId="nav-active-pill"
                className="absolute inset-0 rounded-xl bg-gradient-to-br from-[#B8001F] to-[#7A0015] shadow-md shadow-[#B8001F]/40"
                transition={{ type: "spring", stiffness: 420, damping: 32 }}
              />
            )}
            {Icon && (
              <span className="relative z-10">
                <Icon size={17} strokeWidth={2.2} />
              </span>
            )}
            <span className="relative z-10 text-[10px] xl:text-[11px] font-bold tracking-wide whitespace-nowrap">
              {label}
            </span>
          </motion.button>
        );
      })}
    </nav>
  );
}
