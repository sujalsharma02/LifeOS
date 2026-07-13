"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type DiaryDetail } from "@/lib/api";

const META_FIELDS = [
  ["people", "People"],
  ["places", "Places"],
  ["projects", "Projects"],
  ["goals", "Goals"],
  ["tasks", "Tasks"],
  ["companies", "Companies"],
  ["skills", "Skills"],
  ["topics", "Topics"],
  ["events", "Events"],
] as const;

export default function DiaryDetailPage() {
  const params = useParams<{ id: string }>();
  const [diary, setDiary] = useState<DiaryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showMeta, setShowMeta] = useState(false);

  useEffect(() => {
    const id = Number(params.id);
    if (!Number.isFinite(id)) return;
    api
      .diary(id)
      .then(setDiary)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load diary."));
  }, [params.id]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[760px] px-4 py-10 md:px-6">
        <Link href="/diary" className="text-sm text-[#8ab4f8] hover:underline">
          ← All entries
        </Link>

        {error && (
          <p className="mt-4 rounded-2xl bg-[#3c1d1f] px-4 py-3 text-sm text-[#f2b8bb]">{error}</p>
        )}
        {!diary && !error && <p className="pt-6 text-sm text-muted">Loading…</p>}

        {diary && (
          <article>
            <div className="flex items-start justify-between gap-4 pt-5">
              <div>
                <h1 className="gemini-gradient-text w-fit text-3xl font-medium leading-snug">
                  {diary.title}
                </h1>
                <p className="pt-1.5 text-sm text-muted">{diary.date}</p>
              </div>
              {diary.mood && (
                <span className="mt-1 shrink-0 rounded-full bg-[#1f3760] px-3.5 py-1.5 text-sm font-medium text-[#c2e7ff]">
                  {diary.mood}
                </span>
              )}
            </div>

            <div className="mt-7 whitespace-pre-wrap rounded-3xl bg-surface p-7 text-[15px] leading-7 text-[#dadce0]">
              {diary.essay}
            </div>

            {diary.meta && (
              <div className="mt-6">
                <button
                  onClick={() => setShowMeta((s) => !s)}
                  className="rounded-full border border-surface-3 px-4 py-2 text-sm text-[#c4c7c5] transition hover:bg-surface-2"
                >
                  {showMeta ? "Hide" : "Show"} extracted memory
                </button>
                {showMeta && (
                  <div className="mt-4 space-y-5 rounded-3xl bg-surface p-6 text-sm">
                    <p className="leading-relaxed text-[#c4c7c5]">{diary.meta.summary}</p>
                    {diary.meta.important_facts.length > 0 && (
                      <div>
                        <h3 className="pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
                          Important facts
                        </h3>
                        <ul className="list-inside list-disc space-y-1 text-[#c4c7c5]">
                          {diary.meta.important_facts.map((f) => (
                            <li key={f}>{f}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-x-8 gap-y-4">
                      {META_FIELDS.map(([key, label]) => {
                        const values = diary.meta![key];
                        if (!values || values.length === 0) return null;
                        return (
                          <div key={key}>
                            <h3 className="pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
                              {label}
                            </h3>
                            <div className="flex flex-wrap gap-1.5">
                              {values.map((v) => (
                                <span
                                  key={v}
                                  className="rounded-full bg-surface-3 px-3 py-1 text-xs text-[#e3e3e3]"
                                >
                                  {v}
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <p className="text-xs text-muted">
                      emotion: {diary.meta.emotion ?? "n/a"} · importance:{" "}
                      {Math.round(diary.meta.importance_score * 100)}%
                    </p>
                  </div>
                )}
              </div>
            )}
          </article>
        )}
      </div>
    </div>
  );
}
