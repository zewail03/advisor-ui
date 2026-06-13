type MiniStatProps = {
  label: string;
  value: string;
  isDark: boolean;
};

export default function MiniStat({ label, value, isDark }: MiniStatProps) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${isDark ? "border-zinc-800 bg-zinc-950" : "border-zinc-200 bg-white"}`}>
      <div className={`text-[11px] font-semibold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>{label}</div>
      <div className={`mt-1 text-[14px] font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>{value}</div>
    </div>
  );
}
