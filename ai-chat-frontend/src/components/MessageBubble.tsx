"use client";

import ReactMarkdown from "react-markdown";
import type { Message } from "@/lib/types";

interface Props {
  message: Message;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[85%] rounded-2xl rounded-br-md bg-sky-600 px-4 py-2 text-sm text-white shadow-md"
          style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  const showDots = isStreaming && !message.content;

  return (
    <div className="flex justify-start">
      <div
        className="max-w-[85%] rounded-2xl rounded-bl-md border border-slate-600 bg-slate-800/80 px-4 py-3 text-sm leading-relaxed text-slate-100 shadow-md [&_code]:rounded [&_code]:bg-slate-900 [&_code]:px-1 [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-4"
        style={{ wordBreak: "break-word" }}
      >
        {showDots ? (
          <span className="animate-pulse text-slate-400">…</span>
        ) : (
          <ReactMarkdown>{message.content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
