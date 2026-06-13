"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type SwitchProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
};

export function Switch({
  checked = false,
  onCheckedChange,
  className,
  disabled,
  ...props
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => {
        if (disabled) return;
        onCheckedChange?.(!checked);
      }}
      className={cn(
        "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors",
        checked
          ? "bg-emerald-500 border-emerald-600 dark:bg-emerald-500 dark:border-emerald-600"
          : "bg-zinc-200 border-zinc-300 dark:bg-zinc-800 dark:border-zinc-700",
        disabled && "opacity-60 cursor-not-allowed",
        className
      )}
      {...props}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-5 w-5 transform rounded-full border transition-transform",
          checked ? "translate-x-5" : "translate-x-1",
          "bg-white border-zinc-200",
          "dark:bg-zinc-950 dark:border-zinc-700"
        )}
      />
    </button>
  );
}
