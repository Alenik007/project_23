"use client";

import { ChatWindow } from "@/components/ChatWindow";
import { PromptInput } from "@/components/PromptInput";
import { useChat } from "@/hooks/useChat";

export default function HomePage() {
  const {
    messages,
    input,
    isLoading,
    error,
    info,
    setInput,
    sendMessage,
    stopGeneration,
    clearChat,
    retryLastMessage,
  } = useChat();

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-4 px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-50">AI Chat</h1>
          <p className="text-xs text-slate-400">Next.js → FastAPI (streaming)</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={retryLastMessage}
            disabled={isLoading || messages.length === 0}
            className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
          >
            Retry last
          </button>
          <button
            type="button"
            onClick={clearChat}
            className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-1.5 text-xs text-red-100 hover:bg-red-950/60"
          >
            Clear chat
          </button>
        </div>
      </header>

      <ChatWindow messages={messages} isLoading={isLoading} />

      {error ? (
        <div
          className="rounded-lg border border-red-800/60 bg-red-950/50 px-3 py-2 text-sm text-red-100"
          role="alert"
        >
          {error.message}
        </div>
      ) : null}

      {info && !error ? (
        <div className="rounded-lg border border-slate-600 bg-slate-800/60 px-3 py-2 text-sm text-slate-300">
          {info}
        </div>
      ) : null}

      <PromptInput
        value={input}
        onChange={setInput}
        onSend={sendMessage}
        onStop={stopGeneration}
        isLoading={isLoading}
      />
    </main>
  );
}
