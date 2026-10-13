"use client";

import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ErrorBox } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { useAuth } from "@/lib/auth/auth-context";

export default function LoginPage() {
  const { login, status } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (status === "authenticated") router.replace("/");
  }, [status, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.replace("/");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex size-12 items-center justify-center rounded-xl bg-accent text-accent-ink">
            <ShieldCheck className="size-6" aria-hidden />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-ink">DomicileSecure</h1>
            <p className="text-sm text-ink-muted">Connectez-vous pour surveiller votre domicile</p>
          </div>
        </div>
        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-xl border border-border bg-surface-1 p-6 shadow-xs"
        >
          <Field label="E-mail">
            <Input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field label="Mot de passe">
            <Input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {error !== null && <ErrorBox error={error} />}
          <Button type="submit" className="w-full" loading={submitting}>
            Se connecter
          </Button>
        </form>
      </div>
    </main>
  );
}
