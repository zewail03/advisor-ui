"use client";

import Image from "next/image";
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { getMe, changePassword, get2faStatus, sendOtp, enable2fa, disable2fa, type MeResponse } from "@/lib/api";
import { normalizeErrorMessage, isAbortError } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ErrorBanner from "@/components/ErrorBanner";
import AppLayout from "@/components/layout/AppLayout";
import PageContainer from "@/components/layout/PageContainer";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { useLanguage } from "@/hooks/useLanguage";

export default function UserSettingsPage() {
  const { isDark } = useTheme();
  const { t, lang, setLanguage } = useLanguage();
  const { token, signOut } = useAuth();

  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const [formMsg, setFormMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPasswordError, setShowPasswordError] = useState(false);

  // Two-factor auth (server-generated login OTP)
  const [twofaEnabled, setTwofaEnabled] = useState<boolean | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [disarming, setDisarming] = useState(false);
  const [sentCode, setSentCode] = useState<string | null>(null);
  const [twofaCode, setTwofaCode] = useState("");
  const [twofaBusy, setTwofaBusy] = useState(false);
  const [twofaMsg, setTwofaMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    get2faStatus(token).then((s) => setTwofaEnabled(!!s.enabled)).catch(() => setTwofaEnabled(false));
  }, [token]);

  async function sendCode(mode: "enroll" | "disarm") {
    if (!token) return;
    setTwofaMsg(null);
    setTwofaBusy(true);
    try {
      const d = await sendOtp(token);
      setSentCode(d.demo_code ?? null);
      setTwofaCode("");
      setEnrolling(mode === "enroll");
      setDisarming(mode === "disarm");
    } catch (e) {
      setTwofaMsg(normalizeErrorMessage(e, "Could not send code"));
    } finally {
      setTwofaBusy(false);
    }
  }

  function resetTwofaFlow() {
    setEnrolling(false);
    setDisarming(false);
    setSentCode(null);
    setTwofaCode("");
  }

  async function confirmTwofa() {
    if (!token || twofaCode.trim().length < 6) return;
    setTwofaMsg(null);
    setTwofaBusy(true);
    try {
      await enable2fa(token, twofaCode.trim());
      setTwofaEnabled(true);
      resetTwofaFlow();
      setTwofaMsg("✅ Two-factor authentication is now on.");
    } catch (e) {
      setTwofaMsg(normalizeErrorMessage(e, "That code didn't match. Try again."));
    } finally {
      setTwofaBusy(false);
    }
  }

  async function turnOffTwofa() {
    if (!token || twofaCode.trim().length < 6) return;
    setTwofaMsg(null);
    setTwofaBusy(true);
    try {
      await disable2fa(token, twofaCode.trim());
      setTwofaEnabled(false);
      resetTwofaFlow();
      setTwofaMsg("Two-factor authentication turned off.");
    } catch (e) {
      setTwofaMsg(normalizeErrorMessage(e, "Invalid code."));
    } finally {
      setTwofaBusy(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    getMe(token, controller.signal)
      .then((d) => {
        if (!controller.signal.aborted) setSummary(d);
      })
      .catch((e) => {
        if (isAbortError(e) || controller.signal.aborted) return;
        const msg = normalizeErrorMessage(e, "Failed to load");
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
          signOut();
          return;
        }
        setErr(msg);
      });
    return () => controller.abort();
  }, [token, signOut]);

  useEffect(() => {
    if (newPass.length > 0 && newPass.length < 8) setShowPasswordError(true);
    else setShowPasswordError(false);
  }, [newPass]);

  async function onSubmitChangePassword() {
    setFormMsg(null);

    if (!currentPass.trim() || !newPass.trim() || !confirmPass.trim()) {
      setFormMsg(t("settings.fillAll"));
      return;
    }
    if (newPass.length < 8) {
      setFormMsg(t("settings.min8"));
      return;
    }
    if (newPass !== confirmPass) {
      setFormMsg(t("settings.noMatch"));
      return;
    }

    if (!token) {
      signOut();
      return;
    }

    setIsSubmitting(true);
    try {
      await changePassword(token, currentPass, newPass);
      setFormMsg(t("settings.success"));
      setCurrentPass("");
      setNewPass("");
      setConfirmPass("");
    } catch (error: unknown) {
      const msg = normalizeErrorMessage(error, "Please try again.");
      if (
        msg.toLowerCase().includes("incorrect") ||
        msg.toLowerCase().includes("wrong") ||
        msg.toLowerCase().includes("current password")
      ) {
        setFormMsg(t("settings.failedCheck"));
      } else {
        setFormMsg("\u274C Failed. " + msg);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AppLayout activePath="/user-settings" userName={summary?.full_name ?? "Loading..."}>
      <main className="relative flex-1 w-full overflow-hidden">
        <Image src="/aiu-bg.png" alt="AIU Background" fill priority className="object-cover object-bottom" />

        <div
          className="absolute inset-0"
          style={{
            background: isDark
              ? "linear-gradient(to bottom, rgba(0,0,0,0.85), rgba(0,0,0,0.88))"
              : "linear-gradient(to bottom, rgba(255,255,255,0.78), rgba(255,255,255,0.72))",
          }}
        />

        <div className="relative z-10 w-full px-4 py-10 md:py-12 flex justify-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="w-full max-w-md mx-auto box-border"
          >
            <div
              className={`w-full box-border overflow-hidden rounded-2xl border ${
                isDark ? "bg-zinc-900 border-zinc-700" : "bg-white border-zinc-200"
              }`}
            >
              <div className={`px-6 md:px-8 py-5 text-center border-b ${isDark ? "border-zinc-800" : "border-zinc-200"}`}>
                <h1 className="text-sm md:text-base font-extrabold text-[#B8001F]">{t("settings.changePassword")}</h1>
                <div className={`mt-1 space-y-0.5 text-xs ${isDark ? "text-zinc-200" : "text-zinc-600"}`}>
                  <p className="font-semibold">
                    {t("settings.userId")}{" "}
                    <span className={isDark ? "text-white" : "text-zinc-900"}>{summary?.student_number ?? "22101901"}</span>
                  </p>
                  <p className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                    {summary?.full_name ?? "Mohamed Mohamed Ibrahim El Sariti"}
                  </p>
                </div>
              </div>

              <div className="px-6 md:px-8 py-6 box-border">
                <div className="w-full space-y-4">
                  {/* Language preference */}
                  <div className={`flex items-center justify-between rounded-lg border px-3 py-2.5 ${isDark ? "border-zinc-700" : "border-zinc-200"}`}>
                    <span className={`text-sm font-semibold ${isDark ? "text-zinc-200" : "text-zinc-700"}`}>
                      {t("common.language")}
                    </span>
                    <div className="flex gap-1">
                      {(["en", "ar"] as const).map((l) => (
                        <button
                          key={l}
                          type="button"
                          onClick={() => setLanguage(l)}
                          className={`rounded-md px-3 py-1 text-xs font-bold transition-colors ${
                            lang === l
                              ? "bg-[#B8001F] text-white"
                              : isDark
                              ? "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                              : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
                          }`}
                        >
                          {l === "en" ? "English" : "العربية"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className={`block mb-2 text-sm font-semibold ${isDark ? "text-zinc-200" : "text-zinc-700"}`}>
                      {t("settings.current")} <span className="text-[#B8001F]">*</span>
                    </label>
                    <Input
                      type="password"
                      value={currentPass}
                      onChange={(e) => setCurrentPass(e.target.value)}
                      className={`h-11 w-full text-sm box-border ${
                        isDark ? "bg-zinc-800/70 border-zinc-700 text-white" : "bg-white border-zinc-300"
                      }`}
                      autoComplete="current-password"
                    />
                  </div>

                  <div>
                    <label className={`block mb-2 text-sm font-semibold ${isDark ? "text-zinc-200" : "text-zinc-700"}`}>
                      {t("settings.new")} <span className="text-[#B8001F]">*</span>
                    </label>
                    <Input
                      type="password"
                      value={newPass}
                      onChange={(e) => setNewPass(e.target.value)}
                      className={`h-11 w-full text-sm box-border ${
                        isDark ? "bg-zinc-800/70 border-zinc-700 text-white" : "bg-white border-zinc-300"
                      }`}
                      autoComplete="new-password"
                    />
                    {newPass.length > 0 && (
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}>
                        <div className="flex gap-1 mt-1">
                          {[1, 2, 3, 4].map((level) => (
                            <div
                              key={level}
                              className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
                                newPass.length >= level * 3
                                  ? level <= 1
                                    ? "bg-red-400"
                                    : level <= 2
                                    ? "bg-orange-400"
                                    : level <= 3
                                    ? "bg-yellow-400"
                                    : "bg-green-500"
                                  : isDark
                                  ? "bg-zinc-700"
                                  : "bg-zinc-200"
                              }`}
                            />
                          ))}
                        </div>
                        <p
                          className={`text-xs mt-1 ${
                            newPass.length >= 12 ? "text-green-500" : newPass.length >= 8 ? "text-yellow-500" : "text-red-400"
                          }`}
                        >
                          {newPass.length >= 12 ? t("settings.strong") : newPass.length >= 8 ? t("settings.good") : t("settings.tooShort")}
                        </p>
                      </motion.div>
                    )}
                  </div>

                  <div>
                    <label className={`block mb-2 text-sm font-semibold ${isDark ? "text-zinc-200" : "text-zinc-700"}`}>
                      {t("settings.confirm")} <span className="text-[#B8001F]">*</span>
                    </label>
                    <div className="relative">
                      <Input
                        type="password"
                        value={confirmPass}
                        onChange={(e) => setConfirmPass(e.target.value)}
                        className={`h-11 w-full text-sm box-border ${
                          isDark ? "bg-zinc-800/70 border-zinc-700 text-white" : "bg-white border-zinc-300"
                        }`}
                        autoComplete="new-password"
                      />
                      {confirmPass.length > 0 && (
                        <span
                          className={`absolute right-3 top-1/2 -translate-y-1/2 text-lg font-bold ${
                            confirmPass === newPass ? "text-green-500" : "text-red-500"
                          }`}
                        >
                          {confirmPass === newPass ? "\u2713" : "\u2717"}
                        </span>
                      )}
                    </div>
                  </div>

                  <AnimatePresence>
                    {showPasswordError && (
                      <motion.p
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="text-xs text-[#B8001F] font-semibold"
                      >
                        {t("settings.min8")}
                      </motion.p>
                    )}
                  </AnimatePresence>

                  <AnimatePresence>
                    {formMsg && (
                      <motion.div
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        className={`rounded-md px-3 py-2 text-sm font-semibold text-center ${
                          formMsg.startsWith("\u2705")
                            ? "bg-green-50 text-green-700 border border-green-200"
                            : "bg-red-50 text-red-700 border border-red-200"
                        }`}
                      >
                        {formMsg}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="pt-2">
                    <Button
                      onClick={onSubmitChangePassword}
                      disabled={isSubmitting}
                      type="button"
                      className="h-12 w-full rounded-md bg-red-600 hover:bg-red-700 text-white text-base font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                    >
                      {isSubmitting ? t("settings.changing") : t("settings.changePassword")}
                    </Button>
                  </div>

                  {/* Two-Factor Authentication */}
                  <div className={`rounded-lg border p-4 ${isDark ? "border-zinc-700" : "border-zinc-200"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <div className={`text-sm font-bold ${isDark ? "text-zinc-100" : "text-zinc-800"}`}>
                          🔐 Two-Factor Authentication
                        </div>
                        <div className="mt-0.5 text-xs text-zinc-500">
                          Require a one-time code at login (sent to you).
                        </div>
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                          twofaEnabled
                            ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
                            : isDark
                            ? "bg-zinc-800 text-zinc-400"
                            : "bg-zinc-100 text-zinc-500"
                        }`}
                      >
                        {twofaEnabled === null ? "…" : twofaEnabled ? "ON" : "OFF"}
                      </span>
                    </div>

                    {twofaEnabled && !disarming && (
                      <Button
                        onClick={() => sendCode("disarm")}
                        disabled={twofaBusy}
                        type="button"
                        className="mt-3 h-9 w-full rounded-md bg-zinc-200 text-sm font-semibold text-zinc-800 hover:bg-zinc-300 disabled:opacity-60 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
                      >
                        {twofaBusy ? "Sending code…" : "Turn off"}
                      </Button>
                    )}

                    {twofaEnabled === false && !enrolling && (
                      <Button
                        onClick={() => sendCode("enroll")}
                        disabled={twofaBusy}
                        type="button"
                        className="mt-3 h-9 w-full rounded-md bg-red-600 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                      >
                        {twofaBusy ? "Sending code…" : "Enable"}
                      </Button>
                    )}

                    {(enrolling || disarming) && (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs text-zinc-500">
                          We sent a 6-digit code. Enter it to {enrolling ? "turn on" : "turn off"} 2FA.
                        </p>
                        {sentCode && (
                          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-center text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
                            Demo code (would be emailed):{" "}
                            <span className="font-mono text-sm font-bold tracking-widest">{sentCode}</span>
                          </div>
                        )}
                        <Input
                          value={twofaCode}
                          onChange={(e) => setTwofaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                          inputMode="numeric"
                          maxLength={6}
                          placeholder="123456"
                          className="h-10 text-center font-bold tracking-[0.4em]"
                        />
                        <div className="flex gap-2">
                          <Button
                            onClick={enrolling ? confirmTwofa : turnOffTwofa}
                            disabled={twofaBusy || twofaCode.length < 6}
                            type="button"
                            className="h-9 flex-1 rounded-md bg-red-600 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                          >
                            {enrolling ? "Confirm" : "Confirm off"}
                          </Button>
                          <Button onClick={resetTwofaFlow} type="button" className="h-9 flex-1 rounded-md bg-zinc-200 text-sm text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">Cancel</Button>
                        </div>
                      </div>
                    )}

                    {twofaMsg && (
                      <div className="mt-3 rounded-md bg-zinc-50 px-3 py-2 text-center text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                        {twofaMsg}
                      </div>
                    )}
                  </div>

                  <div className={`pt-1 text-center text-xs ${isDark ? "text-zinc-300" : "text-zinc-500"}`}>
                    {t("settings.terms")}
                  </div>

                  {err ? <ErrorBanner message={err} isDark={isDark} onDismiss={() => setErr(null)} /> : null}
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </main>
    </AppLayout>
  );
}
