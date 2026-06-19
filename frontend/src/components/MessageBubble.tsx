"use client";

import { useState } from "react";
import { Copy, Check, Volume2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";

type Props = {
  role: "user" | "assistant";
  text: string;
  isStreaming?: boolean;
};

export default function MessageBubble({ role, text, isStreaming }: Props) {
  const [copied, setCopied] = useState(false);
  const { t } = useI18n();
  const isUser = role === "user";

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`flex animate-fade-in-up ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[85%] md:max-w-[75%] group transition-all duration-200 ${
          isUser
            ? "bg-[var(--foundation-dark)] text-white rounded-3xl rounded-br-md"
            : "bg-white text-[var(--text-primary)] rounded-3xl rounded-bl-md border border-[var(--border-subtle)] shadow-warm-sm"
        }`}
      >
        <div className="px-5 py-3.5">
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">
            {text}
            {isStreaming && <span className="streaming-cursor" />}
          </p>
        </div>

        <div
          className={`px-5 pb-2.5 flex items-center gap-1 ${
            isUser ? "text-white/40" : "text-[var(--text-muted)]"
          }`}
        >
          {!isUser && (
            <>
              <button
                onClick={handleCopy}
                className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-[var(--gray-100)] transition-all duration-200"
                title={t("copy")}
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
              <span className="text-[10px] font-medium tracking-wide ml-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                {copied ? t("copied") : t("copy")}
              </span>
            </>
          )}
          <Volume2 className="w-3 h-3 ml-auto opacity-40" />
        </div>
      </div>
    </div>
  );
}
