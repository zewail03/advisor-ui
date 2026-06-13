"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { adminLogin, setSession, getToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (getToken()) router.replace("/dashboard");
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const r = await adminLogin(username.trim(), password);
      setSession(r.access_token, r.role, r.full_name);
      router.replace("/dashboard");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-4">
      {/* soft animated brand glows */}
      <motion.div
        aria-hidden
        animate={{ scale: [1, 1.15, 1], opacity: [0.25, 0.4, 0.25] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="pointer-events-none absolute -top-32 -left-24 h-80 w-80 rounded-full bg-[#b8001f]/20 blur-3xl"
      />
      <motion.div
        aria-hidden
        animate={{ scale: [1, 1.2, 1], opacity: [0.15, 0.3, 0.15] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-blue-500/15 blur-3xl"
      />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-md"
      >
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <motion.div
            animate={{ y: [0, -5, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          >
            <Image src="/aiu-logo.png" alt="AIU" width={150} height={60} priority className="h-auto w-[150px]" />
          </motion.div>
          <div>
            <h1 className="text-2xl font-bold text-zinc-900">AIU Admin Portal</h1>
            <p className="text-sm text-zinc-500">Sign in to manage the student system</p>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-2xl border border-zinc-200 bg-white/90 p-6 shadow-xl backdrop-blur"
        >
          {err && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-700">Username</label>
            <input
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-[#b8001f] focus:ring-1 focus:ring-[#b8001f]"
              placeholder="admin"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 px-3 py-2 outline-none focus:border-[#b8001f] focus:ring-1 focus:ring-[#b8001f]"
              placeholder="••••••••"
            />
          </div>
          <motion.button
            type="submit"
            disabled={busy || !username || !password}
            whileHover={{ scale: busy ? 1 : 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#b8001f] py-2.5 font-semibold text-white shadow-lg shadow-[#b8001f]/20 transition hover:bg-[#9b0019] disabled:opacity-50"
          >
            {busy && <Loader2 size={16} className="animate-spin" />}
            {busy ? "Signing in…" : "Sign in"}
          </motion.button>
          <p className="text-center text-xs text-zinc-400">
            Demo: admin / admin123 · registrar / registrar123 · viewer / viewer123
          </p>
        </form>
      </motion.div>
    </main>
  );
}
