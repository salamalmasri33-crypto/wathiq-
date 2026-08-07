import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { useToast } from '@/hooks/use-toast';
import {
  BarChart3,
  Building2,
  FileText,
  Languages,
  Lock,
  Moon,
  Search,
  Settings as SettingsIcon,
  Shield,
  Sun,
  Upload,
  User as UserIcon,
  Users,
  Wrench,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  ADD_DOCUMENT_ALLOWED_ROLES,
  DEPARTMENTS_ALLOWED_ROLES,
  DOCUMENTS_ALLOWED_ROLES,
  INSTITUTION_SETTINGS_ALLOWED_ROLES,
  MAINTENANCE_ALLOWED_ROLES,
  REPORTS_ALLOWED_ROLES,
  USERS_ALLOWED_ROLES,
  getPrimaryBackendRole,
  getRolePresentation,
  hasAnyRole,
} from '@/lib/roles';
import { getMyScopeRequest } from '@/services/permissions.service';
import {
  changePasswordRequest,
  getTwoFactorStatusRequest,
  setTwoFactorStatusRequest,
  updateProfileRequest,
} from '@/services/users.service';

/* =======================
   Types
======================= */
type UiLanguage = 'en' | 'ar';
type UiTheme = 'light' | 'dark';

type TwoFactorStatusResponse = { enabled: boolean };

type UpdateProfilePayload = { name: string; email: string };
type ChangePasswordPayload = { currentPassword: string; newPassword: string };

type PermissionScopeLite = {
  role?: string | null;
  institutionId?: string | null;
  departmentId?: string | null;
  departmentName?: string | null;
};

type AuthUserShape = {
  id?: string;
  name?: string;
  email?: string;
  role?: string;
  department?: string | null;
  avatar?: string | null;
  twoFactorEnabled?: boolean;
  institutionId?: string | null;
  departmentId?: string | null;
  backendRole?: string | null;
};

/* =======================
   Helpers
======================= */
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null;
}
function pickString(obj: unknown, key: string): string | null {
  if (!isRecord(obj)) return null;
  const value = obj[key];
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length ? trimmed : null;
}
function normalize2FA(data: unknown): TwoFactorStatusResponse | null {
  if (!isRecord(data)) return null;
  const enabled = data.enabled;
  if (typeof enabled !== 'boolean') return null;
  return { enabled };
}
function applyTheme(theme: UiTheme) {
  const root = document.documentElement;
  if (theme === 'dark') root.classList.add('dark');
  else root.classList.remove('dark');
}
function applyLanguage(lang: UiLanguage) {
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.documentElement.lang = lang;
  document.documentElement.dir = dir;
  document.body.dir = dir;
}

/* =======================
   Component
======================= */
export default function Settings() {
  const { toast } = useToast();
  const { user, token, updateLocalUser } = useAuth();
  const { language, setLanguage, t } = useLanguage();

  const typedUser: AuthUserShape | null = (user as unknown as AuthUserShape) ?? null;
  const primaryRole = getPrimaryBackendRole(user);

  const [fullName, setFullName] = useState<string>(typedUser?.name ?? '');
  const [email, setEmail] = useState<string>(typedUser?.email ?? '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [twoFactorLoading, setTwoFactorLoading] = useState(false);
  const [theme, setTheme] = useState<UiTheme>('light');
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [scopeLoading, setScopeLoading] = useState(false);
  const [scope, setScope] = useState<PermissionScopeLite | null>(null);

  const display = useMemo(() => {
    return {
      name: typedUser?.name ?? '',
      email: typedUser?.email ?? '',
      role: typedUser?.role ?? '',
      department: typedUser?.department ?? null,
      avatar: typedUser?.avatar ?? null,
      twoFactorEnabledLocal: typedUser?.twoFactorEnabled ?? null,
    };
  }, [typedUser?.name, typedUser?.email, typedUser?.role, typedUser?.department, typedUser?.avatar, typedUser?.twoFactorEnabled]);

  useEffect(() => {
    setFullName(typedUser?.name ?? '');
    setEmail(typedUser?.email ?? '');
  }, [typedUser?.name, typedUser?.email]);

  useEffect(() => {
    const savedLang = localStorage.getItem('ui_language');
    const savedTheme = localStorage.getItem('ui_theme');

    if (savedLang === 'ar' || savedLang === 'en') {
      setLanguage(savedLang as UiLanguage);
      applyLanguage(savedLang as UiLanguage);
    } else {
      applyLanguage('en');
    }

    if (savedTheme === 'light' || savedTheme === 'dark') {
      setTheme(savedTheme as UiTheme);
      applyTheme(savedTheme as UiTheme);
    } else {
      applyTheme('light');
    }
  }, []);

  useEffect(() => {
    const load2FA = async () => {
      if (!token) return;
      setLoading(true);
      try {
        const res = await getTwoFactorStatusRequest();
        const parsed = normalize2FA(res);
        if (parsed) setTwoFactorEnabled(parsed.enabled);
      } catch (e) {
        console.error('Load 2FA failed', e);
      } finally {
        setLoading(false);
      }
    };
    void load2FA();
  }, [token]);

  useEffect(() => {
    const loadScope = async () => {
      if (!token) return;
      setScopeLoading(true);
      try {
        const res = await getMyScopeRequest();
        const nextScope: PermissionScopeLite = {
          role: pickString(res, 'role'),
          institutionId: pickString(res, 'institutionId'),
          departmentId: pickString(res, 'departmentId'),
          departmentName: pickString(res, 'departmentName') ?? pickString(res, 'department'),
        };
        setScope(nextScope);
      } catch (e) {
        console.error('Load permission scope failed', e);
        setScope(null);
      } finally {
        setScopeLoading(false);
      }
    };
    void loadScope();
  }, [token]);

  const handleSaveProfile = async () => {
    if (!token) {
      toast({ title: t("خطأ","Error"), description: t("يرجى تسجيل الدخول مجدداً.","Please login again.") });
      return;
    }
    if (!fullName.trim() || !email.trim()) {
      toast({ title: t("تنبيه","Warning"), description: t("الاسم والبريد مطلوبين.","Name and email are required.") });
      return;
    }
    setSavingProfile(true);
    try {
      const payload: UpdateProfilePayload = { name: fullName.trim(), email: email.trim() };
      await updateProfileRequest(payload);
      updateLocalUser({ name: payload.name, email: payload.email });
      toast({ title: t("تم الحفظ","Saved"), description: t("تم تحديث معلومات الملف الشخصي بنجاح.","Profile updated successfully.") });
    } catch (e) {
      console.error('Profile update failed', e);
      toast({ title: t("فشل الحفظ","Failed"), description: t("تعذر تحديث الملف الشخصي.","Could not update profile.") });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    if (!token) {
      toast({ title: t("خطأ","Error"), description: t("يرجى تسجيل الدخول مجدداً.","Please login again.") });
      return;
    }
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast({ title: t("تنبيه","Warning"), description: t("املأ جميع حقول كلمة المرور.","Fill all password fields.") });
      return;
    }
    if (newPassword !== confirmPassword) {
      toast({ title: t("تنبيه","Warning"), description: t("كلمة المرور الجديدة وتأكيدها غير متطابقين.","Passwords do not match.") });
      return;
    }
    setChangingPassword(true);
    try {
      const payload: ChangePasswordPayload = { currentPassword, newPassword };
      await changePasswordRequest(payload);
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
      toast({ title: t("تم التحديث","Updated"), description: t("تم تغيير كلمة المرور بنجاح.","Password changed successfully.") });
    } catch (e) {
      console.error('Change password failed', e);
      toast({ title: t("فشل التحديث","Failed"), description: t("تعذر تغيير كلمة المرور.","Could not change password.") });
    } finally {
      setChangingPassword(false);
    }
  };

  const handleToggleTwoFactor = async (next: boolean) => {
    if (!token) {
      toast({ title: t("خطأ","Error"), description: t("يرجى تسجيل الدخول مجدداً.","Please login again.") });
      return;
    }
    setTwoFactorLoading(true);
    try {
      await setTwoFactorStatusRequest({ enabled: next });
      setTwoFactorEnabled(next);
      updateLocalUser({ twoFactorEnabled: next });
      toast({ title: t("تم التحديث","Updated"), description: next ? t("تم تفعيل المصادقة الثنائية.","2FA enabled.") : t("تم إيقاف المصادقة الثنائية.","2FA disabled.") });
    } catch (e) {
      console.error('2FA toggle failed', e);
      toast({ title: t("فشل التحديث","Failed"), description: t("تعذر تحديث المصادقة الثنائية.","Could not update 2FA.") });
    } finally {
      setTwoFactorLoading(false);
    }
  };

    const handleChangeLanguage = (next: UiLanguage) => {
    setLanguage(next);
    localStorage.setItem('ui_language', next);
    applyLanguage(next);
    toast({
      title: t("تم التحديث","Updated"),
      description: next === 'ar' ? t("تم اختيار العربية.","Arabic selected.") : t("تم اختيار الإنجليزية.","English selected."),
    });
  };

  const handleToggleTheme = (nextDark: boolean) => {
    const nextTheme: UiTheme = nextDark ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('ui_theme', nextTheme);
    applyTheme(nextTheme);
    toast({
      title: t("تم التحديث","Updated"),
      description: nextTheme === 'dark' ? t("تم تفعيل الوضع الليلي.","Dark mode enabled.") : t("تم تفعيل الوضع النهاري.","Light mode enabled."),
    });
  };

  return (
    <div className="p-6 animate-fade-in" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
      <div className="mb-6">
        <h1 className="text-3xl font-cairo font-bold text-foreground mb-2">
          {t("الإعدادات","Settings")}
        </h1>
        <p className="text-muted-foreground">
          {t("إدارة إعدادات الحساب","Manage account settings")}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left */}
        <div className="lg:col-span-2 space-y-6">
          {/* Profile */}
          <Card className="hover-lift">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserIcon className="w-5 h-5 text-primary" />
                {t("الملف الشخصي","Profile")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <Avatar className="w-20 h-20">
                  <AvatarImage src={display.avatar ?? undefined} alt={display.name} />
                  <AvatarFallback className="bg-primary text-primary-foreground text-2xl">
                    {(display.name || '?').charAt(0)}
                  </AvatarFallback>
                </Avatar>
                <Button variant="outline" disabled>
                  {t("تغيير الصورة","Change photo")}
                </Button>
              </div>
              <Separator />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="name">{t("الاسم الكامل","Full name")}</Label>
                  <Input id="name" value={fullName} onChange={(e) => setFullName(e.target.value)} disabled={!token} />
                </div>
                <div>
                  <Label htmlFor="email">{t("البريد الإلكتروني","Email")}</Label>
                  <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={!token} dir="ltr" />
                </div>
              </div>
              {display.department && (
                <div>
                  <Label htmlFor="department">{t("القسم","Department")}</Label>
                  <Input id="department" value={display.department} disabled />
                </div>
              )}
              <Button onClick={handleSaveProfile} className="gradient-hero" disabled={savingProfile || !token}>
                {savingProfile ? t("جاري الحفظ...","Saving...") : t("حفظ التغييرات","Save changes")}
              </Button>
            </CardContent>
          </Card>

          {/* Password */}
          <Card className="hover-lift">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lock className="w-5 h-5 text-primary" />
                {t("تغيير كلمة المرور","Change password")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="current-password">{t("كلمة المرور الحالية","Current password")}</Label>
                <Input id="current-password" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} disabled={!token} />
              </div>
              <div>
                <Label htmlFor="new-password">{t("كلمة المرور الجديدة","New password")}</Label>
                <Input id="new-password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} disabled={!token} />
              </div>
              <div>
                <Label htmlFor="confirm-password">{t("تأكيد كلمة المرور","Confirm new password")}</Label>
                <Input id="confirm-password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} disabled={!token} />
              </div>
              <Button onClick={handleChangePassword} className="gradient-hero" disabled={changingPassword || !token}>
                {changingPassword ? t("جاري التحديث...","Updating...") : t("تحديث كلمة المرور","Update password")}
              </Button>
            </CardContent>
          </Card>

          {/* Language + Theme */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Language */}
            <Card className="hover-lift">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Languages className="w-5 h-5 text-primary" />
                  {t("اللغة","Language")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Label>{t("لغة الواجهة","UI language")}</Label>
                <Select value={language} onValueChange={(v) => handleChangeLanguage(v as UiLanguage)}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("اختر اللغة","Select language")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="ar">العربية</SelectItem>
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            {/* Theme */}
            <Card className="hover-lift">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {theme === 'dark' ? <Moon className="w-5 h-5 text-primary" /> : <Sun className="w-5 h-5 text-primary" />}
                  {t("المظهر","Theme")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="theme-toggle">{t("الوضع الليلي","Dark mode")}</Label>
                    <p className="text-xs text-muted-foreground mt-1">
                      {t("بدّل بين الوضع النهاري والليلي","Toggle dark/light mode")}
                    </p>
                  </div>
                  <div dir="ltr" className="flex items-center">
                    <Switch id="theme-toggle" checked={theme === 'dark'} onCheckedChange={(v) => handleToggleTheme(v)} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Right */}
        <div className="space-y-6">
              {/* Permissions & Scope */}
          <Card className="hover-lift">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-primary" />
                {t("الصلاحيات والنطاق", "Permissions & scope")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {!token ? (
                <p className="text-sm text-muted-foreground">
                  {t("سجّل الدخول لعرض نطاق الصلاحيات.", "Login to view your permission scope.")}
                </p>
              ) : scopeLoading ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Skeleton className="h-6 w-28 rounded-full" />
                    <Skeleton className="h-6 w-40 rounded-full" />
                    <Skeleton className="h-6 w-32 rounded-full" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {Array.from({ length: 8 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))}
                  </div>
                </div>
              ) : (
                (() => {
                  const scopeRoleRaw = scope?.role ?? typedUser?.backendRole ?? typedUser?.role ?? primaryRole ?? null;
                  const presentation = getRolePresentation(scopeRoleRaw);
                  const roleLabel = language === "ar" ? presentation.ar : presentation.en;

                  const scopeInstitutionId =
                    scope?.institutionId ?? typedUser?.institutionId ?? null;
                  const scopeDepartmentId =
                    scope?.departmentId ?? typedUser?.departmentId ?? null;
                  const scopeDepartmentName =
                    scope?.departmentName ?? typedUser?.department ?? null;

                  const modules = [
                    {
                      key: "documents",
                      icon: FileText,
                      titleAr: "إدارة الوثائق",
                      titleEn: "Documents",
                      allowed: hasAnyRole(user, DOCUMENTS_ALLOWED_ROLES),
                    },
                    {
                      key: "upload",
                      icon: Upload,
                      titleAr: "رفع وثيقة",
                      titleEn: "Upload document",
                      allowed: hasAnyRole(user, ADD_DOCUMENT_ALLOWED_ROLES),
                    },
                    {
                      key: "search",
                      icon: Search,
                      titleAr: "البحث",
                      titleEn: "Search",
                      allowed: true,
                    },
                    {
                      key: "reports",
                      icon: BarChart3,
                      titleAr: "التقارير",
                      titleEn: "Reports",
                      allowed: hasAnyRole(user, REPORTS_ALLOWED_ROLES),
                    },
                    {
                      key: "users",
                      icon: Users,
                      titleAr: "إدارة المستخدمين",
                      titleEn: "User management",
                      allowed: hasAnyRole(user, USERS_ALLOWED_ROLES),
                    },
                    {
                      key: "departments",
                      icon: Building2,
                      titleAr: "الأقسام",
                      titleEn: "Departments",
                      allowed: hasAnyRole(user, DEPARTMENTS_ALLOWED_ROLES),
                    },
                    {
                      key: "institution",
                      icon: SettingsIcon,
                      titleAr: "إعدادات المؤسسة",
                      titleEn: "Institution settings",
                      allowed: hasAnyRole(user, INSTITUTION_SETTINGS_ALLOWED_ROLES),
                    },
                    {
                      key: "maintenance",
                      icon: Wrench,
                      titleAr: "الصيانة والفهرسة",
                      titleEn: "Maintenance & indexing",
                      allowed: hasAnyRole(user, MAINTENANCE_ALLOWED_ROLES),
                    },
                  ];

                  return (
                    <>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline" className="bg-muted/30">
                          <span className="text-muted-foreground">{t("الدور:", "Role:")} </span>
                          <span className="font-semibold text-foreground">{roleLabel}</span>
                        </Badge>
                        <Badge variant="outline" className="bg-muted/30">
                          <span className="text-muted-foreground">{t("المؤسسة:", "Institution:")} </span>
                          <span className="font-semibold text-foreground">
                            {(scopeInstitutionId ?? "—").toString()}
                          </span>
                        </Badge>
                        <Badge variant="outline" className="bg-muted/30">
                          <span className="text-muted-foreground">{t("القسم:", "Department:")} </span>
                          <span className="font-semibold text-foreground">
                            {(scopeDepartmentName ?? scopeDepartmentId ?? "—").toString()}
                          </span>
                        </Badge>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {modules.map((m) => {
                          const allowed = m.allowed;
                          const Icon = m.icon;
                          return (
                            <div
                              key={m.key}
                              className={cn(
                                "flex items-center justify-between rounded-lg border px-3 py-2 transition-colors",
                                allowed
                                  ? "bg-background hover:bg-muted/30"
                                  : "bg-muted/30 text-muted-foreground"
                              )}
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                <div
                                  className={cn(
                                    "w-9 h-9 rounded-md flex items-center justify-center shrink-0",
                                    allowed ? "gradient-hero" : "bg-muted"
                                  )}
                                >
                                  <Icon className={cn("w-4 h-4", allowed ? "text-white" : "text-muted-foreground")} />
                                </div>
                                <span className={cn("text-sm font-medium truncate", allowed ? "text-foreground" : "text-muted-foreground")}>
                                  {t(m.titleAr, m.titleEn)}
                                </span>
                              </div>
                              <div className="shrink-0">
                                {allowed ? (
                                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                ) : (
                                  <XCircle className="w-4 h-4 text-muted-foreground/70" />
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  );
                })()
              )}
            </CardContent>
          </Card>

          {/* 2FA */}
          <Card className="hover-lift">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-primary" />
                {t("الأمان","Security")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="two-factor">{t("المصادقة الثنائية","Two-factor authentication")}</Label>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t("تفعيل/تعطيل المصادقة الثنائية لحسابك","Enable/disable 2FA for your account")}
                  </p>
                </div>
                <div dir="ltr" className="flex items-center">
                  <Switch id="two-factor" checked={twoFactorEnabled} onCheckedChange={(v) => void handleToggleTwoFactor(v)} disabled={twoFactorLoading || !token || loading} />
                </div>
              </div>
              {twoFactorLoading && (
                <p className="text-xs text-muted-foreground">{t("جاري تحديث المصادقة الثنائية...","Updating 2FA...")}</p>
              )}
            </CardContent>
          </Card>
        
        </div>
      </div>
    </div>
  );
}
