"use client";

import { useEffect, useRef } from "react";
import { apiBaseUrl } from "@/lib/api";

type Handler = (msg: any) => void;

export function useWebSocket(token: string | null, onMessage: Handler) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    if (!token || typeof window === "undefined") return;

    const httpUrl = apiBaseUrl();
    const wsUrl = httpUrl.replace(/^http/, "ws") + `/ws/${token}`;

    let socket: WebSocket | null = null;
    let closed = false;
    let reconnectTimer: number | null = null;

    const connect = () => {
      if (closed) return;
      socket = new WebSocket(wsUrl);
      socket.onmessage = (ev) => {
        try {
          handlerRef.current(JSON.parse(ev.data));
        } catch {
          /* ignore non-JSON */
        }
      };
      socket.onclose = () => {
        if (!closed) {
          reconnectTimer = window.setTimeout(connect, 3000);
        }
      };
      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [token]);
}
