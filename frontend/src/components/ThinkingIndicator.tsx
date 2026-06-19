"use client";

export default function ThinkingIndicator() {
  return (
    <div className="flex justify-start animate-fade-in">
      <div className="bg-white rounded-3xl rounded-bl-md border border-[var(--border-subtle)] shadow-warm-sm px-6 py-4">
        <div className="flex items-center gap-2">
          <span className="thinking-dot" style={{ animationDelay: "0ms" }} />
          <span
            className="thinking-dot"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="thinking-dot"
            style={{ animationDelay: "300ms" }}
          />
        </div>
      </div>
    </div>
  );
}
