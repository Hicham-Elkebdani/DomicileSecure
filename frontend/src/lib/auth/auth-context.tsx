"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { setUnauthorizedHandler, tokenStore } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { User } from "@/lib/api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
    router.replace("/login");
  }, [queryClient, router]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    const restore = tokenStore.get()
      ? api.auth.me()
      : Promise.reject(new Error("no stored session"));
    restore
      .then((me) => {
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        tokenStore.clear();
        setStatus("anonymous");
      });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const token = await api.auth.login(email, password);
    tokenStore.set(token.access_token, token.expires_in);
    const me = await api.auth.me();
    setUser(me);
    setStatus("authenticated");
  }, []);

  const value = useMemo(() => ({ status, user, login, logout }), [status, user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
