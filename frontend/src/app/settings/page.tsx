"use client";

import { useEffect, useState } from "react";
import { api, type Profile, type StyleOption, type UserSettings } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [styles, setStyles] = useState<StyleOption[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [customPrompt, setCustomPrompt] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.settings(), api.styles(), api.profile()])
      .then(([s, st, p]) => {
        setSettings(s);
        setStyles(st);
        setProfile(p);
        setCustomPrompt(s.custom_style_prompt ?? "");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load settings."));
  }, []);

  async function selectStyle(key: string) {
    try {
      setSettings(await api.updateStyle({ diary_style: key, custom_style_prompt: "" }));
      setCustomPrompt("");
      flashSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save.");
    }
  }

  async function saveCustomPrompt() {
    try {
      setSettings(await api.updateStyle({ custom_style_prompt: customPrompt }));
      flashSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save.");
    }
  }

  function flashSaved() {
    setError(null);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const profileSections: Array<[string, string[] | string]> = profile
    ? [
        ["Current goals", profile.current_goals],
        ["Interests", profile.interests],
        ["Career", profile.career_status],
        ["Relationships", profile.relationships],
        ["Preferences", profile.preferences],
        ["Challenges", profile.challenges],
      ]
    : [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[760px] space-y-12 px-4 py-10 md:px-6">
        <section>
          <h1 className="gemini-gradient-text w-fit text-3xl font-medium">Diary style</h1>
          <p className="pb-5 pt-1.5 text-sm text-muted">
            How should LifeOS write your entries?{" "}
            {saved && <span className="font-medium text-[#6dd58c]">Saved ✓</span>}
          </p>
          {error && (
            <p className="mb-4 rounded-2xl bg-[#3c1d1f] px-4 py-3 text-sm text-[#f2b8bb]">
              {error}
            </p>
          )}

          <div className="grid gap-2.5 sm:grid-cols-2">
            {styles.map((s) => {
              const active = settings?.diary_style === s.key && !settings?.custom_style_prompt;
              return (
                <button
                  key={s.key}
                  onClick={() => selectStyle(s.key)}
                  className={`rounded-3xl p-4 text-left transition ${
                    active
                      ? "bg-[#1f3760] ring-1 ring-[#8ab4f8]/40"
                      : "bg-surface hover:bg-surface-2"
                  }`}
                >
                  <span
                    className={`text-sm font-medium capitalize ${
                      active ? "text-[#c2e7ff]" : "text-foreground"
                    }`}
                  >
                    {s.key}
                  </span>
                  <p className="pt-1 text-xs leading-5 text-muted">{s.description}</p>
                </button>
              );
            })}
          </div>

          <div className="pt-6">
            <h2 className="text-sm font-medium text-foreground">Custom style prompt</h2>
            <p className="pb-2.5 pt-1 text-xs text-muted">
              Overrides the presets. e.g. “Write under 300 words, first person, realistic tone, end
              with one lesson.”
            </p>
            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              rows={3}
              className="w-full resize-none rounded-3xl bg-surface-2 p-4 text-sm text-foreground outline-none transition placeholder:text-muted focus:bg-surface-3"
              placeholder="Describe how your diary should sound…"
            />
            <button
              onClick={saveCustomPrompt}
              className="mt-2.5 rounded-full bg-[#8ab4f8] px-5 py-2.5 text-sm font-medium text-[#062e6f] transition hover:bg-[#aecbfa]"
            >
              Save custom style
            </button>
          </div>
        </section>

        <section>
          <h1 className="gemini-gradient-text w-fit text-3xl font-medium">
            What LifeOS knows about you
          </h1>
          <p className="pb-5 pt-1.5 text-sm text-muted">
            The living profile, updated automatically after each diary entry.
          </p>
          {!profile && (
            <p className="rounded-3xl bg-surface px-6 py-10 text-center text-sm text-muted">
              Nothing yet — it builds up as you chat.
            </p>
          )}
          {profile && (
            <div className="grid gap-3 sm:grid-cols-2">
              {profileSections.map(([label, value]) => (
                <div key={label} className="rounded-3xl bg-surface p-5">
                  <h3 className="pb-2 text-xs font-medium uppercase tracking-wide text-muted">
                    {label}
                  </h3>
                  {Array.isArray(value) ? (
                    value.length ? (
                      <ul className="space-y-1.5 text-sm leading-relaxed text-[#c4c7c5]">
                        {value.map((v) => (
                          <li key={v}>{v}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-surface-3">—</p>
                    )
                  ) : (
                    <p className="text-sm text-[#c4c7c5]">{value || "—"}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="pb-6">
          <h1 className="gemini-gradient-text w-fit text-3xl font-medium">Export your data</h1>
          <p className="pb-5 pt-1.5 text-sm text-muted">You own everything. Download it anytime.</p>
          <div className="flex gap-2.5">
            {(["markdown", "json", "sqlite"] as const).map((f) => (
              <button
                key={f}
                onClick={() =>
                  api.download(f).catch((e) => setError(e instanceof Error ? e.message : "Export failed."))
                }
                className="rounded-full border border-surface-3 px-5 py-2.5 text-sm font-medium capitalize text-[#c4c7c5] transition hover:bg-surface-2"
              >
                {f}
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
