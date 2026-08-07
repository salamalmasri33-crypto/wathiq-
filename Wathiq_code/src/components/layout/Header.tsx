import { FormEvent, useState } from "react";
import { Bell, Menu, Search as SearchIcon } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useLanguage } from "@/contexts/LanguageContext";
import { useNotifications } from "@/contexts/NotificationsContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type HeaderProps = {
  onOpenSidebar: () => void;
};

export const Header = ({ onOpenSidebar }: HeaderProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language, t } = useLanguage();
  const { unreadCount, isLoadingUnreadCount } = useNotifications();
  const [searchQuery, setSearchQuery] = useState("");

  const isRTL = language === "ar";
  const isNotificationsPage = location.pathname === "/notifications";

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchQuery.trim();

    if (query) {
      navigate(`/search?q=${encodeURIComponent(query)}`);
      return;
    }

    navigate("/search");
  };

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-card/95 backdrop-blur">
      <div className="px-3 py-3 sm:px-4 lg:px-6">
        <div className="flex items-center gap-2 sm:gap-3" dir="ltr">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-11 w-11 rounded-xl lg:hidden"
            onClick={onOpenSidebar}
            aria-label={t("فتح القائمة", "Open menu")}
          >
            <Menu className="h-5 w-5" />
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn(
              "relative h-11 w-11 rounded-xl text-foreground hover:bg-muted/60",
              isNotificationsPage && "bg-primary/8 text-primary hover:bg-primary/10",
            )}
            onClick={() => navigate("/notifications")}
            aria-label={t("فتح صفحة الإشعارات", "Open notifications page")}
          >
            <Bell className="h-5 w-5" />
            {!isLoadingUnreadCount && unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground shadow-sm">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </Button>

          <form onSubmit={handleSearchSubmit} className="flex-1">
            <div className="relative w-full">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder={t(
                  "ابحث في الوثائق، الأقسام، المراجع...",
                  "Search documents, departments, references...",
                )}
                dir={isRTL ? "rtl" : "ltr"}
                className={cn(
                  "h-11 rounded-2xl border-border bg-background pl-10 shadow-none transition-colors focus-visible:ring-1 focus-visible:ring-primary",
                  isRTL ? "text-right pr-4" : "text-left pr-4",
                )}
              />
            </div>
          </form>
        </div>
      </div>
    </header>
  );
};
