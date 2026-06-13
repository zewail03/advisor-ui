import { Switch } from "@/components/ui/switch";

type SwitchRowProps = {
  label: string;
  desc: string;
  checked: boolean;
  isDark: boolean;
  onCheckedChange: (v: boolean) => void;
};

export default function SwitchRow({ label, desc, checked, isDark, onCheckedChange }: SwitchRowProps) {
  return (
    <div className={`flex items-center justify-between gap-6 rounded-xl border px-4 py-4 ${isDark ? "border-zinc-800 bg-zinc-950" : "border-zinc-200 bg-white"}`}>
      <div className="min-w-0 flex-1">
        <div className={`text-sm font-extrabold mb-1 ${isDark ? "text-white" : "text-zinc-900"}`}>{label}</div>
        <div className={`text-xs ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>{desc}</div>
      </div>

      <Switch
        checked={checked}
        onCheckedChange={onCheckedChange}
        className={`${checked ? "data-[state=checked]:bg-emerald-500" : ""} ${isDark ? "data-[state=unchecked]:bg-zinc-800" : ""}`}
      />
    </div>
  );
}
