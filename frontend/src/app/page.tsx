"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { api, type Attachment, type Conversation, type Message } from "@/lib/api";
import { CHATS_CHANGED_EVENT } from "@/components/Sidebar";
import {
  BookIcon,
  CloseIcon,
  FileIcon,
  MicIcon,
  PaperclipIcon,
  SendIcon,
  SparkleIcon,
} from "@/components/icons";

function notifyChatsChanged() {
  window.dispatchEvent(new Event(CHATS_CHANGED_EVENT));
}

type LocalMessage = Pick<Message, "role" | "content"> & {
  id: number | string;
  attachments?: Attachment[];
};

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

function ChatView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const viewId = searchParams.get("c"); // set -> read-only view of a past chat
  const wantNew = searchParams.get("new") === "1";

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [viewing, setViewing] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [ending, setEnding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [micSupported, setMicSupported] = useState(false);
  const [pending, setPending] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
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
    if (!viewId) {
      setViewing(null);
      loadConversation();
      return;
    }
    (async () => {
      try {
        const conv = await api.conversation(Number(viewId));
        if (conv.status === "active") {
          router.replace("/"); // the "past" chat is actually the live one
          return;
        }
        setViewing(conv);
        setMessages(await api.messages(conv.id));
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load that conversation.");
      }
    })();
  }, [viewId, loadConversation, router]);

  // "New chat": end the current conversation (writing its diary) and start fresh.
  const newHandled = useRef(false);
  useEffect(() => {
    if (!wantNew) {
      newHandled.current = false;
      return;
    }
    if (viewId || newHandled.current || !conversation) return;
    newHandled.current = true;
    if (messages.length > 0 && conversation.status === "active") {
      endConversation();
    }
    router.replace("/");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantNew, viewId, conversation, messages.length, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function attachFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        const att = await api.upload(file);
        setPending((p) => [...p, att]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function send() {
    const text = input.trim();
    const attachments = pending;
    if ((!text && attachments.length === 0) || sending || ending || uploading || viewing) return;
    setInput("");
    setPending([]);
    if (inputRef.current) inputRef.current.style.height = "auto";
    setSending(true);
    setError(null);
    const replyId = `tmp-reply-${Date.now()}`;
    setMessages((m) => [...m, { id: `tmp-${m.length}`, role: "user", content: text, attachments }]);
    try {
      // Stream the reply token by token; one assistant bubble grows in place.
      setMessages((m) => [...m, { id: replyId, role: "assistant", content: "" }]);
      await api.chatStream(
        text,
        (soFar) => {
          setMessages((m) => m.map((msg) => (msg.id === replyId ? { ...msg, content: soFar } : msg)));
        },
        attachments.map((a) => a.id)
      );
      notifyChatsChanged();
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
            notifyChatsChanged();
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
          {viewing && (
            <div className="mb-7 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl bg-surface-2 px-4 py-3 text-sm text-[#c4c7c5]">
              <span>
                Past conversation from{" "}
                {new Date(viewing.started_at).toLocaleDateString(undefined, {
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}{" "}
                — read-only.
              </span>
              {viewing.diary_id && (
                <Link
                  href={`/diary/${viewing.diary_id}`}
                  className="flex items-center gap-1.5 text-[#c2e7ff] hover:underline"
                >
                  <BookIcon className="h-4 w-4" /> Open its diary entry
                </Link>
              )}
            </div>
          )}
          {empty && !error && !viewing && (
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
            {messages.filter((m) => m.content || m.attachments?.length).map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex flex-col items-end gap-1.5">
                  {m.attachments && m.attachments.length > 0 && (
                    <div className="flex max-w-[85%] flex-wrap justify-end gap-2">
                      {m.attachments.map((a) =>
                        a.resource_type === "image" && !a.deleted ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            key={a.id}
                            src={a.url}
                            alt={a.filename}
                            className="max-h-52 max-w-[260px] rounded-2xl object-cover"
                          />
                        ) : (
                          <a
                            key={a.id}
                            href={a.deleted ? undefined : a.url}
                            target="_blank"
                            rel="noreferrer"
                            className={`flex items-center gap-2 rounded-2xl bg-surface-2 px-3.5 py-2.5 text-sm ${
                              a.deleted ? "cursor-default text-muted" : "text-[#c4c7c5] hover:bg-surface-3"
                            }`}
                          >
                            <FileIcon className="h-4 w-4 shrink-0" />
                            <span className="max-w-[200px] truncate">{a.filename}</span>
                            {a.deleted && <span className="text-xs">(expired)</span>}
                          </a>
                        )
                      )}
                    </div>
                  )}
                  {m.content && (
                    <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl rounded-tr-lg bg-surface-3 px-5 py-3 text-[15px] leading-relaxed">
                      {m.content}
                    </div>
                  )}
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

      {/* Composer (or a back link when viewing a past chat) */}
      <div className="shrink-0 pb-5">
        <div className="mx-auto w-full max-w-[760px] px-4 md:px-6">
          {viewing ? (
            <div className="flex justify-center">
              <Link
                href="/"
                className="rounded-full border border-surface-3 px-5 py-2 text-sm font-medium text-[#c2e7ff] transition hover:bg-surface-2"
              >
                ← Back to today&apos;s chat
              </Link>
            </div>
          ) : (
            <>
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
          {(pending.length > 0 || uploading) && (
            <div className="flex flex-wrap gap-2 pb-2">
              {pending.map((a) => (
                <div
                  key={a.id}
                  className="relative flex items-center gap-2 rounded-2xl bg-surface-2 py-1.5 pl-2 pr-8"
                >
                  {a.resource_type === "image" ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={a.url} alt={a.filename} className="h-10 w-10 rounded-lg object-cover" />
                  ) : (
                    <FileIcon className="h-5 w-5 text-[#c4c7c5]" />
                  )}
                  <span className="max-w-[160px] truncate text-xs text-[#c4c7c5]">{a.filename}</span>
                  <button
                    type="button"
                    onClick={() => setPending((p) => p.filter((x) => x.id !== a.id))}
                    aria-label={`Remove ${a.filename}`}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full p-1 text-muted transition hover:bg-surface-3 hover:text-foreground"
                  >
                    <CloseIcon className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {uploading && (
                <div className="flex items-center gap-2 rounded-2xl bg-surface-2 px-3 py-2 text-xs text-muted">
                  <SparkleIcon className="sparkle-thinking h-4 w-4" /> Uploading…
                </div>
              )}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="flex items-end gap-2 rounded-[28px] bg-surface-2 py-2 pl-3 pr-2 transition focus-within:bg-surface-3"
          >
            <input
              ref={fileRef}
              type="file"
              multiple
              hidden
              onChange={(e) => attachFiles(e.target.files)}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={ending || uploading}
              aria-label="Attach a file"
              title="Attach a file"
              className="mb-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[#c4c7c5] transition hover:bg-surface-3 disabled:opacity-50"
            >
              <PaperclipIcon className="h-5 w-5" />
            </button>
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
              disabled={sending || ending || uploading || (!input.trim() && pending.length === 0)}
              aria-label="Send"
              className={`mb-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition ${
                (input.trim() || pending.length > 0) && !sending && !ending && !uploading
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  // useSearchParams requires a Suspense boundary during static prerendering.
  return (
    <Suspense fallback={null}>
      <ChatView />
    </Suspense>
  );
}
