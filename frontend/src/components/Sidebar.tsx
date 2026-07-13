"use client";

/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, type ConversationSummary } from "@/lib/api";
import { useAuth } from "./AuthGate";
import { BookIcon, ChartIcon, ChatIcon, GearIcon, PlusIcon, SparkleIcon } from "./icons";

const items = [
  { href: "/", label: "Chat", icon: ChatIcon },
  { href: "/diary", label: "Diary", icon: BookIcon },
  { href: "/insights", label: "Insights", icon: ChartIcon },
  { href: "/settings", label: "Settings", icon: GearIcon },
];

/** Fired by the chat page whenever conversations change (message sent, chat ended). */
export const CHATS_CHANGED_EVENT = "lifeos:chats-changed";

function chatLabel(c: ConversationSummary): string {
  if (c.title) return c.title;
  if (c.status === "active") return "Current chat";
  const d = new Date(c.started_at);
  return `Chat from ${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

export default function Sidebar() {
  const pathname = usePathname();
  const { user, authEnabled, signOut } = useAuth();
  const [chats, setChats] = useState<ConversationSummary[]>([]);

  const refreshChats = useCallback(() => {
    api.conversations().then(setChats).catch(() => setChats([]));
  }, []);

  useEffect(() => {
    refreshChats();
    window.addEventListener(CHATS_CHANGED_EVENT, refreshChats);
    return () => window.removeEventListener(CHATS_CHANGED_EVENT, refreshChats);
  }, [refreshChats]);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden w-[264px] shrink-0 flex-col bg-surface p-3 md:flex">
        <Link href="/" className="flex items-center gap-2.5 px-3 py-3">
          <SparkleIcon className="h-6 w-6" />
          <span className="text-lg font-medium tracking-tight text-foreground">LifeOS</span>
        </Link>

        <Link
          href="/?new=1"
          className="mt-3 flex items-center gap-3 self-start rounded-full bg-surface-2 py-2.5 pl-4 pr-5 text-sm text-[#c4c7c5] transition hover:bg-surface-3"
        >
          <PlusIcon className="h-4.5 w-4.5 shrink-0" />
          New chat
        </Link>

        <nav className="mt-4 flex flex-col gap-1">
          {items.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-full px-4 py-2.5 text-sm transition ${
                  active
                    ? "bg-[#1f3760] text-[#c2e7ff]"
                    : "text-[#c4c7c5] hover:bg-surface-2"
                }`}
              >
                <Icon className="h-4.5 w-4.5 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        {chats.length > 0 && (
          <div className="mt-5 flex min-h-0 flex-1 flex-col">
            <p className="px-4 pb-1.5 text-xs font-medium text-muted">Recent</p>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {chats.map((c) => (
                <Link
                  key={c.id}
                  href={c.status === "active" ? "/" : `/?c=${c.id}`}
                  className="block truncate rounded-full px-4 py-2 text-sm text-[#c4c7c5] transition hover:bg-surface-2"
                  title={chatLabel(c)}
                >
                  {chatLabel(c)}
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="mt-auto pt-3">
          {authEnabled && user ? (
            <div className="flex items-center gap-3 rounded-2xl bg-surface-2 p-3">
              {user.picture ? (
                <img
                  src={user.picture}
                  alt=""
                  referrerPolicy="no-referrer"
                  className="h-9 w-9 shrink-0 rounded-full"
                />
              ) : (
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#1f3760] text-sm font-medium text-[#c2e7ff]">
                  {user.name.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">{user.name}</p>
                {user.email && <p className="truncate text-xs text-muted">{user.email}</p>}
              </div>
              <button
                onClick={signOut}
                title="Sign out"
                className="shrink-0 rounded-full px-2 py-1 text-xs text-muted transition hover:bg-surface-3 hover:text-foreground"
              >
                Sign out
              </button>
            </div>
          ) : (
            <div className="px-4 pb-2 text-xs leading-5 text-muted">
              Your AI diary companion.
              <br />
              Talk about your day — it writes the journal.
            </div>
          )}
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="fixed inset-x-0 top-0 z-20 flex items-center justify-between bg-surface px-4 py-2.5 md:hidden">
        <Link href="/" className="flex items-center gap-2">
          <SparkleIcon className="h-5 w-5" />
          <span className="font-medium text-foreground">LifeOS</span>
        </Link>
        <nav className="flex gap-1">
          {items.map(({ href, label }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`rounded-full px-3 py-1.5 text-sm ${
                  active ? "bg-[#1f3760] text-[#c2e7ff]" : "text-[#c4c7c5]"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );
}
