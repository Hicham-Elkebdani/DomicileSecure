"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Spinner } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth/auth-context";

/** Every page in this group requires a signed-in user. */
export default function ProtectedLayout({ children }: LayoutProps<"/">) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated") return <Spinner />;
  return <AppShell>{children}</AppShell>;
}
