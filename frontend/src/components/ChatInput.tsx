"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Send, Mic } from "lucide-react";
import { useI18n } from "@/lib/i18n";

type Props = {
  onSendText: (text: string) => void;
  onOpenVoiceMode: () => void;
  disabled?: boolean;
};

export default function ChatInput({
  onSendText,
  onOpenVoiceMode,
  disabled,
}: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { t } = useI18n();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  }, [text]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSendText(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasText = text.trim().length > 0;

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="flex items-end gap-1.5 bg-white rounded-2xl border border-[var(--border-subtle)] shadow-warm-sm px-2 py-1.5 transition-all duration-200 focus-within:border-[var(--accent-primary)]/40 focus-within:shadow-accent-sm">
        <button
          onClick={onOpenVoiceMode}
          className="p-2.5 text-[var(--text-muted)] hover:text-[var(--accent-primary)] transition-colors shrink-0 rounded-xl hover:bg-[var(--gray-100)]"
          title={t("voiceMode")}
        >
          <Mic className="w-[18px] h-[18px]" />
        </button>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("placeholder")}
          rows={1}
          disabled={disabled}
          className="flex-1 bg-transparent text-[var(--text-primary)] text-[15px] placeholder-[var(--text-muted)] resize-none outline-none py-2.5 leading-relaxed max-h-[150px]"
        />

        <button
          onClick={handleSend}
          disabled={!hasText || disabled}
          className={`p-2.5 rounded-xl shrink-0 transition-all duration-200 ${
            hasText && !disabled
              ? "bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-primary-hover)] shadow-accent-sm hover:-translate-y-0.5"
              : "text-[var(--gray-300)] cursor-not-allowed"
          }`}
        >
          <Send className="w-[18px] h-[18px]" />
        </button>
      </div>
    </div>
  );
}
