"use client";

import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import type { Message } from "@/lib/types";

interface Props {
  messages: Message[];
  isLoading: boolean;
}

export function ChatWindow({ messages, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-600 bg-slate-900/40 p-8 text-center text-slate-400">
        <p className="text-lg font-medium text-slate-200">Добро пожаловать</p>
        <p className="max-w-md text-sm">
          Введите сообщение ниже. Ответ модели приходит потоком с бэкенда{" "}
          <code className="rounded bg-slate-800 px-1 py-0.5 text-xs">/generate/stream</code>.
        </p>
      </div>
    );
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const streamingAssistantId = isLoading ? lastAssistant?.id : undefined;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-900/50">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            isStreaming={m.id === streamingAssistantId}
          />
        ))}
        {isLoading && (
          <p className="text-xs text-slate-500" aria-live="polite">
            Model is typing…
          </p>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
