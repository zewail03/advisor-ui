"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { getMe, type MeResponse } from "@/lib/api";
import { normalizeErrorMessage } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import ErrorBanner from "@/components/ErrorBanner";
import { DashboardSkeleton } from "@/components/LoadingSkeleton";
import AppLayout from "@/components/layout/AppLayout";
import RecoveryPanel from "@/components/dashboard/RecoveryPanel";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { useLanguage } from "@/hooks/useLanguage";

export default function DashboardPage() {
  const { isDark } = useTheme();
  const { t } = useLanguage();
  const { token, signOut } = useAuth();
  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();

    setErr(null);
    setLoading(true);

    getMe(token, controller.signal)
      .then((d) => setSummary(d))
      .catch((e) => {
        if (controller.signal.aborted) return;
        const msg = normalizeErrorMessage(e, "Failed to load");
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
          signOut();
          return;
        }
        setErr(msg);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [token, signOut]);

  return (
    <AppLayout activePath="/dashboard" userName={summary?.full_name ?? "Loading..."}>
      <main className="relative min-h-[calc(100vh-300px)]">
        <div className="pointer-events-none absolute right-0 top-0 h-[400px] md:h-[600px] w-[50%] md:w-[60%] z-0">
          <Image src="/build.png" alt="AIU Building" fill priority className="object-contain object-right opacity-90" />
        </div>

        <div className="relative z-10 px-4 md:px-8 lg:px-16 py-8 md:py-16">
          <ErrorBanner
            message={err}
            isDark={isDark}
            onDismiss={() => setErr(null)}
            onRetry={() => {
              if (token) {
                setErr(null);
                setLoading(true);
                getMe(token)
                  .then((d) => setSummary(d))
                  .catch((e) => setErr(normalizeErrorMessage(e, "Failed to load")))
                  .finally(() => setLoading(false));
              }
            }}
          />

          {token && <RecoveryPanel token={token} isDark={isDark} />}

          {loading && !summary ? (
            <div className="max-w-full md:max-w-[560px]">
              <DashboardSkeleton isDark={isDark} />
            </div>
          ) : null}

          <div className={`max-w-full md:max-w-[560px] ${loading && !summary ? "hidden" : ""}`}>
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-4 text-[28px] md:text-[40px] font-extrabold leading-tight text-[#B8001F]"
            >
              {t("dash.title")}
            </motion.h1>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className={`mb-5 text-[16px] md:text-[20px] font-bold leading-snug ${isDark ? "text-white" : "text-zinc-900"}`}
            >
              {t("dash.tagline1")}
              <br />
              {t("dash.tagline2")}
            </motion.div>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className={`mb-8 text-[15px] leading-relaxed ${isDark ? "text-zinc-300" : "text-zinc-700"}`}
            >
              {t("dash.desc")}
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="flex flex-wrap items-center gap-3 md:gap-4"
            >
              <Button
                className="h-11 md:h-12 rounded-lg bg-[#B8001F] px-6 md:px-8 text-sm md:text-[15px] font-bold hover:bg-[#A0001A]"
                type="button"
              >
                {t("dash.contact")}
              </Button>
              <Button
                variant="outline"
                onClick={signOut}
                className={`h-11 md:h-12 rounded-lg border-2 border-[#B8001F] px-6 md:px-8 text-sm md:text-[15px] font-bold ${
                  isDark ? "text-[#B8001F] hover:bg-[#B8001F]/10" : "text-[#B8001F] hover:bg-red-50"
                }`}
                type="button"
              >
                {t("common.signOut")}
              </Button>
            </motion.div>
          </div>
        </div>
      </main>
    </AppLayout>
  );
}
