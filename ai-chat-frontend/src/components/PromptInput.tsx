"use client";

import { useCallback } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  isLoading: boolean;
}

export function PromptInput({ value, onChange, onSend, onStop, isLoading }: Props) {
  const canSend = value.trim().length > 0 && !isLoading;

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (canSend) onSend();
      }
    },
    [canSend, onSend],
  );

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-slate-700 bg-slate-900/80 p-3">
      <textarea
        className="min-h-[88px] w-full resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:opacity-50"
        placeholder="Введите промпт… (Enter — отправить, Shift+Enter — новая строка)"
        value={value}
        disabled={isLoading}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        rows={3}
      />
      <div className="flex justify-end gap-2">
        {isLoading ? (
          <button
            type="button"
            onClick={onStop}
            className="rounded-lg border border-amber-600/60 bg-amber-900/40 px-4 py-2 text-sm font-medium text-amber-100 hover:bg-amber-900/60"
          >
            Stop
          </button>
        ) : null}
        <button
          type="button"
          disabled={!canSend}
          onClick={onSend}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        >
          Send
        </button>
      </div>
    </div>
  );
}
