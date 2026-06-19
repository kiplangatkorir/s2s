"use client";

import { Mic, MicOff, X } from "lucide-react";
import { useI18n } from "@/lib/i18n";

type Props = {
  isRecording: boolean;
  isThinking: boolean;
  isSpeaking: boolean;
  toggleRecording: () => void;
  onClose: () => void;
};

export default function VoiceMode({
  isRecording,
  isThinking,
  isSpeaking,
  toggleRecording,
  onClose,
}: Props) {
  const { t } = useI18n();

  const statusKey = isRecording
    ? "listening"
    : isThinking
    ? "thinking"
    : isSpeaking
    ? "speaking"
    : "ready";

  const hintKey = isRecording
    ? "saySomething"
    : isThinking
    ? "waitMoment"
    : isSpeaking
    ? "tapToInterrupt"
    : "tapToSpeak";

  const orbClass = isRecording
    ? "voice-orb voice-orb--recording"
    : isThinking
    ? "voice-orb voice-orb--thinking"
    : isSpeaking
    ? "voice-orb voice-orb--speaking"
    : "voice-orb";

  const showRings = isRecording || isSpeaking;

  return (
    <div className="fixed inset-0 z-50 bg-[var(--foundation-dark)] flex flex-col items-center justify-between animate-fade-in">
      {/* Radial glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(circle at 50% 45%, rgba(194, 65, 12, ${
              isRecording ? 0.12 : isThinking ? 0.08 : isSpeaking ? 0.06 : 0.04
            }) 0%, transparent 55%),
            radial-gradient(circle at 50% 55%, rgba(234, 88, 12, ${
              isRecording ? 0.08 : 0.03
            }) 0%, transparent 45%)
          `,
        }}
      />

      {/* Top bar */}
      <div className="relative w-full flex items-center justify-between px-6 pt-6">
        <div>
          <p className="text-white/30 text-xs font-semibold tracking-[0.3em] uppercase">
            {t("brand")}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-2.5 text-white/50 hover:text-white transition-colors rounded-xl hover:bg-white/10"
          aria-label="Close voice mode"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Orb section */}
      <div className="relative flex flex-col items-center gap-10">
        <div className="relative w-56 h-56 flex items-center justify-center">
          {showRings && (
            <>
              <div className="voice-orb-ring voice-orb-ring--1" />
              <div className="voice-orb-ring voice-orb-ring--2" />
              <div className="voice-orb-ring voice-orb-ring--3" />
            </>
          )}
          <div className={orbClass} />
        </div>

        <div className="text-center space-y-2">
          <p className="text-white/60 text-sm font-semibold tracking-[0.25em] uppercase">
            {t(statusKey as any)}
          </p>
          <p className="text-white/25 text-sm">{t(hintKey as any)}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="relative pb-24 flex flex-col items-center gap-5">
        <button
          onClick={toggleRecording}
          className={`p-6 rounded-full transition-all duration-300 ${
            isRecording
              ? "bg-red-600 text-white hover:bg-red-700 scale-110 shadow-[0_0_40px_rgba(220,38,38,0.3)]"
              : "bg-white text-[var(--gray-900)] hover:bg-[var(--gray-100)] shadow-warm-lg hover:-translate-y-0.5"
          }`}
        >
          {isRecording ? (
            <MicOff className="w-8 h-8" />
          ) : (
            <Mic className="w-8 h-8" />
          )}
        </button>
        <p className="text-white/15 text-xs tracking-wide">
          {isRecording ? t("tapToStop") : t("tapToSpeak")}
        </p>
      </div>
    </div>
  );
}
