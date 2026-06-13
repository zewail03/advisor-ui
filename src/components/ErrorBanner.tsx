"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/hooks/useLanguage";

type Props = {
  message: string | null;
  onRetry?: () => void;
  onDismiss?: () => void;
  isDark?: boolean;
};

export default function ErrorBanner({ message, onRetry, onDismiss, isDark = false }: Props) {
  const { t } = useLanguage();
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          initial={{ opacity: 0, y: -10, height: 0 }}
          animate={{ opacity: 1, y: 0, height: "auto" }}
          exit={{ opacity: 0, y: -10, height: 0 }}
          className={`mb-6 overflow-hidden rounded-xl border ${
            isDark
              ? "border-red-800/50 bg-red-950/50"
              : "border-red-200 bg-red-50"
          }`}
        >
          <div className="flex items-center gap-3 px-4 py-3">
            <motion.span
              initial={{ rotate: 0 }}
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-lg"
            >
              ⚠
            </motion.span>
            <span
              className={`flex-1 text-sm font-medium ${
                isDark ? "text-red-300" : "text-red-700"
              }`}
            >
              {message}
            </span>
            <div className="flex items-center gap-2">
              {onRetry && (
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={onRetry}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-colors ${
                    isDark
                      ? "bg-red-800/50 text-red-200 hover:bg-red-800"
                      : "bg-red-100 text-red-700 hover:bg-red-200"
                  }`}
                  type="button"
                >
                  {t("common.retry")}
                </motion.button>
              )}
              {onDismiss && (
                <button
                  onClick={onDismiss}
                  className={`text-sm font-bold ${
                    isDark ? "text-red-400 hover:text-red-300" : "text-red-500 hover:text-red-700"
                  }`}
                  type="button"
                >
                  x
                </button>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
