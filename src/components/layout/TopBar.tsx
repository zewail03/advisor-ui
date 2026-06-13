"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import MobileMenu from "@/components/MobileMenu";
import NavBar from "./NavBar";
import ProfilePill from "./ProfilePill";
import NotificationsDropdown from "./NotificationsDropdown";
import { NAV_ITEMS } from "@/lib/constants";
import { useLanguage } from "@/hooks/useLanguage";
import type { TranslationKey } from "@/lib/i18n";

type TopBarProps = {
  isDark: boolean;
  toggleTheme: () => void;
  signOut: () => void;
  activePath: string;
  userName?: string | null;
  avatarDataUrl: string | null;
};

export default function TopBar({
  isDark,
  toggleTheme,
  signOut,
  activePath,
  userName,
  avatarDataUrl,
}: TopBarProps) {
  const router = useRouter();
  const { t, isAr, toggleLanguage } = useLanguage();

  const mobileItems = [
    {
      label: t("nav./dashboard"),
      onClick: () => router.push("/dashboard"),
      active: activePath === "/dashboard",
    },
    ...NAV_ITEMS.map((item) => ({
      label: t(`nav.${item.href}` as TranslationKey),
      onClick: () => router.push(item.href),
      active: activePath === item.href || activePath.startsWith(item.href + "/"),
    })),
  ];

  return (
    <header className="sticky top-0 z-50">
      <div
        className={`${isDark ? "bg-zinc-900/95" : "bg-[#d9d9d9]"} backdrop-blur-sm pb-4 md:pb-5`}
        style={{
          borderBottomLeftRadius: "50% 30px",
          borderBottomRightRadius: "50% 30px",
        }}
      >
        <div className="px-4 md:px-6 lg:px-10 py-3 md:py-3">
          {/* Top row */}
          <div className="flex items-center gap-3 md:gap-6">
            {/* Logo */}
            <button onClick={() => router.push("/dashboard")} className="shrink-0" type="button">
              <Image
                src="/aiu-header-logo.svg"
                alt="AIU"
                width={150}
                height={52}
                priority
                className="md:w-[170px] md:h-[58px]"
              />
            </button>

            {/* Navigation */}
            <NavBar isDark={isDark} activePath={activePath} />

            {/* Right Actions */}
            <div className="flex items-center gap-3">
              {/* Mobile Menu */}
              <MobileMenu isDark={isDark} onSignOut={signOut} items={mobileItems} />

              {/* Language */}
              <button
                onClick={toggleLanguage}
                title={t("common.language")}
                className={`grid h-10 w-10 place-items-center rounded-full text-sm font-extrabold ${
                  isDark ? "bg-zinc-800 text-zinc-100" : "bg-white text-zinc-800"
                } shadow-sm hover:opacity-80 transition-opacity`}
                type="button"
              >
                {isAr ? "EN" : "ع"}
              </button>

              {/* Theme */}
              <button
                onClick={toggleTheme}
                className={`grid h-10 w-10 place-items-center rounded-full ${
                  isDark ? "bg-zinc-800" : "bg-white"
                } shadow-sm hover:opacity-80 transition-opacity`}
                type="button"
              >
                <Image src={isDark ? "/icon.svg" : "/dark.svg"} alt="theme" width={20} height={20} />
              </button>

              {/* Notifications */}
              <NotificationsDropdown isDark={isDark} />

              {/* Profile */}
              <ProfilePill isDark={isDark} userName={userName} avatarDataUrl={avatarDataUrl} />
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
