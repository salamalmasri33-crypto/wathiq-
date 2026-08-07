import { useLanguage } from '@/contexts/LanguageContext';

type EmptyModulePageProps = {
  titleAr: string;
  titleEn: string;
};

export const EmptyModulePage = ({ titleAr, titleEn }: EmptyModulePageProps) => {
  const { language } = useLanguage();

  return (
    <div className="p-6 animate-fade-in" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
      <div className="mb-6">
        <h1 className="text-3xl font-cairo font-bold text-foreground">
          {language === 'ar' ? titleAr : titleEn}
        </h1>
      </div>
    </div>
  );
};
