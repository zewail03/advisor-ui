"use client";

import Image from "next/image";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import {
  getMe,
  getProfile,
  updateProfile,
  type MeResponse,
  type StudentProfile,
} from "@/lib/api";
import { normalizeErrorMessage, isAbortError } from "@/lib/utils";
import { AVATAR_LS_KEY } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import ErrorBanner from "@/components/ErrorBanner";
import SuccessBanner from "@/components/SuccessBanner";
import { ProfileSkeleton } from "@/components/LoadingSkeleton";
import AppLayout from "@/components/layout/AppLayout";
import PageContainer from "@/components/layout/PageContainer";
import SectionCard from "@/components/profile/SectionCard";
import MiniStat from "@/components/profile/MiniStat";
import ReadField from "@/components/profile/ReadField";
import InfoRow from "@/components/profile/InfoRow";
import SwitchRow from "@/components/profile/SwitchRow";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { useLanguage } from "@/hooks/useLanguage";

type TogglesState = {
  notif_email: boolean;
  notif_sms: boolean;
  notif_advisor: boolean;
  public_profile: boolean;
};

export default function ProfilePage() {
  const { isDark } = useTheme();
  const { t } = useLanguage();
  const { token, signOut } = useAuth();

  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const [avatarDataUrl, setAvatarDataUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [toggles, setToggles] = useState<TogglesState>({
    notif_email: true,
    notif_sms: true,
    notif_advisor: true,
    public_profile: false,
  });

  const [editableProfile, setEditableProfile] = useState({
    full_name: "",
    phone: "",
    date_of_birth: "",
    gender: "",
    nationality: "",
    school_id: "",
    home_address: "",
    city: "",
    postal_code: "",
    emergency_contact_name: "",
    emergency_relationship: "",
    emergency_phone: "",
    emergency_email: "",
  });

  const loadData = useCallback(async (tkn: string, signal?: AbortSignal) => {
    setErr(null);
    setLoading(true);
    try {
      const [s, p] = await Promise.all([getMe(tkn, signal), getProfile(tkn, signal)]);
      if (signal?.aborted) return;
      setSummary(s);
      setProfile(p);

      setEditableProfile({
        full_name: p.full_name || "",
        phone: p.phone || "",
        date_of_birth: p.date_of_birth || "",
        gender: p.gender || "",
        nationality: p.nationality || "",
        school_id: p.school_id || "",
        home_address: p.home_address || "",
        city: p.city || "",
        postal_code: p.postal_code || "",
        emergency_contact_name: p.emergency_contact_name || "",
        emergency_relationship: p.emergency_relationship || "",
        emergency_phone: p.emergency_phone || "",
        emergency_email: p.emergency_email || "",
      });

      setToggles({
        notif_email: !!p.notif_email,
        notif_sms: !!p.notif_sms,
        notif_advisor: !!p.notif_advisor,
        public_profile: !!p.public_profile,
      });
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      const msg = normalizeErrorMessage(e, "Failed to load profile");
      if (
        msg.toLowerCase().includes("unauthorized") ||
        msg.toLowerCase().includes("invalid token")
      ) {
        signOut();
        return;
      }
      setErr(msg);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [signOut]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    loadData(token, controller.signal);
    return () => controller.abort();
  }, [token, loadData]);

  const retry = useCallback(() => {
    if (token) loadData(token);
  }, [token, loadData]);

  // avatar load
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = localStorage.getItem(AVATAR_LS_KEY);
      if (saved) setAvatarDataUrl(saved);
    } catch {
      // ignore
    }
  }, []);

  const saveChanges = useCallback(async () => {
    if (saving || !token) return;

    setSaveMsg(null);
    setErr(null);
    setSaving(true);

    try {
      const patch: Partial<StudentProfile> = {
        ...editableProfile,
        notif_email: toggles.notif_email ? 1 : 0,
        notif_sms: toggles.notif_sms ? 1 : 0,
        notif_advisor: toggles.notif_advisor ? 1 : 0,
        public_profile: toggles.public_profile ? 1 : 0,
      };

      const updated = await updateProfile(token, patch);

      setProfile(updated);
      setSaveMsg(t("pr.saved"));
      setTimeout(() => setSaveMsg(null), 3000);

      setEditableProfile({
        full_name: updated.full_name || "",
        phone: updated.phone || "",
        date_of_birth: updated.date_of_birth || "",
        gender: updated.gender || "",
        nationality: updated.nationality || "",
        school_id: updated.school_id || "",
        home_address: updated.home_address || "",
        city: updated.city || "",
        postal_code: updated.postal_code || "",
        emergency_contact_name: updated.emergency_contact_name || "",
        emergency_relationship: updated.emergency_relationship || "",
        emergency_phone: updated.emergency_phone || "",
        emergency_email: updated.emergency_email || "",
      });

      setToggles({
        notif_email: !!updated.notif_email,
        notif_sms: !!updated.notif_sms,
        notif_advisor: !!updated.notif_advisor,
        public_profile: !!updated.public_profile,
      });
    } catch (e: unknown) {
      const msg = normalizeErrorMessage(e, "Failed to save changes");
      if (
        msg.toLowerCase().includes("unauthorized") ||
        msg.toLowerCase().includes("invalid token")
      ) {
        signOut();
        return;
      }
      setErr(msg);
    } finally {
      setSaving(false);
    }
  }, [saving, token, editableProfile, toggles, signOut]);

  function cancelChanges() {
    if (!profile) return;

    setEditableProfile({
      full_name: profile.full_name || "",
      phone: profile.phone || "",
      date_of_birth: profile.date_of_birth || "",
      gender: profile.gender || "",
      nationality: profile.nationality || "",
      school_id: profile.school_id || "",
      home_address: profile.home_address || "",
      city: profile.city || "",
      postal_code: profile.postal_code || "",
      emergency_contact_name: profile.emergency_contact_name || "",
      emergency_relationship: profile.emergency_relationship || "",
      emergency_phone: profile.emergency_phone || "",
      emergency_email: profile.emergency_email || "",
    });

    setToggles({
      notif_email: !!profile.notif_email,
      notif_sms: !!profile.notif_sms,
      notif_advisor: !!profile.notif_advisor,
      public_profile: !!profile.public_profile,
    });
  }

  function openAvatarPicker() {
    fileInputRef.current?.click();
  }

  function onAvatarFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      e.target.value = "";
      return;
    }

    const maxBytes = 2.5 * 1024 * 1024;
    if (file.size > maxBytes) {
      e.target.value = "";
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = typeof reader.result === "string" ? reader.result : null;
      if (!dataUrl) return;

      try {
        localStorage.setItem(AVATAR_LS_KEY, dataUrl);
      } catch {
        // ignore
      }
      setAvatarDataUrl(dataUrl);
      e.target.value = "";
    };
    reader.onerror = () => {
      e.target.value = "";
    };
    reader.readAsDataURL(file);
  }

  const containerMax = "max-w-[980px]";
  const cardBase = isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white";
  const cardInner = isDark ? "text-white" : "text-zinc-900";

  return (
    <AppLayout activePath="/profile" userName={summary?.full_name ?? "Loading..."}>
      <PageContainer>
        <div className={`mx-auto w-full ${containerMax}`}>
          <ErrorBanner message={err} isDark={isDark} onDismiss={() => setErr(null)} />
          {err && (
            <Button
              type="button"
              onClick={retry}
              className="h-9 rounded-lg bg-[#B8001F] hover:bg-[#9A0019] px-5 text-sm font-semibold text-white mb-4"
            >
              Retry
            </Button>
          )}
          <SuccessBanner message={saveMsg} isDark={isDark} onDismiss={() => setSaveMsg(null)} />

          {loading && !profile ? (
            <div className={`rounded-2xl border ${cardBase} p-5 md:p-6`}>
              <ProfileSkeleton isDark={isDark} />
            </div>
          ) : null}

          {/* Student Profile (ONLY PLACE THAT UPLOADS) */}
          <SectionCard title={t("pr.studentProfile")} icon="/user-red.svg" isDark={isDark}>
            <div className={`rounded-2xl border ${cardBase} p-5 md:p-6`}>
              <div className="flex flex-col md:flex-row md:items-center gap-5 md:gap-6">
                <button
                  onClick={openAvatarPicker}
                  className={`shrink-0 rounded-full overflow-hidden border ${
                    isDark ? "border-zinc-700 bg-zinc-950" : "border-zinc-200 bg-white"
                  }`}
                  style={{ width: 92, height: 92 }}
                  aria-label="change avatar"
                  title="Change avatar"
                  type="button"
                >
                  {avatarDataUrl ? (
                    <img src={avatarDataUrl} alt="profile avatar" className="h-full w-full object-cover" />
                  ) : (
                    <Image
                      src="/avatar.png"
                      alt="profile avatar"
                      width={92}
                      height={92}
                      className="h-[92px] w-[92px] object-cover"
                    />
                  )}
                </button>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={onAvatarFileChange}
                />

                <div className="flex-1 min-w-0">
                  <div className={`text-[18px] md:text-[20px] font-extrabold ${cardInner} truncate`}>
                    {profile?.full_name || summary?.full_name || "Student"}
                  </div>
                  <div className={`mt-1 text-[12px] md:text-[13px] ${isDark ? "text-zinc-400" : "text-zinc-600"} truncate`}>
                    {profile?.email || "—"}
                  </div>

                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-6">
                    <MiniStat label={t("pr.program")} value={typeof profile?.program === "object" ? (profile.program as any)?.name : profile?.program || "—"} isDark={isDark} />
                    <MiniStat label={t("pr.major")} value={typeof profile?.major === "object" ? (profile.major as any)?.name : profile?.major || "—"} isDark={isDark} />
                    <MiniStat label={t("pr.year")} value={profile?.academic_year || "—"} isDark={isDark} />
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>

          {/* Sections */}
          <div className={`space-y-6 mt-6 ${loading && !profile ? "hidden" : ""}`}>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              <SectionCard title={t("pr.personal")} icon="/user-red.svg" isDark={isDark}>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <ReadField label={t("pr.fullName")} value={profile?.full_name} isDark={isDark} />
                  <ReadField label={t("pr.studentId")} value={profile?.student_id} isDark={isDark} />
                  <ReadField label={t("pr.dob")} value={profile?.date_of_birth} isDark={isDark} />
                  <ReadField label={t("pr.gender")} value={profile?.gender} isDark={isDark} />
                  <ReadField label={t("pr.nationality")} value={profile?.nationality} isDark={isDark} />
                  <ReadField label={t("pr.schoolId")} value={profile?.school_id} isDark={isDark} />
                  <div className="sm:col-span-2">
                    <ReadField label={t("pr.username")} value={profile?.username} isDark={isDark} />
                  </div>
                </div>
              </SectionCard>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <SectionCard title={t("pr.contact")} icon="/phone-red.svg" isDark={isDark}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <ReadField label={t("pr.email")} value={profile?.email} isDark={isDark} />
                  <ReadField label={t("pr.phone")} value={profile?.phone} isDark={isDark} />
                  <ReadField label={t("pr.address")} value={profile?.home_address} isDark={isDark} />
                  <ReadField label={t("pr.city")} value={profile?.city} isDark={isDark} />
                  <ReadField label={t("pr.postal")} value={profile?.postal_code} isDark={isDark} />
                </div>
              </SectionCard>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
              <SectionCard title={t("pr.emergency")} icon="/emergency-red.svg" isDark={isDark}>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <ReadField label={t("pr.contactName")} value={profile?.emergency_contact_name} isDark={isDark} />
                  <ReadField label={t("pr.relationship")} value={profile?.emergency_relationship} isDark={isDark} />
                  <ReadField label={t("pr.phone")} value={profile?.emergency_phone} isDark={isDark} />
                  <ReadField label={t("pr.emEmail")} value={profile?.emergency_email} isDark={isDark} />
                </div>
              </SectionCard>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
              <SectionCard title={t("pr.academic")} icon="/user-red.svg" isDark={isDark}>
                <div className="space-y-2">
                  <InfoRow label={t("pr.program")} value={typeof profile?.program === "object" ? (profile.program as any)?.name : profile?.program} isDark={isDark} />
                  <InfoRow label={t("pr.major")} value={typeof profile?.major === "object" ? (profile.major as any)?.name : profile?.major} isDark={isDark} />
                  <InfoRow label={t("pr.year")} value={profile?.academic_year} isDark={isDark} />
                  <InfoRow label={t("pr.gradDate")} value={profile?.expected_graduation} isDark={isDark} />
                  <InfoRow label={t("pr.advisor")} value={profile?.academic_advisor} isDark={isDark} />
                </div>
              </SectionCard>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
              <SectionCard title={t("pr.account")} icon="/user-red.svg" isDark={isDark}>
                <div className="space-y-5">
                  <SwitchRow
                    isDark={isDark}
                    label={t("pr.notifEmail")}
                    desc={t("pr.notifEmailDesc")}
                    checked={toggles.notif_email}
                    onCheckedChange={(v) => setToggles((t) => ({ ...t, notif_email: v }))}
                  />
                  <SwitchRow
                    isDark={isDark}
                    label={t("pr.notifSms")}
                    desc={t("pr.notifSmsDesc")}
                    checked={toggles.notif_sms}
                    onCheckedChange={(v) => setToggles((t) => ({ ...t, notif_sms: v }))}
                  />
                  <SwitchRow
                    isDark={isDark}
                    label={t("pr.notifAdvisor")}
                    desc={t("pr.notifAdvisorDesc")}
                    checked={toggles.notif_advisor}
                    onCheckedChange={(v) => setToggles((t) => ({ ...t, notif_advisor: v }))}
                  />
                  <SwitchRow
                    isDark={isDark}
                    label={t("pr.public")}
                    desc={t("pr.publicDesc")}
                    checked={toggles.public_profile}
                    onCheckedChange={(v) => setToggles((t) => ({ ...t, public_profile: v }))}
                  />
                </div>

                <div className="mt-7 flex justify-end gap-3">
                  <Button
                    variant="outline"
                    onClick={cancelChanges}
                    disabled={saving}
                    className={`h-11 rounded-lg border px-6 text-sm font-bold ${
                      isDark
                        ? "border-zinc-700 text-zinc-200 hover:bg-zinc-800"
                        : "border-zinc-300 text-zinc-800 hover:bg-zinc-50"
                    }`}
                    type="button"
                  >
                    {t("pr.cancel")}
                  </Button>

                  <Button
                    onClick={saveChanges}
                    disabled={saving}
                    className={`h-11 rounded-lg px-8 text-sm font-bold text-white ${
                      saving ? "bg-blue-400 cursor-not-allowed" : "bg-blue-700 hover:bg-blue-800"
                    }`}
                    type="button"
                  >
                    {saving ? t("pr.saving") : t("pr.save")}
                  </Button>
                </div>
              </SectionCard>
            </motion.div>
          </div>
        </div>
      </PageContainer>
    </AppLayout>
  );
}
