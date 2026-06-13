"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";

export type Notification = {
  id: string;
  type: string;
  title: string;
  message: string;
  link: string | null;
  read: boolean;
  created_at: string;
};

export function useNotifications(token: string | null) {
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await getNotifications(token);
      setItems(Array.isArray(data) ? data : []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useWebSocket(token, (msg) => {
    if (msg?.type === "notification") {
      setItems((prev) => [msg.notification, ...prev].slice(0, 100));
    }
  });

  const markRead = useCallback(
    async (id: string) => {
      if (!token) return;
      await markNotificationRead(token, id);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
    },
    [token],
  );

  const markAllRead = useCallback(async () => {
    if (!token) return;
    await markAllNotificationsRead(token);
    setItems((prev) => prev.map((n) => ({ ...n, read: true })));
  }, [token]);

  const unreadCount = items.filter((n) => !n.read).length;

  return { items, loading, refresh, markRead, markAllRead, unreadCount };
}
