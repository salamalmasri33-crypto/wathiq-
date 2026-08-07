import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Bell,
  Check,
  CheckCheck,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileText,
  Info,
  RefreshCw,
} from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useNotifications } from "@/contexts/NotificationsContext";
import {
  getNotificationsRequest,
  markAllNotificationsAsReadRequest,
  markNotificationAsReadRequest,
} from "@/services/notifications.service";
import type { NotificationItem, NotificationsPage as NotificationsPageData } from "@/types/platform";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const DEFAULT_PAGE: NotificationsPageData = {
  total: 0,
  unreadCount: 0,
  page: 1,
  pageSize: 10,
  data: [],
};

function formatNotificationDate(value: string | null | undefined, locale: "ar" | "en") {
  if (!value) {
    return locale === "ar" ? "غير محدد" : "Not specified";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return locale === "ar" ? "غير محدد" : "Not specified";
  }

  return new Intl.DateTimeFormat(locale === "ar" ? "ar-SA" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function getNotificationTone(type: string | null | undefined) {
  const normalized = (type ?? "").toLowerCase();

  if (normalized.includes("reject")) {
    return {
      icon: AlertTriangle,
      className: "border-destructive/20 bg-destructive/10 text-destructive",
      badgeClassName: "border-destructive/20 bg-destructive/10 text-destructive",
    };
  }

  if (normalized.includes("approve")) {
    return {
      icon: CheckCircle2,
      className: "border-success/20 bg-success/10 text-success",
      badgeClassName: "border-success/20 bg-success/10 text-success",
    };
  }

  if (normalized.includes("transfer") || normalized.includes("update")) {
    return {
      icon: Bell,
      className: "border-warning/20 bg-warning/10 text-warning",
      badgeClassName: "border-warning/20 bg-warning/10 text-warning",
    };
  }

  return {
    icon: Info,
    className: "border-primary/20 bg-primary/10 text-primary",
    badgeClassName: "border-primary/20 bg-primary/10 text-primary",
  };
}

function getNotificationTypeLabel(type: string | null | undefined, t: (ar: string, en: string) => string) {
  const normalized = (type ?? "").toLowerCase();

  if (normalized.includes("approve")) {
    return t("اعتماد", "Approved");
  }

  if (normalized.includes("reject")) {
    return t("رفض", "Rejected");
  }

  if (normalized.includes("transfer")) {
    return t("تحويل", "Transferred");
  }

  if (normalized.includes("update")) {
    return t("تحديث", "Updated");
  }

  return t("تنبيه", "Notification");
}

function NotificationRowSkeleton() {
  return (
    <Card className="border-border/60">
      <CardContent className="p-5">
        <div className="flex items-start gap-4">
          <Skeleton className="h-11 w-11 rounded-xl" />
          <div className="min-w-0 flex-1 space-y-3">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-32" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-9 w-24 rounded-md" />
            <Skeleton className="h-9 w-24 rounded-md" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export const Notifications = () => {
  const navigate = useNavigate();
  const { language, t } = useLanguage();
  const { unreadCount, refreshUnreadCount, syncUnreadCount } = useNotifications();
  const [pageData, setPageData] = useState<NotificationsPageData>(DEFAULT_PAGE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);
  const [activeNotificationId, setActiveNotificationId] = useState<string | null>(null);

  const isRTL = language === "ar";

  const loadNotifications = useCallback(
    async (page: number) => {
      setLoading(true);
      setError(null);

      try {
        const response = await getNotificationsRequest({
          unreadOnly,
          page,
          pageSize: pageData.pageSize,
        });

        if (page > 1 && response.data.length === 0 && response.total > 0) {
          const previousPage = Math.max(1, page - 1);
          const previousResponse = await getNotificationsRequest({
            unreadOnly,
            page: previousPage,
            pageSize: pageData.pageSize,
          });
          setPageData(previousResponse);
          syncUnreadCount(previousResponse.unreadCount);
          return;
        }

        setPageData(response);
        syncUnreadCount(response.unreadCount);
      } catch (loadError) {
        console.error("Failed to load notifications:", loadError);
        setError(
          t(
            "تعذر تحميل الإشعارات حالياً. حاول مرة أخرى بعد قليل.",
            "Unable to load notifications right now. Please try again shortly.",
          ),
        );
      } finally {
        setLoading(false);
      }
    },
    [pageData.pageSize, syncUnreadCount, t, unreadOnly],
  );

  useEffect(() => {
    void loadNotifications(1);
  }, [loadNotifications]);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(pageData.total / pageData.pageSize || 1));
  }, [pageData.pageSize, pageData.total]);

  const handleMarkAsRead = async (notificationId: string) => {
    try {
      setActiveNotificationId(notificationId);
      await markNotificationAsReadRequest(notificationId);
      await loadNotifications(pageData.page);
      await refreshUnreadCount();
    } catch (markError) {
      console.error("Failed to mark notification as read:", markError);
    } finally {
      setActiveNotificationId(null);
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      setMarkingAll(true);
      await markAllNotificationsAsReadRequest();
      await loadNotifications(pageData.page);
      syncUnreadCount(0);
      await refreshUnreadCount();
    } catch (markAllError) {
      console.error("Failed to mark all notifications as read:", markAllError);
    } finally {
      setMarkingAll(false);
    }
  };

  const handleOpenDocument = async (notification: NotificationItem) => {
    try {
      if (!notification.isRead) {
        setActiveNotificationId(notification.id);
        await markNotificationAsReadRequest(notification.id);
        await refreshUnreadCount();
      }
    } catch (openError) {
      console.error("Failed to update notification before opening document:", openError);
    } finally {
      setActiveNotificationId(null);
      if (notification.documentId) {
        navigate(`/documents/${notification.documentId}`);
      }
    }
  };

  return (
    <div className="animate-fade-in p-4 sm:p-6" style={{ direction: isRTL ? "rtl" : "ltr" }}>
      <div className="mb-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Card className="border-border/60 shadow-sm">
            <CardContent className="flex items-center gap-3 p-5">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Bell className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("إجمالي الإشعارات", "Total notifications")}</p>
                <p className="text-2xl font-cairo font-bold text-foreground">{pageData.total}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/60 shadow-sm">
            <CardContent className="flex items-center gap-3 p-5">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-warning/10 text-warning">
                <Info className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("غير المقروءة", "Unread")}</p>
                <p className="text-2xl font-cairo font-bold text-foreground">{unreadCount}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/60 shadow-sm">
            <CardContent className="flex items-center gap-3 p-5">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-success/10 text-success">
                <CheckCheck className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("الصفحة الحالية", "Current page")}</p>
                <p className="text-2xl font-cairo font-bold text-foreground">
                  {pageData.page} / {totalPages}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className={cn("flex flex-col gap-3 sm:flex-row sm:flex-wrap", isRTL ? "xl:justify-start" : "xl:justify-end")}>
          <Button
            variant={unreadOnly ? "default" : "outline"}
            className={cn("w-full sm:w-auto", unreadOnly && "gradient-primary")}
            onClick={() => setUnreadOnly((current) => !current)}
          >
            {unreadOnly
              ? t("عرض الكل", "Show all")
              : t("إظهار غير المقروء فقط", "Show unread only")}
          </Button>

          <Button variant="outline" className="w-full sm:w-auto" onClick={() => void loadNotifications(pageData.page)} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2", loading && "animate-spin")} />
            {t("تحديث", "Refresh")}
          </Button>

          <Button
            className="gradient-primary w-full sm:w-auto"
            onClick={handleMarkAllAsRead}
            disabled={markingAll || unreadCount === 0}
          >
            <CheckCheck className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
            {markingAll ? t("جارٍ التحديث...", "Updating...") : t("تحديد الكل كمقروء", "Mark all as read")}
          </Button>
        </div>
      </div>

      {error && (
        <Card className="mb-6 border-destructive/20 bg-destructive/5">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {loading ? (
        <div className="space-y-4">
          <NotificationRowSkeleton />
          <NotificationRowSkeleton />
          <NotificationRowSkeleton />
        </div>
      ) : pageData.data.length === 0 ? (
        <Card className="border-dashed border-border/80 bg-card/70 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
              <Bell className="h-6 w-6" />
            </div>
            <h3 className="mb-2 text-xl font-cairo font-bold text-foreground">
              {unreadOnly
                ? t("لا توجد إشعارات غير مقروءة", "There are no unread notifications")
                : t("لا توجد إشعارات حالياً", "There are no notifications right now")}
            </h3>
            <p className="max-w-md text-sm leading-6 text-muted-foreground">
              {unreadOnly
                ? t(
                    "جميع الإشعارات تمت قراءتها. عند وصول إشعارات جديدة ستظهر هنا مباشرة.",
                    "All notifications are already read. Any new notifications will appear here right away.",
                  )
                : t(
                    "عند حدوث تحديثات على الوثائق أو سير العمل المرتبط بها ستظهر الإشعارات هنا.",
                    "Notifications about document updates and workflow activity will appear here.",
                  )}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {pageData.data.map((notification) => {
            const tone = getNotificationTone(notification.type);
            const ToneIcon = tone.icon;
            const isBusy = activeNotificationId === notification.id;

            return (
              <Card
                key={notification.id}
                className={cn(
                  "border-border/60 shadow-sm transition-colors hover:border-primary/20",
                  !notification.isRead && "border-primary/20 bg-primary/5",
                )}
              >
                <CardContent className="p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex min-w-0 flex-1 items-start gap-4">
                      <div
                        className={cn(
                          "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border",
                          tone.className,
                        )}
                      >
                        <ToneIcon className="h-5 w-5" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <h3 className="text-lg font-cairo font-bold text-foreground">
                            {notification.title || t("إشعار جديد", "New notification")}
                          </h3>

                          {!notification.isRead && (
                            <Badge className="bg-primary text-primary-foreground">
                              {t("جديد", "New")}
                            </Badge>
                          )}

                          <Badge variant="outline" className={tone.badgeClassName}>
                            {getNotificationTypeLabel(notification.type, t)}
                          </Badge>
                        </div>

                        <p className="text-sm leading-6 text-muted-foreground">
                          {notification.message ||
                            t("لا يوجد وصف إضافي لهذا الإشعار.", "There is no extra description for this notification.")}
                        </p>

                        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                          <span>{formatNotificationDate(notification.createdAt, language)}</span>
                          {notification.documentId && (
                            <span className="inline-flex items-center gap-1">
                              <FileText className="h-3.5 w-3.5" />
                              {t("مرتبطة بوثيقة", "Linked to a document")}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className={cn("grid gap-2 sm:flex sm:flex-wrap", isRTL ? "sm:justify-start" : "sm:justify-end")}>
                      {!notification.isRead && (
                        <Button
                          variant="outline"
                          className="w-full sm:w-auto"
                          onClick={() => void handleMarkAsRead(notification.id)}
                          disabled={isBusy}
                        >
                          <Check className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                          {isBusy ? t("جارٍ التحديث...", "Updating...") : t("تحديد كمقروء", "Mark as read")}
                        </Button>
                      )}

                      {notification.documentId && (
                        <Button
                          variant="default"
                          className="gradient-primary w-full sm:w-auto"
                          onClick={() => void handleOpenDocument(notification)}
                          disabled={isBusy}
                        >
                          <FileText className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                          {t("فتح الوثيقة", "Open document")}
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {!loading && pageData.total > pageData.pageSize && (
        <div className={cn("mt-6 flex flex-col gap-3 sm:flex-row sm:items-center", isRTL ? "sm:justify-start" : "sm:justify-end")}>
          <Button
            variant="outline"
            className="w-full sm:w-auto"
            onClick={() => void loadNotifications(pageData.page - 1)}
            disabled={pageData.page <= 1}
          >
            {isRTL ? <ChevronRight className="ml-2 h-4 w-4" /> : <ChevronLeft className="mr-2 h-4 w-4" />}
            {t("الصفحة السابقة", "Previous page")}
          </Button>

          <Badge variant="outline" className="justify-center px-3 py-2 text-sm">
            {t("صفحة", "Page")} {pageData.page} {t("من", "of")} {totalPages}
          </Badge>

          <Button
            variant="outline"
            className="w-full sm:w-auto"
            onClick={() => void loadNotifications(pageData.page + 1)}
            disabled={pageData.page >= totalPages}
          >
            {t("الصفحة التالية", "Next page")}
            {isRTL ? <ChevronLeft className="mr-2 h-4 w-4" /> : <ChevronRight className="ml-2 h-4 w-4" />}
          </Button>
        </div>
      )}
    </div>
  );
};

export default Notifications;
