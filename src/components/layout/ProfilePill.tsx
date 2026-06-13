"use client";

type ProfilePillProps = {
  isDark: boolean;
  userName?: string | null;
  avatarDataUrl: string | null;
};

export default function ProfilePill({ isDark, userName, avatarDataUrl }: ProfilePillProps) {
  const initials = userName
    ? userName
        .split(" ")
        .slice(0, 2)
        .map((w) => w[0]?.toUpperCase())
        .join("")
    : "U";

  // Avatar-only variant (no name text)
  if (!userName) {
    return (
      <div className="relative grid h-10 w-10 place-items-center overflow-hidden rounded-full bg-[#B8001F] text-sm font-bold text-white cursor-default">
        {avatarDataUrl ? (
          <img src={avatarDataUrl} alt="avatar" className="h-full w-full object-cover" />
        ) : (
          <span>U</span>
        )}
      </div>
    );
  }

  // Full pill variant with name + avatar
  return (
    <div
      className={`flex items-center gap-3 rounded-full px-4 py-2 ${
        isDark ? "bg-zinc-800" : "bg-white"
      } shadow-sm`}
    >
      <div className="text-right leading-tight">
        <div className={`text-sm font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
          {userName}
        </div>
      </div>
      <div
        className="relative grid h-10 w-10 place-items-center overflow-hidden rounded-full bg-[#B8001F] text-sm font-bold text-white cursor-default"
        title="Profile picture"
      >
        {avatarDataUrl ? (
          <img src={avatarDataUrl} alt="avatar" className="h-full w-full object-cover" />
        ) : (
          <>{initials || "HG"}</>
        )}
      </div>
    </div>
  );
}
