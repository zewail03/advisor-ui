"use client";

import { motion } from "framer-motion";

function Pulse({ className = "" }: { className?: string }) {
  return (
    <motion.div
      className={`rounded-lg bg-zinc-200 dark:bg-zinc-700 ${className}`}
      animate={{ opacity: [0.5, 1, 0.5] }}
      transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
    />
  );
}

export function CardSkeleton({ isDark = false }: { isDark?: boolean }) {
  return (
    <div
      className={`rounded-xl border p-6 ${
        isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"
      }`}
    >
      <Pulse className="mb-4 h-4 w-1/3" />
      <Pulse className="mb-3 h-8 w-2/3" />
      <Pulse className="h-3 w-1/2" />
    </div>
  );
}

export function TableSkeleton({ rows = 5, isDark = false }: { rows?: number; isDark?: boolean }) {
  return (
    <div
      className={`rounded-xl border overflow-hidden ${
        isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"
      }`}
    >
      <div className={`p-4 ${isDark ? "bg-zinc-800" : "bg-zinc-50"}`}>
        <Pulse className="h-4 w-1/4" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`flex items-center gap-4 border-t p-4 ${
            isDark ? "border-zinc-800" : "border-zinc-100"
          }`}
        >
          <Pulse className="h-4 w-1/6" />
          <Pulse className="h-4 w-1/3" />
          <Pulse className="h-4 w-1/6" />
          <Pulse className="h-4 w-1/6" />
        </div>
      ))}
    </div>
  );
}

export function ProfileSkeleton({ isDark = false }: { isDark?: boolean }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <motion.div
          className={`h-20 w-20 rounded-full ${isDark ? "bg-zinc-700" : "bg-zinc-200"}`}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="space-y-2 flex-1">
          <Pulse className="h-5 w-1/3" />
          <Pulse className="h-4 w-1/4" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Pulse className="h-3 w-1/3" />
            <Pulse className="h-10 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardSkeleton({ isDark = false }: { isDark?: boolean }) {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <Pulse className="h-10 w-2/3" />
        <Pulse className="h-6 w-1/2" />
        <Pulse className="h-20 w-full max-w-xl" />
      </div>
      <div className="flex gap-4">
        <Pulse className="h-12 w-48 rounded-lg" />
        <Pulse className="h-12 w-36 rounded-lg" />
      </div>
    </div>
  );
}

export function FinancialSkeleton({ isDark = false }: { isDark?: boolean }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <CardSkeleton key={i} isDark={isDark} />
        ))}
      </div>
      <TableSkeleton rows={4} isDark={isDark} />
    </div>
  );
}

export default Pulse;
