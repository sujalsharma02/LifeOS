const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "lifeos_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (res.status === 401 && token) {
    // Session expired — force a fresh login.
    clearToken();
    window.location.reload();
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export interface Attachment {
  id: number;
  url: string;
  filename: string;
  mime_type: string;
  resource_type: "image" | "video" | "raw";
  deleted: boolean;
  created_at: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  attachments: Attachment[];
}

export interface Conversation {
  id: number;
  status: "active" | "processing" | "completed" | "failed";
  started_at: string;
  ended_at: string | null;
}

export interface Diary {
  id: number;
  date: string;
  title: string;
  essay: string;
  mood: string | null;
  created_at: string;
}

export interface DiaryMetadata {
  summary: string;
  people: string[];
  places: string[];
  projects: string[];
  goals: string[];
  tasks: string[];
  companies: string[];
  skills: string[];
  topics: string[];
  events: string[];
  important_facts: string[];
  emotion: string | null;
  importance_score: number;
}

export interface DiaryDetail extends Diary {
  meta: DiaryMetadata | null;
}

export interface Profile {
  current_goals: string[];
  interests: string[];
  career_status: string;
  relationships: string[];
  preferences: string[];
  challenges: string[];
  updated_at: string;
}

export interface UserSettings {
  name: string;
  diary_style: string;
  custom_style_prompt: string | null;
}

export interface StyleOption {
  key: string;
  description: string;
}

export interface NamedCount {
  name: string;
  count: number;
}

export interface TimelinePoint {
  date: string;
  mood: string | null;
  emotion: string | null;
  importance: number;
}

export interface Insights {
  total_entries: number;
  total_words: number;
  first_entry_date: string | null;
  current_streak: number;
  longest_streak: number;
  mood_counts: NamedCount[];
  timeline: TimelinePoint[];
  top_people: NamedCount[];
  top_topics: NamedCount[];
  top_places: NamedCount[];
  top_projects: NamedCount[];
  weekday_counts: number[];
}

export interface SearchResult {
  id: number;
  date: string;
  title: string;
  mood: string | null;
  summary: string;
  similarity: number;
}

export interface OnThisDay {
  label: string;
  diary: Diary;
}

export interface Reflection {
  id: number;
  period_start: string;
  period_end: string;
  title: string;
  content: string;
  entry_count: number;
  created_at: string;
}

export interface AuthConfig {
  enabled: boolean;
  google_client_id: string;
}

export interface AuthUser {
  name: string;
  email: string | null;
  picture: string | null;
}

export const api = {
  authConfig: () => request<AuthConfig>("/api/auth/config"),
  googleLogin: (credential: string) =>
    request<{ token: string; user: AuthUser }>("/api/auth/google", {
      method: "POST",
      body: JSON.stringify({ credential }),
    }),
  me: () => request<AuthUser>("/api/auth/me"),
  activeConversation: () => request<Conversation>("/api/conversations/active"),
  conversation: (id: number) => request<Conversation>(`/api/conversations/${id}`),
  messages: (conversationId: number) =>
    request<Message[]>(`/api/conversations/${conversationId}/messages`),
  chat: (message: string, attachmentIds: number[] = []) =>
    request<{ conversation_id: number; reply: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, attachment_ids: attachmentIds }),
    }),
  /** Uploads a chat attachment (multipart). The browser sets the content type. */
  upload: async (file: File): Promise<Attachment> => {
    const token = getToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_URL}/api/uploads`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (res.status === 401 && token) {
      clearToken();
      window.location.reload();
    }
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    return res.json() as Promise<Attachment>;
  },
  /** Streams the reply via SSE; onUpdate receives the full text so far. Returns the final reply. */
  chatStream: async (
    message: string,
    onUpdate: (textSoFar: string) => void,
    attachmentIds: number[] = []
  ): Promise<string> => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, attachment_ids: attachmentIds }),
    });
    if (res.status === 401 && token) {
      clearToken();
      window.location.reload();
    }
    if (!res.ok || !res.body) {
      const body = await res.text().catch(() => "");
      throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const evt = JSON.parse(line.slice(6)) as { token?: string; error?: string; done?: boolean };
        if (evt.error) throw new Error(evt.error);
        if (evt.token) {
          full += evt.token;
          onUpdate(full);
        }
      }
    }
    return full;
  },
  endConversation: (id: number) =>
    request<Conversation>(`/api/conversations/${id}/end`, { method: "POST" }),
  diaries: () => request<Diary[]>("/api/diaries"),
  insights: () => request<Insights>("/api/insights"),
  search: (q: string) => request<SearchResult[]>(`/api/search?q=${encodeURIComponent(q)}`),
  onThisDay: () => request<OnThisDay[]>("/api/onthisday"),
  reflections: () => request<Reflection[]>("/api/reflections"),
  generateReflection: () =>
    request<Reflection>("/api/reflections/generate", { method: "POST" }),
  diary: (id: number) => request<DiaryDetail>(`/api/diaries/${id}`),
  profile: () => request<Profile | null>("/api/profile"),
  settings: () => request<UserSettings>("/api/settings"),
  styles: () => request<StyleOption[]>("/api/styles"),
  updateStyle: (body: { diary_style?: string; custom_style_prompt?: string }) =>
    request<UserSettings>("/api/settings/style", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  download: async (format: "markdown" | "json" | "sqlite") => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/export/${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    const blob = await res.blob();
    const names = {
      markdown: "lifeos-diaries-markdown.zip",
      json: "lifeos-diaries.json",
      sqlite: "lifeos-diaries.sqlite",
    };
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = names[format];
    a.click();
    URL.revokeObjectURL(url);
  },
};
