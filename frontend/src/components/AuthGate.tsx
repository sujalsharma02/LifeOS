"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { api, clearToken, getToken, setToken, type AuthUser } from "@/lib/api";
import { SparkleIcon } from "./icons";

interface AuthContextValue {
  user: AuthUser | null;
  authEnabled: boolean;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  authEnabled: false,
  signOut: () => {},
});

export const useAuth = () => useContext(AuthContext);

type GoogleId = {
  initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
  renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
  disableAutoSelect: () => void;
};

function getGoogleId(): GoogleId | null {
  const w = window as unknown as { google?: { accounts?: { id?: GoogleId } } };
  return w.google?.accounts?.id ?? null;
}

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<"loading" | "login" | "ready" | "offline">("loading");
  const [authEnabled, setAuthEnabled] = useState(false);
  const [clientId, setClientId] = useState("");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const config = await api.authConfig();
        setAuthEnabled(config.enabled);
        setClientId(config.google_client_id);
        if (!config.enabled) {
          setStatus("ready");
          return;
        }
        if (getToken()) {
          try {
            setUser(await api.me());
            setStatus("ready");
            return;
          } catch {
            clearToken();
          }
        }
        setStatus("login");
      } catch {
        // Backend unreachable — let pages render their own error states.
        setStatus("offline");
      }
    })();
  }, []);

  const onCredential = useCallback(async (response: { credential: string }) => {
    try {
      const res = await api.googleLogin(response.credential);
      setToken(res.token);
      setUser(res.user);
      setStatus("ready");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed.");
    }
  }, []);

  // Load the Google Identity Services script and render the official button.
  useEffect(() => {
    if (status !== "login" || !clientId) return;

    const render = () => {
      const gid = getGoogleId();
      if (!gid || !buttonRef.current) return;
      gid.initialize({ client_id: clientId, callback: onCredential });
      gid.renderButton(buttonRef.current, {
        theme: "filled_black",
        size: "large",
        shape: "pill",
        text: "signin_with",
        width: 280,
      });
    };

    if (getGoogleId()) {
      render();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = render;
    document.head.appendChild(script);
  }, [status, clientId, onCredential]);

  const signOut = useCallback(() => {
    clearToken();
    getGoogleId()?.disableAutoSelect();
    setUser(null);
    setStatus("login");
  }, []);

  if (status === "loading") {
    return (
      <div className="flex h-dvh w-full items-center justify-center">
        <SparkleIcon className="sparkle-thinking h-8 w-8" />
      </div>
    );
  }

  if (status === "login") {
    return (
      <div className="flex h-dvh w-full flex-col items-center justify-center gap-6 px-6">
        <SparkleIcon className="h-12 w-12" />
        <div className="text-center">
          <h1 className="gemini-gradient-text text-4xl font-medium">Welcome to LifeOS</h1>
          <p className="pt-3 text-sm leading-6 text-muted">
            Your AI diary companion. Talk about your day —<br />
            it remembers, so you don&apos;t have to write.
          </p>
        </div>
        <div ref={buttonRef} className="min-h-[44px]" />
        {error && (
          <p className="max-w-sm rounded-2xl bg-[#3c1d1f] px-4 py-3 text-center text-sm text-[#f2b8bb]">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, authEnabled, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
