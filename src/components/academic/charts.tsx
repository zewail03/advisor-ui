"use client";

import { motion, animate } from "framer-motion";
import { useEffect, useState } from "react";

/* ── Shared helpers ──────────────────────────────────────── */

export function fmtNum(n: number | null | undefined, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toFixed(digits);
}

function useCountUp(target: number, duration = 1.4) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const controls = animate(0, target, {
      duration,
      ease: [0.2, 0.8, 0.2, 1],
      onUpdate: (v) => setDisplay(v),
    });
    return () => controls.stop();
  }, [target, duration]);
  return display;
}

export function gpaTone(gpa: number | null | undefined) {
  const x = typeof gpa === "number" ? gpa : null;
  if (x === null)
    return {
      stroke: "stroke-zinc-300 dark:stroke-zinc-600",
      text: "text-zinc-600 dark:text-zinc-400",
      fill: "#d4d4d8",
    };
  if (x >= 3.5)
    return {
      stroke: "stroke-green-600 dark:stroke-green-500",
      text: "text-green-600 dark:text-green-400",
      fill: "#16a34a",
    };
  if (x >= 2.5)
    return {
      stroke: "stroke-amber-500 dark:stroke-amber-400",
      text: "text-amber-600 dark:text-amber-400",
      fill: "#f59e0b",
    };
  return {
    stroke: "stroke-red-500 dark:stroke-red-400",
    text: "text-red-600 dark:text-red-400",
    fill: "#ef4444",
  };
}

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

/* ── Chart components ──────────────────────────────────── */

export function ArcRingChart(props: {
  value: number | null;
  max: number;
  label: string;
  sublabel?: string;
  color: string;
  isDark: boolean;
}) {
  const targetValue = props.value ?? 0;
  const progress = props.value === null ? 0 : clamp01(props.value / props.max);
  const radius = 72;
  const strokeWidth = 14;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75;
  const dashOffset = arcLength * (1 - progress);
  const bgColor = props.isDark ? "#3f3f46" : "#e5e7eb";

  const display = useCountUp(targetValue);
  const digits = props.max === 4 ? 2 : 0;

  const slug = props.label.replace(/\s+/g, "").toLowerCase();
  const gradId = `arcGrad-${slug}`;
  const glowId = `arcGlow-${slug}`;

  return (
    <div className="flex flex-col items-center py-2">
      <div className="relative" style={{ width: 200, height: 200 }}>
        <motion.div
          className="absolute inset-3 rounded-full"
          style={{ background: `radial-gradient(circle, ${props.color}22 0%, transparent 70%)` }}
          animate={{ opacity: [0.4, 0.7, 0.4], scale: [0.95, 1.02, 0.95] }}
          transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
        />
        <svg width="200" height="200" viewBox="0 0 200 200" className="relative transform -rotate-[135deg]">
          <defs>
            <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={props.color} stopOpacity="0.65" />
              <stop offset="100%" stopColor={props.color} stopOpacity="1" />
            </linearGradient>
            <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <circle
            cx="100"
            cy="100"
            r={radius}
            fill="none"
            stroke={bgColor}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference - arcLength}`}
            strokeLinecap="round"
          />
          <motion.circle
            cx="100"
            cy="100"
            r={radius}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference - arcLength}`}
            strokeLinecap="round"
            filter={`url(#${glowId})`}
            initial={{ strokeDashoffset: arcLength }}
            animate={{ strokeDashoffset: dashOffset }}
            transition={{ duration: 1.4, ease: [0.2, 0.8, 0.2, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.25, duration: 0.5, type: "spring", stiffness: 180 }}
            className={`text-[44px] font-bold leading-none tracking-tight tabular-nums ${props.isDark ? "text-white" : "text-zinc-900"}`}
          >
            {props.value === null ? "—" : display.toFixed(digits)}
          </motion.div>
          {props.sublabel && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8, duration: 0.4 }}
              className={`text-[11px] font-semibold mt-1.5 tracking-wide ${props.isDark ? "text-zinc-400" : "text-zinc-500"}`}
            >
              {props.sublabel}
            </motion.div>
          )}
        </div>
      </div>
      <motion.div
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.55, duration: 0.4 }}
        className="text-sm font-bold text-[#A0001A] dark:text-[#ef4444] mt-3 tracking-wide"
      >
        {props.label}
      </motion.div>
    </div>
  );
}

export function GPATrendArcChart(props: {
  points: Array<{ term: string; gpa: number }>;
  latestChange?: number;
  isDark: boolean;
}) {
  const pts = props.points;
  if (!pts.length) {
    return (
      <div
        className={`rounded-xl border p-8 text-center text-sm ${
          props.isDark ? "border-zinc-700 bg-zinc-800 text-zinc-400" : "border-zinc-200 bg-white text-zinc-500"
        }`}
      >
        No GPA trend data available yet
      </div>
    );
  }

  const width = 1100;
  const height = 300;
  const padX = 60;
  const padY = 40;
  const gpas = pts.map((p) => p.gpa);
  const minGpa = Math.max(0, Math.min(...gpas) - 0.3);
  const maxGpa = Math.min(4, Math.max(...gpas) + 0.3);
  const scaleX = (i: number) => padX + (i / (pts.length - 1 || 1)) * (width - padX * 2);
  const scaleY = (gpa: number) => height - padY - ((gpa - minGpa) / (maxGpa - minGpa || 1)) * (height - padY * 2);
  const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(p.gpa)}`).join(" ");
  const fillD = `${pathD} L ${scaleX(pts.length - 1)} ${height - padY} L ${scaleX(0)} ${height - padY} Z`;

  return (
    <div className={`rounded-xl border p-4 overflow-x-auto ${props.isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="gpaTrendGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(34, 197, 94, 0.25)" />
            <stop offset="100%" stopColor="rgba(34, 197, 94, 0)" />
          </linearGradient>
        </defs>
        <path d={fillD} fill="url(#gpaTrendGrad)" />
        <path d={pathD} fill="none" stroke="#22c55e" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {pts.map((p, i) => {
          const cx = scaleX(i);
          const cy = scaleY(p.gpa);
          return (
            <g key={p.term + i}>
              <circle cx={cx} cy={cy} r="8" fill="rgba(34, 197, 94, 0.2)" />
              <circle cx={cx} cy={cy} r="5" fill="#22c55e" stroke={props.isDark ? "#18181b" : "#fff"} strokeWidth="2" />
              <text x={cx} y={cy - 16} fontSize="13" fontWeight="700" textAnchor="middle" fill={props.isDark ? "#f4f4f5" : "#1f2937"}>
                {fmtNum(p.gpa, 2)}
              </text>
              <text x={cx} y={height - 12} fontSize="12" textAnchor="middle" fill={props.isDark ? "#a1a1aa" : "#6b7280"} fontWeight="500">
                {p.term}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
