"use client";

import { useEffect, useState } from "react";
import { animate, motion, type Variants } from "framer-motion";

/** Container that staggers its children in. Pair with `fadeUpItem`. */
export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.04 } },
};

export const fadeUpItem: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
};

/** Simple fade/slide-up reveal on mount. */
export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1], delay }}
    >
      {children}
    </motion.div>
  );
}

/** Animated number that counts up from 0 to `value` on mount / change. */
export function CountUp({
  value,
  duration = 1.1,
  format,
}: {
  value: number;
  duration?: number;
  format?: (n: number) => string;
}) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setN(v),
    });
    return () => controls.stop();
  }, [value, duration]);
  const rounded = Math.round(n);
  return <>{format ? format(rounded) : rounded.toLocaleString()}</>;
}
