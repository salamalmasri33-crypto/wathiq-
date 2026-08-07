import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

type UiLanguage = 'en' | 'ar';

type LanguageContextValue = {
  language: UiLanguage;
  setLanguage: (lang: UiLanguage) => void;
  dir: 'ltr' | 'rtl';
  t: (ar: string, en: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

function applyLanguageToDom(lang: UiLanguage) {
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.documentElement.lang = lang;
  document.documentElement.dir = dir;
  document.body.dir = dir;
}

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // ✅ اللغة الافتراضية English
  const [language, setLanguageState] = useState<UiLanguage>('en');

  useEffect(() => {
    const saved = localStorage.getItem('ui_language');
    if (saved === 'en' || saved === 'ar') {
      setLanguageState(saved);
      applyLanguageToDom(saved);
    } else {
      // إذا ما في لغة محفوظة، نستخدم الإنجليزية
      applyLanguageToDom('en');
    }
  }, []);

  const setLanguage = (lang: UiLanguage) => {
    setLanguageState(lang);
    localStorage.setItem('ui_language', lang);
    applyLanguageToDom(lang);
  };

  const value = useMemo<LanguageContextValue>(() => {
    const dir = language === 'ar' ? 'rtl' : 'ltr';
    const t = (ar: string, en: string) => (language === 'ar' ? ar : en);
    return { language, setLanguage, dir, t };
  }, [language]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider');
  return ctx;
};