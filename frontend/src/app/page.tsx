"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Conversation, type Message } from "@/lib/api";
import { MicIcon, SendIcon, SparkleIcon } from "@/components/icons";

type LocalMessage = Pick<Message, "role" | "content"> & { id: number | string };

// Web Speech API (Chrome/Edge expose it as webkitSpeechRecognition)
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as
    | (new () => SpeechRecognitionLike)
    | null;
}

export default function ChatPage() {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [ending, setEnding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [micSupported, setMicSupported] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    setMicSupported(getSpeechRecognition() !== null);
    return () => recognitionRef.current?.stop();
  }, []);

  function toggleMic() {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const Recognition = getSpeechRecognition();
    if (!Recognition) return;
    const rec = new Recognition();
    rec.lang = navigator.language || "en-US";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) transcript += result[0].transcript;
      }
      if (transcript) {
        setInput((prev) => (prev ? prev.replace(/\s+$/, "") + " " : "") + transcript.trim());
      }
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }

  const loadConversation = useCallback(async () => {
    try {
      const conv = await api.activeConversation();
      setConversation(conv);
      setMessages(await api.messages(conv.id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the backend.");
    }
  }, []);

  useEffect(() => {
    loadConversation();
  }, [loadConversation]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send() {
    const text = input.trim();
    if (!text || sending || ending) return;
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    setSending(true);
    setError(null);
    const replyId = `tmp-reply-${Date.now()}`;
    setMessages((m) => [...m, { id: `tmp-${m.length}`, role: "user", content: text }]);
    try {
      // Stream the reply token by token; one assistant bubble grows in place.
      setMessages((m) => [...m, { id: replyId, role: "assistant", content: "" }]);
      await api.chatStream(text, (soFar) => {
        setMessages((m) => m.map((msg) => (msg.id === replyId ? { ...msg, content: soFar } : msg)));
      });
    } catch (e) {
      setMessages((m) => m.filter((msg) => !(msg.id === replyId && !msg.content)));
      setError(e instanceof Error ? e.message : "Failed to send message.");
    } finally {
      setSending(false);
    }
  }

  async function endConversation() {
    if (!conversation || messages.length === 0 || ending) return;
    setEnding(true);
    setError(null);
    try {
      await api.endConversation(conversation.id);
      const ended = conversation.id;
      const poll = setInterval(async () => {
        try {
          const c = await api.conversation(ended);
          if (c.status === "completed" || c.status === "failed") {
            clearInterval(poll);
            setEnding(false);
            if (c.status === "failed") {
              setError("Diary generation failed — check the backend logs.");
            }
            await loadConversation();
          }
        } catch {
          /* keep polling */
        }
      }, 2500);
    } catch (e) {
      setEnding(false);
      setError(e instanceof Error ? e.message : "Failed to end conversation.");
    }
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      {/* Messages / greeting */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[760px] px-4 pb-6 pt-8 md:px-6">
          {empty && !error && (
            <div className="pt-[18vh]">
              <h1 className="gemini-gradient-text text-4xl font-medium leading-tight md:text-5xl">
                Hello there
              </h1>
              <p className="pt-2 text-3xl font-medium text-surface-3 md:text-4xl">
                How was your day?
              </p>
              <div className="mt-10 flex flex-wrap gap-2.5">
                {[
                  "Today was a good day, honestly",
                  "Ugh, long day. Let me vent",
                  "Something interesting happened",
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => setInput(s)}
                    className="rounded-2xl bg-surface-2 px-4 py-3 text-sm text-[#c4c7c5] transition hover:bg-surface-3"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-7">
            {messages.filter((m) => m.content).map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl rounded-tr-lg bg-surface-3 px-5 py-3 text-[15px] leading-relaxed">
                    {m.content}
                  </div>
                </div>
              ) : (
                <div key={m.id} className="flex gap-4">
                  <SparkleIcon className="mt-1 h-6 w-6 shrink-0" />
                  <div className="min-w-0 whitespace-pre-wrap pt-0.5 text-[15px] leading-relaxed text-foreground">
                    {m.content}
                  </div>
                </div>
              )
            )}
            {(ending ||
              (sending &&
                !(messages.at(-1)?.role === "assistant" && messages.at(-1)?.content))) && (
              <div className="flex gap-4">
                <SparkleIcon className="sparkle-thinking mt-1 h-6 w-6 shrink-0" />
                <p className="pt-1 text-sm text-muted">
                  {ending ? "Writing your diary entry…" : "Thinking…"}
                </p>
              </div>
            )}
            {error && (
              <p className="rounded-2xl bg-[#3c1d1f] px-4 py-3 text-sm text-[#f2b8bb]">{error}</p>
            )}
          </div>
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="shrink-0 pb-5">
        <div className="mx-auto w-full max-w-[760px] px-4 md:px-6">
          {!empty && !ending && (
            <div className="flex justify-end pb-2">
              <button
                onClick={endConversation}
                className="rounded-full border border-surface-3 px-4 py-1.5 text-xs font-medium text-[#c2e7ff] transition hover:bg-surface-2"
              >
                ✦ End &amp; write diary
              </button>
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="flex items-end gap-2 rounded-[28px] bg-surface-2 py-2 pl-6 pr-2 transition focus-within:bg-surface-3"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
              placeholder={listening ? "Listening…" : "Tell LifeOS about your day"}
              disabled={ending}
              className="max-h-40 flex-1 resize-none bg-transparent py-2.5 text-[15px] text-foreground outline-none placeholder:text-muted disabled:opacity-50"
            />
            {micSupported && (
              <button
                type="button"
                onClick={toggleMic}
                disabled={ending}
                aria-label={listening ? "Stop dictation" : "Dictate"}
                title={listening ? "Stop dictation" : "Speak instead of typing"}
                className={`mb-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition ${
                  listening
                    ? "animate-pulse bg-[#3c1d1f] text-[#f28b82]"
                    : "text-[#c4c7c5] hover:bg-surface-3"
                }`}
              >
                <MicIcon className="h-5 w-5" />
              </button>
            )}
            <button
              type="submit"
              disabled={sending || ending || !input.trim()}
              aria-label="Send"
              className={`mb-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition ${
                input.trim() && !sending && !ending
                  ? "text-[#8ab4f8] hover:bg-surface-3"
                  : "text-surface-3"
              }`}
            >
              <SendIcon className="h-5 w-5" />
            </button>
          </form>
          <p className="pt-2.5 text-center text-[11px] text-muted">
            LifeOS turns this conversation into a diary entry when you end it.
          </p>
        </div>
      </div>
    </div>
  );
}
