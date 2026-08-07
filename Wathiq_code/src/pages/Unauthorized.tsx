import { useNavigate } from 'react-router-dom';
import { useLanguage } from '@/contexts/LanguageContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ShieldAlert } from 'lucide-react';

export default function Unauthorized() {
  const navigate = useNavigate();
  const { language, t } = useLanguage();

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-destructive/5 p-4"
      style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}
    >
      <Card className="w-full max-w-md text-center animate-slide-up">
        <CardContent className="pt-12 pb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-destructive/10 mb-6 animate-bounce-in">
            <ShieldAlert className="w-10 h-10 text-destructive" />
          </div>

          <h1 className="text-3xl font-cairo font-bold text-foreground mb-3">
            {t('غير مصرح لك بالدخول', 'Unauthorized')}
          </h1>

          <p className="text-muted-foreground mb-8">
            {t('عذراً، ليس لديك صلاحية الوصول إلى هذه الصفحة', "Sorry, you don't have permission to access this page")}
          </p>

          <div className="space-y-3">
            <Button onClick={() => navigate('/dashboard')} className="w-full gradient-primary hover-glow">
              {t('العودة إلى لوحة التحكم', 'Back to dashboard')}
            </Button>
            <Button onClick={() => navigate('/login')} variant="outline" className="w-full">
              {t('تسجيل الخروج', 'Logout')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
