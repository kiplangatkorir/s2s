"use client";

import { useRef, useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { useAudioSocket } from "@/lib/useAudioSocket";
import { useI18n } from "@/lib/i18n";
import MessageBubble from "./MessageBubble";
import ThinkingIndicator from "./ThinkingIndicator";
import ChatInput from "./ChatInput";
import VoiceMode from "./VoiceMode";
import LanguageToggle from "./LanguageToggle";

export default function ChatUI() {
  const { t } = useI18n();
  const {
    messages,
    isRecording,
    isConnected,
    isThinking,
    isSpeaking,
    streamingText,
    toggleRecording,
    stopPlayback,
    sendText,
    setMessages,
  } = useAudioSocket(
    process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws"
  );

  const [voiceModeOpen, setVoiceModeOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText, isThinking]);

  const handleEndSession = () => {
    stopPlayback();
    setMessages([]);
  };

  const isEmpty =
    messages.length === 0 && !streamingText && !isThinking;

  return (
    <>
      <div className="flex flex-col h-screen bg-[var(--foundation-light)]">
        {/* Header */}
        <header className="shrink-0 glass border-b border-[var(--border-subtle)]">
          <div className="max-w-2xl mx-auto flex items-center justify-between px-5 py-3">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-[var(--accent-primary)] text-[10px] font-bold tracking-[0.3em] uppercase">
                  {t("brand")}
                </p>
                <h1 className="text-base font-serif font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  {t("title")}
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <LanguageToggle />

              {!isConnected && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-50 border border-red-200">
                  <WifiOff className="w-3 h-3 text-red-500" />
                  <span className="text-[10px] font-medium text-red-600">
                    {t("disconnected")}
                  </span>
                </div>
              )}

              <button
                onClick={handleEndSession}
                className="px-3.5 py-1.5 text-xs font-medium text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded-xl hover:text-[var(--accent-action)] hover:border-red-200 hover:bg-red-50 transition-all duration-200"
              >
                {t("endSession")}
              </button>
            </div>
          </div>
        </header>

        {/* Chat messages */}
        <main
          ref={scrollRef}
          className="flex-1 overflow-y-auto sauti-scroll"
        >
          <div className="max-w-2xl mx-auto px-5 py-6 space-y-4">
            {isEmpty && (
              <div className="flex flex-col items-center justify-center h-[55vh] text-center animate-fade-in">
                {/* Logo orb */}
                <div
                  className="w-20 h-20 rounded-full flex items-center justify-center mb-6"
                  style={{
                    background:
                      "radial-gradient(circle, rgba(194,65,12,0.08) 0%, rgba(194,65,12,0.02) 70%, transparent 100%)",
                  }}
                >
                  <svg
                    className="w-9 h-9 text-[var(--accent-primary)]"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="22" />
                  </svg>
                </div>

                <h2 className="font-serif text-2xl font-semibold text-[var(--text-primary)] mb-2">
                  {t("emptyTitle")}
                </h2>
                <p className="text-[var(--text-tertiary)] text-sm max-w-xs leading-relaxed">
                  {t("emptySubtitle")}
                </p>

                {/* Decorative divider */}
                <div className="mt-8 w-16 h-px bg-gradient-to-r from-transparent via-[var(--accent-primary)]/30 to-transparent" />
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble key={msg.id} role={msg.role} text={msg.text} />
            ))}

            {streamingText && (
              <MessageBubble
                role="assistant"
                text={streamingText}
                isStreaming
              />
            )}

            {isThinking && <ThinkingIndicator />}
          </div>
        </main>

        {/* Input bar */}
        <div className="shrink-0 max-w-2xl mx-auto w-full">
          <ChatInput
            onSendText={sendText}
            onOpenVoiceMode={() => setVoiceModeOpen(true)}
            disabled={isRecording}
          />
        </div>
      </div>

      {/* Voice mode overlay */}
      {voiceModeOpen && (
        <VoiceMode
          isRecording={isRecording}
          isThinking={isThinking}
          isSpeaking={isSpeaking}
          toggleRecording={toggleRecording}
          onClose={() => {
            if (isRecording) toggleRecording();
            setVoiceModeOpen(false);
          }}
        />
      )}
    </>
  );
}
