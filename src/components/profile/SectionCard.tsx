import Image from "next/image";
import React from "react";

type SectionCardProps = {
  title: string;
  icon: string;
  isDark: boolean;
  children: React.ReactNode;
};

export default function SectionCard({ title, icon, isDark, children }: SectionCardProps) {
  return (
    <section className={`rounded-2xl border p-5 md:p-6 ${isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"}`}>
      <div className="flex items-center gap-2 mb-5">
        <Image src={icon} alt="icon" width={16} height={16} />
        <div className={`text-[16px] font-extrabold ${isDark ? "text-white" : "text-[#B8001F]"}`}>{title}</div>
      </div>
      {children}
    </section>
  );
}
