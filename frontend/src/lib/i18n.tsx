"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

export type Lang = "sw" | "en";

const translations = {
  sw: {
    // Header
    brand: "Sauti",
    title: "Ongea na Sauti",
    subtitle: "Sauti yako → maandishi → majibu → sauti",
    endSession: "Maliza",

    // Empty state
    emptyTitle: "Karibu",
    emptySubtitle: "Andika ujumbe au bonyeza maikrofoni kuanza mazungumzo.",

    // Chat input
    placeholder: "Andika ujumbe...",
    voiceMode: "Hali ya sauti",

    // Voice mode
    ready: "TAYARI",
    listening: "INASIKILIZA...",
    thinking: "INAFIKIRI...",
    speaking: "INAZUNGUMZA...",
    tapToSpeak: "Gusa maikrofoni kuanza",
    tapToStop: "Gusa tena kusimamisha",
    saySomething: "Sema sasa...",
    waitMoment: "Subiri kidogo...",
    tapToInterrupt: "Gusa ili kunyamazisha",

    // Message actions
    copy: "Nakili",
    copied: "Imenakiliwa",

    // Connection
    disconnected: "Umeondoka mtandaoni",
    connecting: "Inaunganisha...",
    connected: "Imeunganishwa",
  },
  en: {
    brand: "Sauti",
    title: "Talk to Sauti",
    subtitle: "Your voice → text → answers → voice",
    endSession: "End",

    emptyTitle: "Welcome",
    emptySubtitle: "Type a message or tap the microphone to start chatting.",

    placeholder: "Type a message...",
    voiceMode: "Voice mode",

    ready: "READY",
    listening: "LISTENING...",
    thinking: "THINKING...",
    speaking: "SPEAKING...",
    tapToSpeak: "Tap the microphone to start",
    tapToStop: "Tap again to stop",
    saySomething: "Say something...",
    waitMoment: "One moment...",
    tapToInterrupt: "Tap to interrupt",

    copy: "Copy",
    copied: "Copied",

    disconnected: "Disconnected",
    connecting: "Connecting...",
    connected: "Connected",
  },
} as const;

type TranslationKeys = keyof typeof translations.sw;

type I18nContextValue = {
  lang: Lang;
  toggleLang: () => void;
  t: (key: TranslationKeys) => string;
};

const I18nContext = createContext<I18nContextValue>({
  lang: "sw",
  toggleLang: () => {},
  t: (key) => translations.sw[key],
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("sw");

  const toggleLang = useCallback(() => {
    setLang((prev) => (prev === "sw" ? "en" : "sw"));
  }, []);

  const t = useCallback(
    (key: TranslationKeys) => translations[lang][key],
    [lang]
  );

  return (
    <I18nContext.Provider value={{ lang, toggleLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
