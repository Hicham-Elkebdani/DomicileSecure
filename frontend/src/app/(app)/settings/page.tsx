"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BellOff, BellRing, Send } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ErrorBox, Spinner } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { api, queryKeys } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth/auth-context";
import { currentSubscription, disablePush, enablePush, pushSupported } from "@/lib/push/push";

function PushSettings() {
  const { notify } = useToast();
  const config = useQuery({ queryKey: queryKeys.pushConfig, queryFn: api.notifications.config });
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  // Rendered only after the config query resolves (client side), so no hydration mismatch.
  const [supported] = useState(pushSupported);

  useEffect(() => {
    if (supported) currentSubscription().then((s) => setSubscribed(Boolean(s)));
  }, [supported]);

  const toggle = useMutation({
    mutationFn: async () => {
      if (subscribed) await disablePush();
      else await enablePush(config.data?.vapid_public_key ?? "");
      return !subscribed;
    },
    onSuccess: (enabled) => {
      setSubscribed(enabled);
      notify({ title: enabled ? "Notifications activées sur cet appareil" : "Notifications désactivées" });
    },
  });
  const test = useMutation({
    mutationFn: api.notifications.test,
    onSuccess: (result) => notify({ title: result.message }),
  });

  if (config.isPending) return <Spinner />;
  if (config.error) return <ErrorBox error={config.error} />;
  if (!config.data?.enabled) {
    return (
      <p className="text-sm text-ink-muted">
        Les notifications push ne sont pas configurées côté serveur. Générez les clés avec{" "}
        <code className="rounded bg-surface-2 px-1">python scripts/generate_secrets.py</code> et
        renseignez <code className="rounded bg-surface-2 px-1">VAPID_PUBLIC_KEY</code> /{" "}
        <code className="rounded bg-surface-2 px-1">VAPID_PRIVATE_KEY</code> dans le .env de l&apos;API.
      </p>
    );
  }
  if (!supported) {
    return <p className="text-sm text-ink-muted">Ce navigateur ne prend pas en charge les notifications push.</p>;
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-muted">
        Recevez les alertes importantes même lorsque l&apos;application est fermée. Les alertes de faible
        gravité restent visibles dans le tableau de bord uniquement.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant={subscribed ? "secondary" : "primary"}
          loading={toggle.isPending}
          disabled={subscribed === null}
          onClick={() => toggle.mutate()}
        >
          {subscribed ? <BellOff className="size-4" aria-hidden /> : <BellRing className="size-4" aria-hidden />}
          {subscribed ? "Désactiver sur cet appareil" : "Activer sur cet appareil"}
        </Button>
        {subscribed && (
          <Button variant="ghost" loading={test.isPending} onClick={() => test.mutate()}>
            <Send className="size-4" aria-hidden /> Envoyer un test
          </Button>
        )}
      </div>
      {toggle.error && <ErrorBox error={toggle.error} />}
      {test.error && <ErrorBox error={test.error} />}
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title="Paramètres" />
      <div className="space-y-6">
        <Card>
          <CardHeader title="Notifications push" />
          <CardBody>
            <PushSettings />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Compte" />
          <CardBody>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-muted">E-mail</dt>
                <dd className="text-ink">{user?.email}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Rôle</dt>
                <dd className="text-ink">{user?.is_admin ? "Administrateur" : "Membre"}</dd>
              </div>
            </dl>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
