"use client";

import { useI18n } from "@/lib/i18n";

export default function LanguageToggle() {
  const { lang, toggleLang } = useI18n();

  return (
    <button
      onClick={toggleLang}
      className="relative flex items-center gap-0.5 px-1 py-1 text-xs font-semibold rounded-full bg-[var(--gray-100)] border border-[var(--border-subtle)] transition-all duration-200 hover:border-[var(--border-default)]"
      aria-label={`Switch to ${lang === "sw" ? "English" : "Kiswahili"}`}
    >
      <span
        className={`px-2.5 py-1 rounded-full transition-all duration-300 ${
          lang === "sw"
            ? "bg-white text-[var(--text-primary)] shadow-sm"
            : "text-[var(--text-muted)]"
        }`}
      >
        SW
      </span>
      <span
        className={`px-2.5 py-1 rounded-full transition-all duration-300 ${
          lang === "en"
            ? "bg-white text-[var(--text-primary)] shadow-sm"
            : "text-[var(--text-muted)]"
        }`}
      >
        EN
      </span>
    </button>
  );
}
