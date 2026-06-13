"use client";

import { motion } from "framer-motion";

type Props = {
  title: string;
  description?: string;
  icon?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  isDark?: boolean;
};

export default function EmptyState({
  title,
  description,
  icon = "📋",
  action,
  isDark = false,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 text-center ${
        isDark ? "border-zinc-700 bg-zinc-900/50" : "border-zinc-200 bg-zinc-50/50"
      }`}
    >
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 20, delay: 0.1 }}
        className="mb-4 text-5xl"
      >
        {icon}
      </motion.div>
      <h3
        className={`mb-2 text-lg font-bold ${
          isDark ? "text-white" : "text-zinc-900"
        }`}
      >
        {title}
      </h3>
      {description && (
        <p
          className={`mb-4 max-w-sm text-sm ${
            isDark ? "text-zinc-400" : "text-zinc-500"
          }`}
        >
          {description}
        </p>
      )}
      {action && (
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={action.onClick}
          className="rounded-lg bg-[#B8001F] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#A0001A] transition-colors"
          type="button"
        >
          {action.label}
        </motion.button>
      )}
    </motion.div>
  );
}
