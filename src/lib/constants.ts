export const LINKS = {
  facebook: "https://www.facebook.com/AiuOfficialgov/",
  youtube: "https://www.youtube.com/channel/UCaNZBjp6yCmW8O8wJaIG-Dw",
  linkedin:
    "https://www.linkedin.com/company/al-alamein-international-university/",
  instagram: "https://www.instagram.com/alameininternationaluni/",
  vision: "https://aiu.edu.eg/visionmission/",
  undergraduate: "https://aiu.edu.eg/undergraduate/",
  values: "https://aiu.edu.eg/governing-values/",
  faculties: "https://aiu.edu.eg/faculties/",
};

export const AVATAR_LS_KEY = "profile_avatar_dataurl";
export const THEME_LS_KEY = "aiu_theme";
export const TOKEN_LS_KEY = "advisor_token";
export const REFRESH_LS_KEY = "advisor_refresh";
export const CHAT_LS_KEY = "aiu_chat_state";

export type Notif = { id: string; title: string; time: string };

export const DEFAULT_NOTIFS: Notif[] = [
  { id: "1", title: "New advisor note available", time: "2h ago" },
  { id: "2", title: "Course registration opens soon", time: "Yesterday" },
  { id: "3", title: "Reminder: update your profile", time: "3 days ago" },
];

export type NavItemDef = {
  label: string;
  shortLabel?: string;
  href: string;
};

export const NAV_ITEMS: NavItemDef[] = [
  { label: "Manage Classes", shortLabel: "Classes", href: "/manage-classes/my-classes" },
  { label: "Schedule Generator", shortLabel: "Schedule", href: "/schedule-generator" },
  { label: "Recommendations", shortLabel: "Advice", href: "/course-recommendations" },
  { label: "GPA Simulator", shortLabel: "GPA Sim", href: "/gpa-simulator" },
  { label: "Study Plan", shortLabel: "Plan", href: "/study-plan" },
  { label: "Academic Records", shortLabel: "Records", href: "/academic-records" },
  { label: "Career", shortLabel: "Career", href: "/career" },
  { label: "Financial Account", shortLabel: "Financial", href: "/financial-account" },
  { label: "Profile", shortLabel: "Profile", href: "/profile" },
  { label: "User Settings", shortLabel: "Settings", href: "/user-settings" },
];
