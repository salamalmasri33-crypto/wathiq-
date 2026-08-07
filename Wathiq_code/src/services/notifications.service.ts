import api from "@/config/api";
import type {
  NotificationItem,
  NotificationsPage,
  NotificationsQuery,
  UnreadNotificationsResponse,
} from "@/types/platform";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeNotificationItem(value: unknown): NotificationItem | null {
  if (!isRecord(value)) {
    return null;
  }

  return {
    id: typeof value.id === "string" ? value.id : "",
    userId: typeof value.userId === "string" ? value.userId : null,
    documentId: typeof value.documentId === "string" ? value.documentId : null,
    institutionId: typeof value.institutionId === "string" ? value.institutionId : null,
    type: typeof value.type === "string" ? value.type : null,
    title: typeof value.title === "string" ? value.title : null,
    message: typeof value.message === "string" ? value.message : null,
    isRead: typeof value.isRead === "boolean" ? value.isRead : false,
    createdAt: typeof value.createdAt === "string" ? value.createdAt : null,
    readAt: typeof value.readAt === "string" ? value.readAt : null,
  };
}

function normalizeNotificationsPage(value: unknown): NotificationsPage {
  if (!isRecord(value)) {
    return {
      total: 0,
      unreadCount: 0,
      page: 1,
      pageSize: 20,
      data: [],
    };
  }

  const rawItems = Array.isArray(value.data)
    ? value.data
    : Array.isArray(value.items)
    ? value.items
    : Array.isArray(value.notifications)
    ? value.notifications
    : [];

  return {
    total: typeof value.total === "number" ? value.total : rawItems.length,
    unreadCount:
      typeof value.unreadCount === "number"
        ? value.unreadCount
        : rawItems.filter((item) => isRecord(item) && item.isRead === false).length,
    page: typeof value.page === "number" ? value.page : 1,
    pageSize: typeof value.pageSize === "number" ? value.pageSize : 20,
    data: rawItems
      .map(normalizeNotificationItem)
      .filter((item): item is NotificationItem => Boolean(item && item.id)),
  };
}

export async function getNotificationsRequest(
  params: NotificationsQuery = {},
): Promise<NotificationsPage> {
  const response = await api.get<unknown>("/notifications", { params });
  return normalizeNotificationsPage(response.data);
}

export async function getUnreadNotificationsCountRequest(): Promise<UnreadNotificationsResponse> {
  const response = await api.get<UnreadNotificationsResponse>("/notifications/unread-count");
  return response.data;
}

export async function markNotificationAsReadRequest(notificationId: string): Promise<unknown> {
  const response = await api.post(`/notifications/${notificationId}/read`);
  return response.data;
}

export async function markAllNotificationsAsReadRequest(): Promise<unknown> {
  const response = await api.post("/notifications/read-all");
  return response.data;
}
