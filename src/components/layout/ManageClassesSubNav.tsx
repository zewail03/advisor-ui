"use client";

import { useRouter } from "next/navigation";

const SUB_NAV_ITEMS = [
  { label: "My Classes", href: "/manage-classes/my-classes" },
  { label: "My Requirements", href: "/manage-classes/requirements" },
];

type ManageClassesSubNavProps = {
  activePath: string;
  isDark: boolean;
};

export default function ManageClassesSubNav({ activePath, isDark }: ManageClassesSubNavProps) {
  const router = useRouter();

  return (
    <div className={`mb-6 flex gap-1 rounded-xl border p-1 w-fit ${
      isDark ? "border-zinc-700 bg-zinc-900" : "border-zinc-200 bg-zinc-100"
    }`}>
      {SUB_NAV_ITEMS.map((item) => {
        const isActive = activePath === item.href;
        return (
          <button
            key={item.href}
            type="button"
            onClick={() => router.push(item.href)}
            className={`rounded-lg px-5 py-2 text-sm font-bold transition-all duration-200 ${
              isActive
                ? "bg-[#B8001F] text-white shadow-sm"
                : isDark
                  ? "text-zinc-400 hover:text-white hover:bg-zinc-800"
                  : "text-zinc-600 hover:text-zinc-900 hover:bg-white"
            }`}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
