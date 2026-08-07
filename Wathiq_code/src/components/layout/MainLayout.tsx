import { useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { Sheet, SheetContent } from '@/components/ui/sheet';

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout = ({ children }: MainLayoutProps) => {
  const { language } = useLanguage();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const isRTL = language === 'ar';

  return (
    <div className="flex min-h-screen w-full bg-background">
      <Sidebar className="hidden lg:flex lg:shrink-0" />

      <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
        <SheetContent
          side={isRTL ? 'right' : 'left'}
          className="w-[290px] p-0 sm:max-w-[290px]"
        >
          <Sidebar mobile className="w-full" onNavigate={() => setIsSidebarOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <Header onOpenSidebar={() => setIsSidebarOpen(true)} />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
};
