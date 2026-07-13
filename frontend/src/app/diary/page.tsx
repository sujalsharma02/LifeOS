"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, type Diary, type OnThisDay, type SearchResult } from "@/lib/api";
import { SparkleIcon } from "@/components/icons";

export default function DiaryListPage() {
  const [diaries, setDiaries] = useState<Diary[] | null>(null);
  const [memories, setMemories] = useState<OnThisDay[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api
      .diaries()
      .then(setDiaries)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load diaries."));
    api.onThisDay().then(setMemories).catch(() => {});
  }, []);

  // Debounced semantic search — meaning-based, so "the week I felt stuck" works.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length < 3) {
      setResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const r = await api.search(q);
        setResults(r);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed.");
      } finally {
        setSearching(false);
      }
    }, 450);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const showingSearch = query.trim().length >= 3;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[760px] px-4 py-10 md:px-6">
        <h1 className="gemini-gradient-text w-fit text-3xl font-medium">Your diary</h1>
        <p className="pb-6 pt-1.5 text-sm text-muted">
          Every entry here was written from a conversation.
        </p>

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by meaning — “the week I felt stuck”, “dinner with mom”…"
          className="mb-6 w-full rounded-full bg-surface-2 px-5 py-3 text-sm text-foreground outline-none transition placeholder:text-muted focus:bg-surface-3"
        />

        {error && (
          <p className="mb-4 rounded-2xl bg-[#3c1d1f] px-4 py-3 text-sm text-[#f2b8bb]">{error}</p>
        )}

        {/* On this day — resurfaced memories */}
        {!showingSearch && memories.length > 0 && (
          <div className="mb-8">
            <h2 className="pb-2.5 text-xs font-medium uppercase tracking-wide text-muted">
              On this day
            </h2>
            <div className="grid gap-2.5 sm:grid-cols-3">
              {memories.map((m) => (
                <Link
                  key={m.label}
                  href={`/diary/${m.diary.id}`}
                  className="rounded-3xl bg-[#1f3760]/40 p-4 transition hover:bg-[#1f3760]/70"
                >
                  <p className="text-xs font-medium text-[#c2e7ff]">{m.label}</p>
                  <p className="truncate pt-1.5 text-sm font-medium text-foreground">
                    {m.diary.title}
                  </p>
                  <p className="line-clamp-2 pt-1 text-xs leading-5 text-[#c4c7c5]">
                    {m.diary.essay}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Semantic search results */}
        {showingSearch && (
          <div className="space-y-3">
            {searching && <p className="text-sm text-muted">Searching your memories…</p>}
            {!searching && results && results.length === 0 && (
              <p className="rounded-3xl bg-surface px-6 py-10 text-center text-sm text-muted">
                Nothing similar found.
              </p>
            )}
            {results?.map((r) => (
              <Link
                key={r.id}
                href={`/diary/${r.id}`}
                className="block rounded-3xl bg-surface p-5 transition hover:bg-surface-2"
              >
                <div className="flex items-center justify-between gap-3">
                  <h2 className="truncate font-medium text-foreground">{r.title}</h2>
                  <span className="shrink-0 text-xs tabular-nums text-muted">
                    {Math.round(r.similarity * 100)}% match
                  </span>
                </div>
                <p className="pt-1 text-xs text-muted">
                  {r.date}
                  {r.mood ? ` · ${r.mood}` : ""}
                </p>
                <p className="line-clamp-2 pt-2.5 text-sm leading-relaxed text-[#c4c7c5]">
                  {r.summary}
                </p>
              </Link>
            ))}
          </div>
        )}

        {/* Full list */}
        {!showingSearch && (
          <>
            {diaries && diaries.length === 0 && (
              <div className="flex flex-col items-center gap-3 rounded-3xl bg-surface px-6 py-16 text-center">
                <SparkleIcon className="h-8 w-8 opacity-60" />
                <p className="text-sm text-muted">
                  No entries yet. Go chat about your day, then hit “End &amp; write diary”.
                </p>
              </div>
            )}

            <div className="space-y-3">
              {diaries?.map((d) => (
                <Link
                  key={d.id}
                  href={`/diary/${d.id}`}
                  className="block rounded-3xl bg-surface p-5 transition hover:bg-surface-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="truncate font-medium text-foreground">{d.title}</h2>
                    {d.mood && (
                      <span className="shrink-0 rounded-full bg-[#1f3760] px-3 py-1 text-xs font-medium text-[#c2e7ff]">
                        {d.mood}
                      </span>
                    )}
                  </div>
                  <p className="pt-1 text-xs text-muted">{d.date}</p>
                  <p className="line-clamp-2 pt-2.5 text-sm leading-relaxed text-[#c4c7c5]">
                    {d.essay}
                  </p>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
