"use client";

import { motion, AnimatePresence } from "framer-motion";

type Props = {
  message: string | null;
  onDismiss?: () => void;
  isDark?: boolean;
};

export default function SuccessBanner({ message, onDismiss, isDark = false }: Props) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          initial={{ opacity: 0, y: -10, height: 0 }}
          animate={{ opacity: 1, y: 0, height: "auto" }}
          exit={{ opacity: 0, y: -10, height: 0 }}
          className={`mb-6 overflow-hidden rounded-xl border ${
            isDark
              ? "border-green-800/50 bg-green-950/50"
              : "border-green-200 bg-green-50"
          }`}
        >
          <div className="flex items-center gap-3 px-4 py-3">
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 300, damping: 15 }}
              className="text-lg"
            >
              ✓
            </motion.span>
            <span
              className={`flex-1 text-sm font-medium ${
                isDark ? "text-green-300" : "text-green-700"
              }`}
            >
              {message}
            </span>
            {onDismiss && (
              <button
                onClick={onDismiss}
                className={`text-sm font-bold ${
                  isDark ? "text-green-400 hover:text-green-300" : "text-green-500 hover:text-green-700"
                }`}
                type="button"
              >
                x
              </button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
