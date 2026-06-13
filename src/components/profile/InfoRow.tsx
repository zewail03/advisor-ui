type InfoRowProps = {
  label: string;
  value?: string | null;
  isDark: boolean;
};

export default function InfoRow({ label, value, isDark }: InfoRowProps) {
  const v = value && String(value).trim() ? String(value) : "—";
  return (
    <div className={`flex items-center justify-between py-3 border-b ${isDark ? "border-zinc-800" : "border-zinc-200"} last:border-0`}>
      <div className={`text-sm font-semibold ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>{label}</div>
      <div className={`text-sm font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>{v}</div>
    </div>
  );
}
