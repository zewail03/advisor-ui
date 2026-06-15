// src/app/page.tsx
"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Lang = "en" | "ar";

const copy = {
  en: {
    title: "We will connect to your university account",
    subtitle: "Please enter the required information.",
    studentId: "Student ID",
    password: "Password",
    language: "Select a Language",
    login: "Login to Account",
    demo: "Sign in with any student ID, e.g. 25100045 / changeme123",
    terms: "By logging in, you agree to the usage policy and terms of service.",
    support: "Contact the Support Center",
    invalid: "Invalid credentials",
    loading: "Loading...",
    placeholderId: "e.g. 25100045",
    placeholderPass: "Enter your password",
    required: "Please enter Student ID and Password",
    backendDown:
      "Cannot reach the backend server. Make sure FastAPI is running on http://127.0.0.1:8000 (or set NEXT_PUBLIC_API_URL).",
    twoFATitle: "Two-Factor Authentication",
    twoFASub: "Enter the 6-digit code we just sent you.",
    twoFAPlaceholder: "123456",
    verify: "Verify",
    twoFABack: "← Use a different account",
    twoFAInvalid: "Invalid or expired code",
    twoFADemo: "Demo code (would be emailed):",
  },
  ar: {
    title: "سنقوم بالاتصال بحسابك الجامعي",
    subtitle: "يرجى إدخال البيانات المطلوبة.",
    studentId: "رقم الطالب",
    password: "كلمة المرور",
    language: "اختر اللغة",
    login: "تسجيل الدخول",
    demo: "سجّل الدخول بأي رقم طالب، مثال: 25100045 / changeme123",
    terms: "بتسجيل الدخول، أنت توافق على سياسة الاستخدام وشروط الخدمة.",
    support: "تواصل مع مركز الدعم",
    invalid: "بيانات الدخول غير صحيحة",
    loading: "جاري التحميل...",
    placeholderId: "مثال: 25100045",
    placeholderPass: "أدخل كلمة المرور",
    required: "من فضلك أدخل رقم الطالب وكلمة المرور",
    backendDown:
      "لا يمكن الاتصال بسيرفر الباك اند. تأكد أن FastAPI شغال على http://127.0.0.1:8000 (أو اضبط NEXT_PUBLIC_API_URL).",
    twoFATitle: "المصادقة الثنائية",
    twoFASub: "أدخل الرمز المكون من 6 أرقام من تطبيق المصادقة.",
    twoFAPlaceholder: "123456",
    verify: "تحقق",
    twoFABack: "← استخدم حسابًا آخر",
    twoFAInvalid: "رمز غير صحيح أو منتهي الصلاحية",
    twoFADemo: "رمز العرض التجريبي (يُرسَل بالبريد عادةً):",
  },
};

function extractFastApiError(err: unknown, fallback: string) {
  // Network errors from fetch usually come as TypeError("Failed to fetch")
  if (err instanceof TypeError) return fallback;

  if (err instanceof Error) return err.message || fallback;

  if (typeof err === "object" && err !== null) {
    const anyErr = err as any;
    if (typeof anyErr.detail === "string") return anyErr.detail;
    if (Array.isArray(anyErr.detail) && anyErr.detail?.[0]?.msg)
      return String(anyErr.detail[0].msg);
    if (typeof anyErr.message === "string") return anyErr.message;
  }

  return fallback;
}

export default function LoginPage() {
  const router = useRouter();
  const { signIn, completeTwoFactor } = useAuth();

  const { lang, setLanguage } = useLanguage();
  const t = useMemo(() => copy[lang], [lang]);
  const dir = lang === "ar" ? "rtl" : "ltr";

  const [studentId, setStudentId] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [shakeKey, setShakeKey] = useState(0);
  const [success, setSuccess] = useState(false);

  // Two-factor second step
  const [twoFAChallenge, setTwoFAChallenge] = useState<string | null>(null);
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [code, setCode] = useState("");

  async function finishLogin() {
    setSuccess(true);
    await new Promise((r) => setTimeout(r, 600));
    router.push("/dashboard");
  }

  async function onVerify(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const c = code.trim();
    if (!c || !twoFAChallenge) {
      setErr(t.twoFAInvalid);
      setShakeKey((k) => k + 1);
      return;
    }
    setLoading(true);
    try {
      await completeTwoFactor(twoFAChallenge, c);
      await finishLogin();
    } catch (e: unknown) {
      setErr(extractFastApiError(e, t.twoFAInvalid));
      setShakeKey((k) => k + 1);
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);

    const sid = studentId.trim();
    const pass = password;

    if (!sid || !pass) {
      setErr(t.required);
      setShakeKey((k) => k + 1);
      return;
    }

    setLoading(true);
    try {
      const r = await signIn(sid, pass);
      localStorage.setItem("advisor_student_id", sid);

      if (r.twofaRequired) {
        setTwoFAChallenge(r.challengeToken);
        setDemoCode(r.demoCode ?? null);
        setCode("");
        return; // show the code step (finally clears loading)
      }

      await finishLogin();
    } catch (e: unknown) {
      // If backend is down / CORS / wrong URL → show backendDown
      const msg = extractFastApiError(e, t.invalid);

      // Heuristic: if it smells like a network error, show backendDown
      const looksLikeNetwork =
        (e instanceof TypeError) ||
        (typeof msg === "string" &&
          /failed to fetch|network|cors|load failed|fetch/i.test(msg));

      setErr(looksLikeNetwork ? t.backendDown : msg);
      setShakeKey((k) => k + 1);
    } finally {
      setLoading(false);
    }
  }

  function goSupport() {
    window.open("https://www.google.com", "_blank", "noopener,noreferrer");
  }

  return (
    <div dir={dir} className="relative min-h-screen w-full overflow-hidden bg-white dark:bg-zinc-900">
      {/* Full-page background */}
      <Image
        src="/aiu-bg.png"
        alt="AIU background"
        fill
        priority
        className="object-cover object-bottom"
      />

      {/* Soft overlay to keep card readable */}
      <div className="absolute inset-0 bg-white/75" />

      {/* Top-right Support Button */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
        className="fixed right-6 top-6 z-20"
      >
        <Button
          onClick={goSupport}
          className="rounded-md bg-red-600 px-5 py-2 font-medium hover:bg-red-700 hover:shadow-lg transition-shadow"
        >
          {t.support}
        </Button>
      </motion.div>

      {/* Center content */}
      <div className="relative z-10 flex min-h-screen items-center justify-center px-4">
        <motion.div
          key={shakeKey}
          initial={{ opacity: 0, y: 18 }}
          animate={
            err && shakeKey > 0
              ? { opacity: 1, y: 0, x: [0, -10, 10, -10, 10, 0] }
              : success
              ? { opacity: 1, y: 0, scale: [1, 1.02, 0.95], transition: { duration: 0.5 } }
              : { opacity: 1, y: 0 }
          }
          transition={{ duration: 0.45, ease: "easeOut" }}
          className="w-full max-w-md"
        >
          <Card className="border-zinc-200/70 shadow-xl hover:shadow-2xl transition-shadow duration-500">
            <CardContent className="p-8">
              {/* Logo + text */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1, duration: 0.4 }}
                className="flex flex-col items-center gap-3 pb-4"
              >
                <motion.div
                  animate={{ y: [0, -3, 0] }}
                  transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                >
                  <Image src="/aiu-logo.png" alt="AIU" width={110} height={44} priority />
                </motion.div>
                <div className="text-center">
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t.title}</p>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">{t.subtitle}</p>
                </div>
              </motion.div>

              {!twoFAChallenge ? (
              <form onSubmit={onSubmit} className="space-y-4">
                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.15 }}
                  className="space-y-2"
                >
                  <Label className="text-sm text-zinc-700 dark:text-zinc-300">{t.studentId}</Label>
                  <Input
                    value={studentId}
                    onChange={(e) => { setStudentId(e.target.value); setErr(null); }}
                    placeholder={t.placeholderId}
                    className={`h-11 transition-all duration-200 ${
                      err && !studentId.trim() ? "border-red-400 ring-1 ring-red-200" : "focus:border-[#B8001F] focus:ring-1 focus:ring-[#B8001F]/20"
                    }`}
                    autoComplete="username"
                    inputMode="numeric"
                  />
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 }}
                  className="space-y-2"
                >
                  <Label className="text-sm text-zinc-700 dark:text-zinc-300">{t.password}</Label>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setErr(null); }}
                    placeholder={t.placeholderPass}
                    className={`h-11 transition-all duration-200 ${
                      err && !password ? "border-red-400 ring-1 ring-red-200" : "focus:border-[#B8001F] focus:ring-1 focus:ring-[#B8001F]/20"
                    }`}
                    autoComplete="current-password"
                  />
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.25 }}
                  className="space-y-2"
                >
                  <Label className="text-sm text-zinc-700 dark:text-zinc-300">{t.language}</Label>
                  <Select value={lang} onValueChange={(v) => setLanguage(v as Lang)}>
                    <SelectTrigger className="h-11">
                      <SelectValue placeholder={t.language} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="ar">العربية</SelectItem>
                    </SelectContent>
                  </Select>
                </motion.div>

                <AnimatePresence mode="wait">
                  {err && (
                    <motion.div
                      initial={{ opacity: 0, height: 0, y: -5 }}
                      animate={{ opacity: 1, height: "auto", y: 0 }}
                      exit={{ opacity: 0, height: 0, y: -5 }}
                      className="overflow-hidden rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-3 py-2 text-sm text-red-700 dark:text-red-300"
                    >
                      {err}
                    </motion.div>
                  )}
                  {success && (
                    <motion.div
                      initial={{ opacity: 0, height: 0, scale: 0.95 }}
                      animate={{ opacity: 1, height: "auto", scale: 1 }}
                      className="overflow-hidden rounded-md border border-green-200 bg-green-50 dark:bg-green-950/40 px-3 py-2 text-sm text-green-700 dark:text-green-300 text-center font-medium"
                    >
                      Login successful! Redirecting...
                    </motion.div>
                  )}
                </AnimatePresence>

                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                >
                  <Button
                    type="submit"
                    disabled={loading || success}
                    className="h-12 w-full rounded-md bg-red-600 text-base font-semibold hover:bg-red-700 hover:shadow-lg transition-all duration-200 disabled:opacity-60"
                  >
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <motion.span
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                          className="inline-block h-4 w-4 rounded-full border-2 border-white/30 border-t-white"
                        />
                        {t.loading}
                      </span>
                    ) : success ? (
                      <motion.span
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 300 }}
                      >
                        ✓
                      </motion.span>
                    ) : (
                      t.login
                    )}
                  </Button>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4 }}
                  className="pt-2 text-center text-xs text-zinc-500 dark:text-zinc-400"
                >
                  <p>{t.demo}</p>
                  <p className="mt-1">{t.terms}</p>
                </motion.div>
              </form>
              ) : (
              <form onSubmit={onVerify} className="space-y-4">
                <div className="space-y-1 pb-1 text-center">
                  <div className="mx-auto mb-2 grid h-12 w-12 place-items-center rounded-full bg-red-50 dark:bg-red-950/40 text-2xl">🔐</div>
                  <p className="text-base font-semibold text-zinc-800 dark:text-zinc-100">{t.twoFATitle}</p>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">{t.twoFASub}</p>
                </div>

                {demoCode && (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-center text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
                    {t.twoFADemo} <span className="font-mono text-base font-bold tracking-widest">{demoCode}</span>
                  </div>
                )}

                <Input
                  value={code}
                  onChange={(e) => { setCode(e.target.value.replace(/\D/g, "").slice(0, 6)); setErr(null); }}
                  placeholder={t.twoFAPlaceholder}
                  inputMode="numeric"
                  autoFocus
                  maxLength={6}
                  className="h-12 text-center text-2xl font-bold tracking-[0.5em]"
                />

                <AnimatePresence mode="wait">
                  {err && (
                    <motion.div
                      initial={{ opacity: 0, height: 0, y: -5 }}
                      animate={{ opacity: 1, height: "auto", y: 0 }}
                      exit={{ opacity: 0, height: 0, y: -5 }}
                      className="overflow-hidden rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-3 py-2 text-sm text-red-700 dark:text-red-300"
                    >
                      {err}
                    </motion.div>
                  )}
                  {success && (
                    <motion.div
                      initial={{ opacity: 0, height: 0, scale: 0.95 }}
                      animate={{ opacity: 1, height: "auto", scale: 1 }}
                      className="overflow-hidden rounded-md border border-green-200 bg-green-50 dark:bg-green-950/40 px-3 py-2 text-center text-sm font-medium text-green-700 dark:text-green-300"
                    >
                      Login successful! Redirecting...
                    </motion.div>
                  )}
                </AnimatePresence>

                <Button
                  type="submit"
                  disabled={loading || success || code.length < 6}
                  className="h-12 w-full rounded-md bg-red-600 text-base font-semibold hover:bg-red-700 hover:shadow-lg transition-all duration-200 disabled:opacity-60"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <motion.span
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                        className="inline-block h-4 w-4 rounded-full border-2 border-white/30 border-t-white"
                      />
                      {t.loading}
                    </span>
                  ) : success ? "✓" : t.verify}
                </Button>

                <button
                  type="button"
                  onClick={() => { setTwoFAChallenge(null); setDemoCode(null); setCode(""); setErr(null); }}
                  className="block w-full pt-1 text-center text-xs text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                >
                  {t.twoFABack}
                </button>
              </form>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
