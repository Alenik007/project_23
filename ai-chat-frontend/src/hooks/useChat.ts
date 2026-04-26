"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, streamGenerateText } from "@/lib/api";
import type { ChatError, Message } from "@/lib/types";

const SESSION_KEY = "ai-chat-messages-v1";

function newId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function mapApiError(err: unknown): ChatError {
  if (err instanceof ApiError) {
    return { message: err.message, status: err.status };
  }
  if (err instanceof TypeError) {
    return { message: "Backend is unavailable. Please try again." };
  }
  if (err instanceof Error) {
    return { message: err.message };
  }
  return { message: "Unknown error." };
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ChatError | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Message[];
        if (Array.isArray(parsed)) setMessages(parsed);
      }
    } catch {
      /* ignore */
    }
    setSessionReady(true);
  }, []);

  useEffect(() => {
    if (!sessionReady) return;
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(messages));
    } catch {
      /* ignore */
    }
  }, [messages, sessionReady]);

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
    setInfo("Generation stopped.");
  }, []);

  const clearChat = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setMessages([]);
    setError(null);
    setInfo(null);
    setIsLoading(false);
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const sendMessage = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setError(null);
    setInfo(null);
    setIsLoading(true);

    const userMsg: Message = {
      id: newId(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
    };
    const assistantId = newId();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamGenerateText(trimmed, {
        signal: controller.signal,
        onToken: (chunk) => {
          setMessages((prev) => {
            const next = [...prev];
            const idx = next.findIndex((m) => m.id === assistantId);
            if (idx === -1) return prev;
            next[idx] = { ...next[idx], content: next[idx].content + chunk };
            return next;
          });
        },
      });
    } catch (e) {
      const aborted =
        (e instanceof DOMException || e instanceof Error) && (e as Error).name === "AbortError";
      if (aborted) {
        setInfo("Generation stopped.");
      } else if (e instanceof ApiError) {
        let msg = e.message;
        if (e.status === 429) msg = "Rate limit exceeded. Please wait and try again.";
        else if (e.status === 422) msg = "Invalid input. Check prompt length and parameters.";
        else if (e.status === 400) msg = "Prompt rejected by security filter.";
        else if (e.status !== undefined && e.status >= 500) {
          msg = "Server error. Please try again later.";
        }
        setError({ message: msg, status: e.status });
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      } else {
        setError(mapApiError(e));
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [input, isLoading]);

  const retryLastMessage = useCallback(async () => {
    if (isLoading) return;
    setError(null);
    setInfo(null);

    const copy = [...messages];
    let userPrompt: string | null = null;
    while (copy.length > 0 && copy[copy.length - 1]?.role === "assistant") {
      copy.pop();
    }
    const last = copy[copy.length - 1];
    if (!last || last.role !== "user") return;
    userPrompt = last.content;

    const assistantId = newId();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
    };

    setMessages([...copy, assistantMsg]);
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamGenerateText(userPrompt, {
        signal: controller.signal,
        onToken: (chunk) => {
          setMessages((prev) => {
            const next = [...prev];
            const idx = next.findIndex((m) => m.id === assistantId);
            if (idx === -1) return prev;
            next[idx] = { ...next[idx], content: next[idx].content + chunk };
            return next;
          });
        },
      });
    } catch (e) {
      const aborted =
        (e instanceof DOMException || e instanceof Error) && (e as Error).name === "AbortError";
      if (aborted) {
        setInfo("Generation stopped.");
      } else if (e instanceof ApiError) {
        let msg = e.message;
        if (e.status === 429) msg = "Rate limit exceeded. Please wait and try again.";
        else if (e.status === 422) msg = "Invalid input. Check prompt length and parameters.";
        else if (e.status === 400) msg = "Prompt rejected by security filter.";
        else if (e.status !== undefined && e.status >= 500) {
          msg = "Server error. Please try again later.";
        }
        setError({ message: msg, status: e.status });
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      } else {
        setError(mapApiError(e));
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [messages, isLoading]);

  return {
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
  };
}
