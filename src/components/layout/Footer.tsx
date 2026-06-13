"use client";

import Image from "next/image";
import { LINKS } from "@/lib/constants";
import { useLanguage } from "@/hooks/useLanguage";

export default function Footer() {
  const { t } = useLanguage();
  return (
    <footer className="bg-[#A0001A] text-white">
      <div className="grid grid-cols-1 gap-8 md:gap-10 px-4 md:px-8 lg:px-16 py-8 md:py-10 md:grid-cols-3">
        <div>
          <div className="mb-4 text-sm font-extrabold uppercase tracking-wide">{t("footer.contact")}</div>
          <div className="flex items-center gap-3 text-sm font-bold mb-3">
            <Image src="/location.svg" alt="loc" width={16} height={16} className="brightness-0 invert" />
            <span>{t("footer.location")}</span>
          </div>
          <div className="flex items-center gap-3 text-sm font-bold">
            <Image src="/mail.svg" alt="mail" width={16} height={16} className="brightness-0 invert" />
            <span>info@aiu.edu.eg</span>
          </div>
        </div>

        <div>
          <div className="mb-4 text-sm font-extrabold uppercase tracking-wide">{t("footer.socials")}</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <a href={LINKS.facebook} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-sm font-bold hover:opacity-80">
              <Image src="/facebook.svg" alt="fb" width={16} height={16} className="brightness-0 invert" />
              Facebook
            </a>
            <a href={LINKS.linkedin} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-sm font-bold hover:opacity-80">
              <Image src="/linkedin.svg" alt="li" width={16} height={16} className="brightness-0 invert" />
              LinkedIn
            </a>
            <a href={LINKS.youtube} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-sm font-bold hover:opacity-80">
              <Image src="/Youtube.svg" alt="yt" width={16} height={16} className="brightness-0 invert" />
              YouTube
            </a>
            <a href={LINKS.instagram} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-sm font-bold hover:opacity-80">
              <Image src="/instagram.svg" alt="ig" width={16} height={16} className="brightness-0 invert" />
              Instagram
            </a>
          </div>
        </div>

        <div>
          <div className="mb-4 text-sm font-extrabold uppercase tracking-wide">{t("footer.about")}</div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm font-bold">
            <a href={LINKS.vision} target="_blank" rel="noreferrer" className="hover:opacity-80">
              {t("footer.vision")}
            </a>
            <a href={LINKS.values} target="_blank" rel="noreferrer" className="hover:opacity-80">
              {t("footer.values")}
            </a>
            <a href={LINKS.undergraduate} target="_blank" rel="noreferrer" className="hover:opacity-80">
              {t("footer.undergrad")}
            </a>
            <a href={LINKS.faculties} target="_blank" rel="noreferrer" className="hover:opacity-80">
              {t("footer.faculties")}
            </a>
          </div>
        </div>
      </div>

      <div className="border-t border-[#800016] py-4 text-center text-sm">
        &copy; {new Date().getFullYear()} {t("footer.rights")}
      </div>
    </footer>
  );
}
