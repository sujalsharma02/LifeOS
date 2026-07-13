"use client";

import { useEffect, useState } from "react";
import { api, type Insights, type NamedCount, type Reflection, type TimelinePoint } from "@/lib/api";
import { SparkleIcon } from "@/components/icons";

// Chart hues validated for this dark surface (dataviz palette check):
// blue for the primary magnitude context, aqua for the second one on screen.
const BLUE = "#3987e5";
const AQUA = "#199e70";
const GRID = "#2c2e30";
const AXIS_TEXT = "#9aa0a6";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function friendlyError(e: unknown, fallback: string): string {
  const msg = e instanceof Error ? e.message : fallback;
  // Backend errors arrive as `API 400: {"detail":"…"}` — surface just the detail.
  const m = msg.match(/"detail"\s*:\s*"([^"]+)"/);
  return m ? m[1] : msg;
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-3xl bg-surface p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="pt-1.5 text-3xl font-semibold text-foreground">{value}</p>
      {hint && <p className="pt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

function BarList({ title, items, color }: { title: string; items: NamedCount[]; color: string }) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="rounded-3xl bg-surface p-5">
      <h2 className="pb-4 text-sm font-medium text-foreground">{title}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-muted">Nothing yet.</p>
      ) : (
        <div className="space-y-3">
          {items.map((i) => (
            <div key={i.name}>
              <div className="flex items-baseline justify-between gap-3 pb-1">
                <span className="truncate text-sm text-[#c4c7c5]">{i.name}</span>
                <span className="shrink-0 text-xs tabular-nums text-muted">{i.count}</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-r">
                <div
                  className="h-full rounded-r"
                  style={{ width: `${(i.count / max) * 100}%`, background: color }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function WeekdayChart({ counts }: { counts: number[] }) {
  const max = Math.max(...counts, 1);
  return (
    <div className="rounded-3xl bg-surface p-5">
      <h2 className="pb-4 text-sm font-medium text-foreground">Journaling rhythm</h2>
      <div className="flex items-end gap-2" style={{ height: 120 }} role="img"
        aria-label={`Entries per weekday: ${counts.map((c, i) => `${WEEKDAYS[i]} ${c}`).join(", ")}`}>
        {counts.map((c, i) => (
          <div key={WEEKDAYS[i]} className="flex flex-1 flex-col items-center justify-end gap-1.5 self-stretch">
            {c > 0 && <span className="text-[11px] tabular-nums text-muted">{c}</span>}
            <div
              className="w-full max-w-6 rounded-t"
              style={{ height: `${(c / max) * 78}%`, minHeight: c > 0 ? 3 : 0, background: BLUE }}
            />
            <span className="text-[11px] text-muted">{WEEKDAYS[i]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TimelineChart({ points }: { points: TimelinePoint[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640;
  const H = 180;
  const PAD = { top: 14, right: 14, bottom: 26, left: 34 };
  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;

  if (points.length === 0) return null;
  const x = (i: number) => PAD.left + (points.length === 1 ? iw / 2 : (i / (points.length - 1)) * iw);
  const y = (v: number) => PAD.top + (1 - v) * ih;
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.importance).toFixed(1)}`).join(" ");
  const hovered = hover !== null ? points[hover] : null;

  return (
    <div className="rounded-3xl bg-surface p-5">
      <div className="flex items-baseline justify-between pb-1">
        <h2 className="text-sm font-medium text-foreground">Days that mattered</h2>
        <span className="text-xs text-muted">importance per entry</span>
      </div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          onMouseLeave={() => setHover(null)}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - rect.left) / rect.width) * W;
            let best = 0;
            for (let i = 1; i < points.length; i++) {
              if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
            }
            setHover(best);
          }}
        >
          {[0, 0.5, 1].map((v) => (
            <g key={v}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke={GRID} strokeWidth={1} />
              <text x={PAD.left - 8} y={y(v) + 3.5} textAnchor="end" fontSize={10} fill={AXIS_TEXT}>
                {Math.round(v * 100)}%
              </text>
            </g>
          ))}
          <text x={PAD.left} y={H - 8} fontSize={10} fill={AXIS_TEXT}>
            {points[0].date}
          </text>
          <text x={W - PAD.right} y={H - 8} textAnchor="end" fontSize={10} fill={AXIS_TEXT}>
            {points[points.length - 1].date}
          </text>

          {hover !== null && (
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + ih} stroke={GRID} strokeWidth={1} />
          )}
          <path d={path} fill="none" stroke={BLUE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {points.map((p, i) => (
            <circle
              key={p.date + i}
              cx={x(i)}
              cy={y(p.importance)}
              r={hover === i ? 5 : 4}
              fill={BLUE}
              stroke="var(--surface)"
              strokeWidth={2}
            />
          ))}
        </svg>
        {hovered && hover !== null && (
          <div
            className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-xl bg-surface-3 px-3 py-2 text-xs shadow-lg"
            style={{ left: `${(x(hover) / W) * 100}%` }}
          >
            <p className="font-medium text-foreground">{hovered.date}</p>
            <p className="pt-0.5 text-muted">
              {Math.round(hovered.importance * 100)}% important
              {hovered.mood ? ` · ${hovered.mood}` : ""}
              {hovered.emotion ? ` · ${hovered.emotion}` : ""}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insights | null>(null);
  const [reflections, setReflections] = useState<Reflection[]>([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reflectionError, setReflectionError] = useState<string | null>(null);

  useEffect(() => {
    api.insights().then(setInsights).catch((e) => setError(friendlyError(e, "Failed to load insights.")));
    api.reflections().then(setReflections).catch(() => {});
  }, []);

  async function generate() {
    setGenerating(true);
    setReflectionError(null);
    try {
      const r = await api.generateReflection();
      setReflections((rs) => [r, ...rs.filter((x) => x.id !== r.id)]);
    } catch (e) {
      setReflectionError(friendlyError(e, "Could not generate a reflection."));
    } finally {
      setGenerating(false);
    }
  }

  const latest = reflections[0];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[760px] px-4 py-10 md:px-6">
        <h1 className="gemini-gradient-text w-fit text-3xl font-medium">Insights</h1>
        <p className="pb-8 pt-1.5 text-sm text-muted">
          Patterns from your diary — streaks, moods, people, and what mattered.
        </p>

        {error && (
          <p className="rounded-2xl bg-[#3c1d1f] px-4 py-3 text-sm text-[#f2b8bb]">{error}</p>
        )}

        {insights && insights.total_entries === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-3xl bg-surface px-6 py-16 text-center">
            <SparkleIcon className="h-8 w-8 opacity-60" />
            <p className="text-sm text-muted">
              No data yet. Chat about your day and end the conversation — insights build from your entries.
            </p>
          </div>
        )}

        {insights && insights.total_entries > 0 && (
          <div className="space-y-4">
            {/* KPI row */}
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile
                label="Current streak"
                value={`${insights.current_streak}d`}
                hint={insights.current_streak > 0 ? "keep it going" : "chat today to restart"}
              />
              <StatTile label="Longest streak" value={`${insights.longest_streak}d`} />
              <StatTile label="Entries" value={insights.total_entries.toLocaleString()}
                hint={insights.first_entry_date ? `since ${insights.first_entry_date}` : undefined} />
              <StatTile label="Words written" value={insights.total_words.toLocaleString()} hint="by your companion, for you" />
            </div>

            {/* Weekly reflection */}
            <div className="rounded-3xl bg-surface p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-medium text-foreground">Weekly reflection</h2>
                <button
                  onClick={generate}
                  disabled={generating}
                  className="rounded-full border border-surface-3 px-4 py-1.5 text-xs font-medium text-[#c2e7ff] transition hover:bg-surface-2 disabled:opacity-50"
                >
                  {generating ? "Reflecting…" : latest ? "✦ Regenerate" : "✦ Reflect on my week"}
                </button>
              </div>
              {reflectionError && (
                <p className="mt-3 rounded-2xl bg-[#3c1d1f] px-4 py-3 text-sm text-[#f2b8bb]">{reflectionError}</p>
              )}
              {latest ? (
                <div className="pt-4">
                  <h3 className="gemini-gradient-text w-fit text-xl font-medium">{latest.title}</h3>
                  <p className="pt-1 text-xs text-muted">
                    {latest.period_start} → {latest.period_end} · {latest.entry_count}{" "}
                    {latest.entry_count === 1 ? "entry" : "entries"}
                  </p>
                  <p className="whitespace-pre-wrap pt-3 text-[15px] leading-7 text-[#dadce0]">{latest.content}</p>
                </div>
              ) : (
                <p className="pt-3 text-sm text-muted">
                  Once you have a few entries, LifeOS can write you a week-in-review: the arc, the wins,
                  the patterns, and one suggestion.
                </p>
              )}
              {reflections.length > 1 && (
                <details className="pt-4">
                  <summary className="cursor-pointer text-xs text-muted hover:text-foreground">
                    Past reflections ({reflections.length - 1})
                  </summary>
                  <div className="space-y-5 pt-3">
                    {reflections.slice(1).map((r) => (
                      <div key={r.id} className="rounded-2xl bg-surface-2 p-4">
                        <p className="text-sm font-medium text-foreground">{r.title}</p>
                        <p className="pt-0.5 text-xs text-muted">{r.period_start} → {r.period_end}</p>
                        <p className="whitespace-pre-wrap pt-2 text-sm leading-6 text-[#c4c7c5]">{r.content}</p>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>

            <TimelineChart points={insights.timeline} />

            <div className="grid gap-4 sm:grid-cols-2">
              <BarList title="People in your life" items={insights.top_people} color={BLUE} />
              <BarList title="What you talk about" items={insights.top_topics} color={AQUA} />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <BarList title="Moods" items={insights.mood_counts} color={BLUE} />
              <WeekdayChart counts={insights.weekday_counts} />
            </div>

            {(insights.top_projects.length > 0 || insights.top_places.length > 0) && (
              <div className="grid gap-4 sm:grid-cols-2">
                <BarList title="Projects" items={insights.top_projects} color={BLUE} />
                <BarList title="Places" items={insights.top_places} color={AQUA} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
