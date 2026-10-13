"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { tokenStore } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/endpoints";
import type { Alert, RealtimeMessage } from "@/lib/api/types";
import { config } from "@/lib/config";

export type ConnectionState = "connecting" | "online" | "offline";

/**
 * Keeps a WebSocket open to the API, authenticates with the first message, refreshes the
 * relevant queries when alerts/events arrive and reconnects with exponential backoff.
 */
export function useRealtime(onAlert: (alert: Alert) => void): ConnectionState {
  const queryClient = useQueryClient();
  const [state, setState] = useState<ConnectionState>("connecting");
  const onAlertRef = useRef(onAlert);

  useEffect(() => {
    onAlertRef.current = onAlert;
  }, [onAlert]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let eventRefresh: ReturnType<typeof setTimeout> | undefined;
    let closed = false;

    const refreshEvents = () => {
      // Events can arrive in bursts: refresh at most once per second.
      if (eventRefresh) return;
      eventRefresh = setTimeout(() => {
        eventRefresh = undefined;
        queryClient.invalidateQueries({ queryKey: ["events"] });
        queryClient.invalidateQueries({ queryKey: ["activity"] });
        queryClient.invalidateQueries({ queryKey: queryKeys.summaryToday });
        queryClient.invalidateQueries({ queryKey: queryKeys.cameras });
      }, 1000);
    };

    const connect = () => {
      const token = tokenStore.get();
      if (!token || closed) return;
      setState("connecting");
      socket = new WebSocket(config.wsUrl);
      socket.onopen = () => socket?.send(JSON.stringify({ type: "auth", token }));
      socket.onmessage = (message) => {
        const payload = JSON.parse(message.data as string) as RealtimeMessage;
        if (payload.type === "ready") {
          retry = 0;
          setState("online");
        } else if (payload.type === "alert.created") {
          queryClient.invalidateQueries({ queryKey: ["alerts"] });
          queryClient.invalidateQueries({ queryKey: queryKeys.alertCounts });
          onAlertRef.current(payload.data);
        } else if (payload.type === "event.created") {
          refreshEvents();
        }
      };
      socket.onclose = () => {
        setState("offline");
        if (closed) return;
        const delay = Math.min(30_000, 1000 * 2 ** retry);
        retry += 1;
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      clearTimeout(eventRefresh);
      socket?.close();
    };
  }, [queryClient]);

  return state;
}
