type ReadFieldProps = {
  label: string;
  value?: string | null;
  isDark: boolean;
};

export default function ReadField({ label, value, isDark }: ReadFieldProps) {
  const v = value && String(value).trim() ? String(value) : "—";
  return (
    <div>
      <div className={`mb-1.5 text-xs font-semibold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>{label}</div>
      <div
        className={`h-10 rounded-lg border px-3 flex items-center text-sm ${
          isDark ? "border-zinc-700 bg-zinc-950 text-zinc-100" : "border-zinc-200 bg-white text-zinc-900"
        }`}
      >
        {v}
      </div>
    </div>
  );
}
