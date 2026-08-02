"use client";

import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore } from "react";
import { KeyRound, LogIn } from "lucide-react";

import { AppUser, fetchMe, getAppToken, getStoredUser, login, logout } from "@/lib/appAuth";
import {
  identityMode,
  signIn as entraSignIn,
  signOut as entraSignOut,
} from "@/lib/auth";
import { clearSessionId } from "@/lib/session";
import Button from "./ui/Button";
import Field from "./ui/Field";
import Status from "./ui/Status";
import { Card } from "./ui/Surface";

interface AppAuthValue {
  user: AppUser;
  signOut: () => Promise<void>;
}

const AppAuthContext = createContext<AppAuthValue | null>(null);
const subscribeHydration = () => () => undefined;

export function useAppAuth(): AppAuthValue {
  const ctx = useContext(AppAuthContext);
  if (!ctx) throw new Error("useAppAuth must be used within AppAuthProvider");
  return ctx;
}

// The one application gate renders only the credential path selected at build
// time. Children render only after an actor is resolved.
export default function AppAuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const hydrated = useSyncExternalStore(subscribeHydration, () => true, () => false);
  const [resolvedUser, setResolvedUser] = useState<AppUser | null>(null);
  const [entraResolved, setEntraResolved] = useState(false);
  const mode = identityMode();
  const demoUser = mode === "demo" && hydrated && getAppToken() ? getStoredUser() : null;
  const user = resolvedUser ?? demoUser;
  const waitingForEntra = hydrated && mode === "entra" && !entraResolved;

  useEffect(() => {
    if (hydrated && mode === "entra") {
      fetchMe()
        .then((me) => setResolvedUser(me))
        .finally(() => setEntraResolved(true));
    }
    const onExpired = () => setResolvedUser(null);
    window.addEventListener("app-auth-expired", onExpired);
    return () => window.removeEventListener("app-auth-expired", onExpired);
  }, [hydrated, mode]);

  const signOut = useCallback(async () => {
    clearSessionId();
    if (mode === "entra") {
      await logout();
      await entraSignOut();
      return;
    }
    await logout();
    window.location.reload();
  }, [mode]);

  if (!hydrated || waitingForEntra) return <Loading />;
  if (!mode) return <ConfigurationError />;
  if (!user) return <SignIn mode={mode} onSignedIn={setResolvedUser} />;

  return <AppAuthContext.Provider value={{ user, signOut }}>{children}</AppAuthContext.Provider>;
}

function SignIn({ mode, onSignedIn }: { mode: "demo" | "entra"; onSignedIn: (u: AppUser) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const u = await login(username.trim(), password);
      onSignedIn(u);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  const microsoft = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await entraSignIn(); // redirect flow — navigates away
    } catch (err) {
      setError(err instanceof Error ? err.message : "Microsoft sign-in failed.");
      setBusy(false);
    }
  };

  const demoForm = mode === "demo" && (
    <>
      <Field label="Username" htmlFor="signin-username" className="mt-8">
        <input
          id="signin-username"
          data-testid="signin-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoFocus
          autoComplete="username"
          className="ui-input"
        />
      </Field>
      <Field label="Password" htmlFor="signin-password" className="mt-4">
        <input
          id="signin-password"
          data-testid="signin-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className="ui-input"
        />
      </Field>

      <Button
        type="submit"
        variant="primary"
        data-testid="signin-submit"
        disabled={busy || !username.trim() || !password}
        className="mt-6 w-full"
      >
        <LogIn size={14} strokeWidth={2.5} className="mr-2" />
        {busy ? "Signing in…" : "Sign in"}
      </Button>
    </>
  );

  return (
    <div className="min-h-screen bg-app px-6 py-10 text-text-primary">
      <div className="mx-auto flex min-h-[80vh] max-w-md items-center justify-center">
        <form
          onSubmit={submit}
          data-testid="signin-form"
          className="w-full"
        >
          <Card className="p-10">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-primary/20 text-brand-primary">
            <KeyRound size={24} />
          </div>
          <h1 className="mt-6 text-center text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Sign in</h1>
          <p className="mt-2 text-center text-sm text-text-muted">
            Your workspace is personal — sign in to load it.
          </p>

          {mode === "entra" && (
            <Button
              type="button"
              variant="primary"
              data-testid="signin-microsoft"
              onClick={microsoft}
              disabled={busy}
              className="mt-8 w-full"
            >
              <LogIn size={14} strokeWidth={2.5} className="mr-2" />
              {busy ? "Redirecting…" : "Sign in with Microsoft"}
            </Button>
          )}

          {demoForm}

          {error && (
            <Status data-testid="signin-error" tone="danger" pill={false} className="mt-4 block px-4 py-3 text-sm">
              {error}
            </Status>
          )}
          </Card>
        </form>
      </div>
    </div>
  );
}

function Loading() {
  return <div className="min-h-screen bg-app" aria-label="Checking sign-in" />;
}

function ConfigurationError() {
  return (
    <div className="min-h-screen bg-app px-6 py-10 text-text-primary">
      <div className="mx-auto flex min-h-[70vh] max-w-lg items-center justify-center text-center text-sm text-text-muted">
        Identity mode is not configured.
      </div>
    </div>
  );
}
