"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

type Props = {
  name: string;
  size?: number; // px
};

const STORAGE_KEY = "advisor_profile_avatar";

export default function ProfileAvatar({ name, size = 44 }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [avatar, setAvatar] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) setAvatar(saved);
  }, []);

  function openPicker() {
    inputRef.current?.click();
  }

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Accept only images
    if (!file.type.startsWith("image/")) return;

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      setAvatar(dataUrl);
      localStorage.setItem(STORAGE_KEY, dataUrl);
    };
    reader.readAsDataURL(file);

    // reset input so selecting the same file again triggers change
    e.target.value = "";
  }

  function removeAvatar() {
    setAvatar(null);
    localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={openPicker}
        className="group relative"
        title="Change profile photo"
      >
        <motion.div
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.98 }}
          className="relative overflow-hidden rounded-full border border-zinc-200 dark:border-zinc-700 shadow-sm"
          style={{ width: size, height: size }}
        >
          {avatar ? (
            <Image
              src={avatar}
              alt="Profile"
              fill
              className="object-cover"
              sizes={`${size}px`}
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-zinc-100 dark:bg-zinc-800 text-sm font-semibold text-zinc-600 dark:text-zinc-400">
              {name?.trim()?.[0]?.toUpperCase() ?? "U"}
            </div>
          )}

          {/* hover overlay */}
          <div className="absolute inset-0 grid place-items-center bg-black/0 text-white opacity-0 transition group-hover:bg-black/25 group-hover:opacity-100">
            <span className="text-[10px] font-medium">Change</span>
          </div>
        </motion.div>
      </button>

      <AnimatePresence>
        {avatar ? (
          <motion.button
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            type="button"
            onClick={removeAvatar}
            className="text-xs text-zinc-500 dark:text-zinc-400 underline hover:text-zinc-700 dark:text-zinc-300"
          >
            Remove
          </motion.button>
        ) : null}
      </AnimatePresence>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={onPickFile}
      />
    </div>
  );
}
