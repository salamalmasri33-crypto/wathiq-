import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { getUnreadNotificationsCountRequest } from "@/services/notifications.service";
import { hasAnyRole, NOTIFICATIONS_ALLOWED_ROLES } from "@/lib/roles";

type NotificationsContextValue = {
  unreadCount: number;
  isLoadingUnreadCount: boolean;
  refreshUnreadCount: () => Promise<number>;
  syncUnreadCount: (count: number) => void;
};

const NotificationsContext = createContext<NotificationsContextValue | undefined>(undefined);

export const NotificationsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, user } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoadingUnreadCount, setIsLoadingUnreadCount] = useState(false);

  const canUseNotifications = isAuthenticated && hasAnyRole(user, NOTIFICATIONS_ALLOWED_ROLES);

  const syncUnreadCount = useCallback((count: number) => {
    setUnreadCount(Math.max(0, count));
  }, []);

  const refreshUnreadCount = useCallback(async (): Promise<number> => {
    if (!canUseNotifications) {
      setUnreadCount(0);
      setIsLoadingUnreadCount(false);
      return 0;
    }

    try {
      setIsLoadingUnreadCount(true);
      const response = await getUnreadNotificationsCountRequest();
      const nextCount = typeof response.unreadCount === "number" ? response.unreadCount : 0;
      setUnreadCount(nextCount);
      return nextCount;
    } catch (error) {
      console.error("Failed to load unread notifications count:", error);
      setUnreadCount(0);
      return 0;
    } finally {
      setIsLoadingUnreadCount(false);
    }
  }, [canUseNotifications]);

  useEffect(() => {
    if (!canUseNotifications) {
      setUnreadCount(0);
      setIsLoadingUnreadCount(false);
      return;
    }

    void refreshUnreadCount();

    const intervalId = window.setInterval(() => {
      void refreshUnreadCount();
    }, 60000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [canUseNotifications, refreshUnreadCount, user?.id]);

  const value = useMemo<NotificationsContextValue>(
    () => ({
      unreadCount,
      isLoadingUnreadCount,
      refreshUnreadCount,
      syncUnreadCount,
    }),
    [isLoadingUnreadCount, refreshUnreadCount, syncUnreadCount, unreadCount],
  );

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
};

export function useNotifications(): NotificationsContextValue {
  const context = useContext(NotificationsContext);
  if (!context) {
    throw new Error("useNotifications must be used within a NotificationsProvider");
  }
  return context;
}
