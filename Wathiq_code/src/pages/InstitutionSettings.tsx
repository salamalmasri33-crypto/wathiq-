import { useCallback, useEffect, useMemo, useState } from "react";
import type { ComponentType } from "react";
import type { AxiosError } from "axios";
import { useSearchParams } from "react-router-dom";
import {
  Building2,
  Clock3,
  Languages,
  Loader2,
  Mail,
  Palette,
  RefreshCw,
  Save,
  ShieldCheck,
  Wrench,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ClassificationSettings } from "@/components/classification-settings/ClassificationSettings";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/use-toast";
import { getPrimaryBackendRole } from "@/lib/roles";
import { cn } from "@/lib/utils";
import { reindexAllDocumentsRequest } from "@/services/indexing.service";
import {
  getInstitutionSettingsRequest,
  updateInstitutionSettingsRequest,
} from "@/services/institution-settings.service";
import type { InstitutionSettings as InstitutionSettingsShape } from "@/types/platform";

type InstitutionSettingsForm = {
  institutionId: string;
  institutionName: string;
  description: string;
  contactEmail: string;
  timeZone: string;
  defaultLanguage: string;
  brandingPrimaryColor: string;
};

const TIMEZONE_OPTIONS = [
  "Asia/Damascus",
  "Europe/Moscow",
  "Asia/Riyadh",
  "Asia/Dubai",
  "Africa/Cairo",
  "UTC",
];

const LANGUAGE_OPTIONS = [
  { value: "ar", labelAr: "العربية", labelEn: "Arabic" },
  { value: "en", labelAr: "الإنجليزية", labelEn: "English" },
];

const DEFAULT_FORM: InstitutionSettingsForm = {
  institutionId: "",
  institutionName: "",
  description: "",
  contactEmail: "",
  timeZone: "Asia/Damascus",
  defaultLanguage: "ar",
  brandingPrimaryColor: "#1f4a8a",
};

function getAxiosMessage(error: unknown): string | null {
  const axiosError = error as AxiosError<unknown>;
  const data = axiosError?.response?.data;

  if (typeof data === "string") {
    return data;
  }

  if (typeof data === "object" && data !== null && "message" in data) {
    const message = (data as { message?: unknown }).message;
    return typeof message === "string" ? message : null;
  }

  return null;
}

function normalizeHexColor(value: string | null | undefined): string {
  if (!value) {
    return DEFAULT_FORM.brandingPrimaryColor;
  }

  const trimmed = value.trim();
  return /^#([0-9a-fA-F]{6})$/.test(trimmed) ? trimmed : DEFAULT_FORM.brandingPrimaryColor;
}

function mapSettingsToForm(settings: InstitutionSettingsShape | null | undefined): InstitutionSettingsForm {
  return {
    institutionId: settings?.institutionId ?? "",
    institutionName: settings?.institutionName ?? "",
    description: settings?.description ?? "",
    contactEmail: settings?.contactEmail ?? "",
    timeZone: settings?.timeZone ?? DEFAULT_FORM.timeZone,
    defaultLanguage: settings?.defaultLanguage ?? DEFAULT_FORM.defaultLanguage,
    brandingPrimaryColor: normalizeHexColor(settings?.brandingPrimaryColor),
  };
}

export const InstitutionSettings = () => {
  const { user, token } = useAuth();
  const { language, t } = useLanguage();
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const currentBackendRole = getPrimaryBackendRole(user);
  const isSystemAdmin = currentBackendRole === "SystemAdmin";
  const isRTL = language === "ar";

  const [institutionInput, setInstitutionInput] = useState(user?.institutionId ?? "");
  const [institutionScope, setInstitutionScope] = useState(user?.institutionId ?? "");

  const [settings, setSettings] = useState<InstitutionSettingsShape | null>(null);
  const [form, setForm] = useState<InstitutionSettingsForm>(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [recreateIndex, setRecreateIndex] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [isReindexDialogOpen, setIsReindexDialogOpen] = useState(false);

  useEffect(() => {
    if (!isSystemAdmin) {
      const userInstitutionId = user?.institutionId ?? "";
      setInstitutionInput(userInstitutionId);
      setInstitutionScope(userInstitutionId);
    }
  }, [isSystemAdmin, user?.institutionId]);

  const effectiveInstitutionId = (isSystemAdmin ? institutionScope : user?.institutionId ?? "").trim();

  const canLoadScope = !isSystemAdmin || institutionInput.trim().length > 0;

  const loadSettings = useCallback(async () => {
    if (!token) {
      return;
    }

    if (!effectiveInstitutionId) {
      setSettings(null);
      setForm(DEFAULT_FORM);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const response = await getInstitutionSettingsRequest(isSystemAdmin ? effectiveInstitutionId : undefined);
      setSettings(response);
      setForm(mapSettingsToForm(response));
    } catch (error) {
      console.error("Failed to load institution settings:", error);
      setSettings(null);
      setForm({
        ...DEFAULT_FORM,
        institutionId: effectiveInstitutionId,
      });
      setErrorMessage(
        getAxiosMessage(error) ??
          t(
            "تعذر جلب إعدادات المؤسسة حالياً. حاول مرة أخرى.",
            "Unable to load institution settings right now. Please try again.",
          ),
      );
    } finally {
      setLoading(false);
    }
  }, [effectiveInstitutionId, isSystemAdmin, t, token]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (settings) {
      setForm(mapSettingsToForm(settings));
      return;
    }

    setForm((current) => ({
      ...current,
      institutionId: effectiveInstitutionId,
    }));
  }, [effectiveInstitutionId, settings]);

  const lastUpdated = useMemo(() => {
    if (!settings?.updatedAt) {
      return "-";
    }

    const date = new Date(settings.updatedAt);
    if (Number.isNaN(date.getTime())) {
      return "-";
    }

    return date.toLocaleDateString(language === "ar" ? "ar-SA" : "en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }, [language, settings?.updatedAt]);

  const roleSummary = useMemo(() => {
    if (currentBackendRole === "SystemAdmin") {
      return t("مدير النظام", "System admin");
    }

    return t("مدير المؤسسة", "Institution admin");
  }, [currentBackendRole, t]);

  const handleApplyScope = () => {
    setInstitutionScope(institutionInput.trim());
  };

  const handleSave = async () => {
    const scopedInstitutionId = (isSystemAdmin ? form.institutionId : effectiveInstitutionId).trim();

    if (!scopedInstitutionId) {
      toast({
        variant: "destructive",
        title: t("معرف المؤسسة مطلوب", "Institution id is required"),
      });
      return;
    }

    setSaving(true);

    try {
      await updateInstitutionSettingsRequest({
        institutionId: scopedInstitutionId,
        institutionName: form.institutionName.trim() || null,
        description: form.description.trim() || null,
        contactEmail: form.contactEmail.trim() || null,
        timeZone: form.timeZone,
        defaultLanguage: form.defaultLanguage,
        brandingPrimaryColor: normalizeHexColor(form.brandingPrimaryColor),
      });

      if (isSystemAdmin && scopedInstitutionId !== institutionScope) {
        setInstitutionInput(scopedInstitutionId);
        setInstitutionScope(scopedInstitutionId);
      } else {
        await loadSettings();
      }

      toast({
        title: t("تم حفظ الإعدادات", "Settings saved"),
        description: t("تم تحديث إعدادات المؤسسة بنجاح.", "Institution settings were updated successfully."),
      });
    } catch (error) {
      toast({
        variant: "destructive",
        title: t("فشل حفظ الإعدادات", "Failed to save settings"),
        description:
          getAxiosMessage(error) ??
          t("تعذر حفظ الإعدادات حالياً.", "Unable to save the settings right now."),
      });
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmReindex = async () => {
    setReindexing(true);

    try {
      await reindexAllDocumentsRequest(recreateIndex);
      toast({
        title: t("تم تنفيذ الفهرسة", "Reindexing started"),
        description: recreateIndex
          ? t(
              "تم إرسال طلب إعادة إنشاء الفهرس ثم إعادة الفهرسة بنجاح.",
              "The request to recreate the index and reindex documents was sent successfully.",
            )
          : t(
              "تم إرسال طلب إعادة فهرسة الوثائق بنجاح.",
              "The request to reindex all documents was sent successfully.",
            ),
      });
      setIsReindexDialogOpen(false);
    } catch (error) {
      toast({
        variant: "destructive",
        title: t("فشلت عملية الفهرسة", "Reindexing failed"),
        description:
          getAxiosMessage(error) ??
          t("تعذر تنفيذ إعادة الفهرسة حالياً.", "Unable to run reindexing right now."),
      });
    } finally {
      setReindexing(false);
    }
  };

  return (
    <div className="animate-fade-in space-y-6 p-4 sm:p-6" style={{ direction: isRTL ? "rtl" : "ltr" }}>
      <div className="flex flex-col gap-2">
        <h1 className="font-cairo text-3xl font-bold text-foreground">
          {t("إعدادات المؤسسة", "Institution settings")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("إدارة بيانات المؤسسة والهوية البصرية.", "Manage institution profile and visual identity.")}
        </p>
      </div>

      <Tabs
        value={searchParams.get("tab") === "classification" ? "classification" : "general"}
        onValueChange={(value) => {
          const next = new URLSearchParams(searchParams);
          if (value === "classification") next.set("tab", "classification");
          else next.delete("tab");
          setSearchParams(next, { replace: true });
        }}
        className="space-y-5"
      >
        <TabsList className="h-auto w-full justify-start overflow-x-auto rounded-2xl border border-primary/10 bg-card p-1.5 shadow-[var(--shadow-card)] sm:w-fit">
          <TabsTrigger value="general" className="rounded-xl px-5 py-2.5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
            {t("إعدادات المؤسسة", "Institution settings")}
          </TabsTrigger>
          <TabsTrigger value="classification" className="rounded-xl px-5 py-2.5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-[inset_0_-3px_0_hsl(var(--secondary))]">
            {t("تصنيف الوثائق", "Document classification")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="mt-0 space-y-6">

      {!effectiveInstitutionId ? (
        <Card className="border-dashed border-primary/20 bg-primary/5 shadow-[var(--shadow-card)]">
          <CardContent className="p-6 sm:p-10">
            <div className="mx-auto flex max-w-2xl flex-col items-center gap-5 text-center">
              <div className="grid h-16 w-16 place-items-center rounded-3xl bg-primary/10 text-primary shadow-sm">
                <Building2 className="h-8 w-8" />
              </div>

              <div className="space-y-2">
                <h2 className="font-cairo text-xl font-semibold text-foreground">
                  {t("حدد المؤسسة أولاً", "Choose an institution first")}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {isSystemAdmin
                    ? t(
                        "أدخل معرف المؤسسة ثم اضغط عرض حتى نحمّل الإعدادات ونربطها مع الباك بشكل صحيح.",
                        "Enter the institution id, then click load so we can fetch the settings and connect them to the backend correctly.",
                      )
                    : t(
                        "هذا الحساب غير مرتبط بمؤسسة حالياً، لذلك لا يمكن عرض الإعدادات.",
                        "This account is not assigned to an institution yet, so the settings cannot be displayed.",
                      )}
                </p>
              </div>

              {isSystemAdmin ? (
                <div className="w-full rounded-[1.75rem] border border-primary/15 bg-background/80 p-4 shadow-sm">
                  <div className="grid gap-2 text-start">
                    <Label htmlFor="institution-scope-empty">
                      {t("معرف المؤسسة", "Institution id")}
                    </Label>
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <Input
                        id="institution-scope-empty"
                        value={institutionInput}
                        onChange={(event) => setInstitutionInput(event.target.value)}
                        placeholder={t("مثال: inst-main", "Example: inst-main")}
                        className="h-11"
                      />
                      <Button
                        type="button"
                        className="gradient-hero h-11 shadow-[var(--shadow-elegant)]"
                        onClick={handleApplyScope}
                        disabled={!canLoadScope}
                      >
                        {t("عرض الإعدادات", "Load settings")}
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid items-stretch gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
            <Card className="flex h-full flex-col overflow-hidden border-primary/10 shadow-[var(--shadow-card)]">
              <div className="gradient-primary h-1.5 w-full" />
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Building2 className="h-5 w-5 text-primary" />
                      {t("بيانات المؤسسة", "Institution profile")}
                    </CardTitle>
                    <CardDescription>
                      {t("البيانات الأساسية للمؤسسة.", "Primary institution details.")}
                    </CardDescription>
                  </div>
                  <Button
                    type="button"
                    className="gradient-hero shadow-[var(--shadow-elegant)]"
                    onClick={() => void handleSave()}
                    disabled={loading || saving || !effectiveInstitutionId}
                  >
                    {saving ? (
                      <Loader2 className={cn("h-4 w-4 animate-spin", isRTL ? "ml-2" : "mr-2")} />
                    ) : (
                      <Save className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                    )}
                    {t("حفظ التعديلات", "Save changes")}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-5">
                {isSystemAdmin && (
                  <div className="grid gap-2 rounded-2xl border border-primary/10 bg-primary/5 p-4">
                    <Label htmlFor="institution-scope">{t("معرف المؤسسة", "Institution id")}</Label>
                    <div className="flex gap-2">
                      <Input
                        id="institution-scope"
                        value={institutionInput}
                        onChange={(event) => setInstitutionInput(event.target.value)}
                        placeholder={t("أدخل معرف المؤسسة", "Enter institution id")}
                        className="h-11"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        className="h-11 border-primary/20 bg-background text-primary hover:bg-primary/10"
                        onClick={handleApplyScope}
                        disabled={!canLoadScope}
                      >
                        {t("عرض", "Load")}
                      </Button>
                    </div>
                  </div>
                )}

                <div className="grid gap-5 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="institution-name">{t("اسم المؤسسة", "Institution name")}</Label>
                    <Input
                      id="institution-name"
                      value={form.institutionName}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, institutionName: event.target.value }))
                      }
                      placeholder={t("مثال: مؤسسة وثّق", "Example: Wathiq Institution")}
                      className="h-11"
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="contact-email">{t("البريد الرسمي", "Contact email")}</Label>
                    <Input
                      id="contact-email"
                      type="email"
                      value={form.contactEmail}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, contactEmail: event.target.value }))
                      }
                      placeholder="contact@institution.com"
                      className="h-11"
                    />
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="institution-description">{t("وصف المؤسسة", "Description")}</Label>
                  <Textarea
                    id="institution-description"
                    rows={5}
                    value={form.description}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, description: event.target.value }))
                    }
                    placeholder={t("نبذة مختصرة عن المؤسسة.", "Short institution summary.")}
                    className="resize-none"
                  />
                </div>

                <div className="grid gap-5 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>{t("المنطقة الزمنية", "Time zone")}</Label>
                    <Select
                      value={form.timeZone}
                      onValueChange={(value) => setForm((current) => ({ ...current, timeZone: value }))}
                    >
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder={t("اختر المنطقة الزمنية", "Select time zone")} />
                      </SelectTrigger>
                      <SelectContent>
                        {TIMEZONE_OPTIONS.map((timeZone) => (
                          <SelectItem key={timeZone} value={timeZone}>
                            {timeZone}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-2">
                    <Label>{t("اللغة الافتراضية", "Default language")}</Label>
                    <Select
                      value={form.defaultLanguage}
                      onValueChange={(value) =>
                        setForm((current) => ({ ...current, defaultLanguage: value }))
                      }
                    >
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder={t("اختر اللغة", "Select language")} />
                      </SelectTrigger>
                      <SelectContent>
                        {LANGUAGE_OPTIONS.map((item) => (
                          <SelectItem key={item.value} value={item.value}>
                            {language === "ar" ? item.labelAr : item.labelEn}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="flex h-full flex-col overflow-hidden border-primary/10 shadow-[var(--shadow-card)]">
              <div className="gradient-primary h-1.5 w-full" />
              <CardHeader>
                <CardTitle>{t("ملخص سريع", "Quick summary")}</CardTitle>
                <CardDescription>
                  {t("معلومات مرجعية سريعة.", "Quick reference information.")}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col space-y-4">
                <SummaryRow
                  icon={Building2}
                  label={t("معرف المؤسسة", "Institution id")}
                  value={form.institutionId || effectiveInstitutionId || "-"}
                />
                <SummaryRow
                  icon={Mail}
                  label={t("البريد الرسمي", "Contact email")}
                  value={form.contactEmail || "-"}
                />
                <SummaryRow
                  icon={Clock3}
                  label={t("آخر تحديث", "Last updated")}
                  value={lastUpdated}
                />
                <SummaryRow
                  icon={Languages}
                  label={t("اللغة الافتراضية", "Default language")}
                  value={
                    form.defaultLanguage === "ar"
                      ? t("العربية", "Arabic")
                      : form.defaultLanguage === "en"
                        ? t("الإنجليزية", "English")
                        : form.defaultLanguage
                  }
                />
                <SummaryRow icon={ShieldCheck} label={t("الصلاحية", "Role")} value={roleSummary} />
                <div className="mt-auto rounded-2xl border border-primary/10 bg-primary/5 p-4">
                  <p className="mb-2 text-xs text-muted-foreground">{t("اللون المعتمد", "Approved color")}</p>
                  <div
                    className="h-12 rounded-xl shadow-inner"
                    style={{ backgroundColor: normalizeHexColor(form.brandingPrimaryColor) }}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          <div className={cn("grid items-stretch gap-6", isSystemAdmin ? "xl:grid-cols-[minmax(0,1fr)_340px]" : "xl:grid-cols-1")}>
            <Card className="flex h-full flex-col overflow-hidden border-primary/10 shadow-[var(--shadow-card)]">
              <div className="gradient-primary h-1.5 w-full" />
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Palette className="h-5 w-5 text-primary" />
                      {t("الهوية البصرية", "Visual identity")}
                    </CardTitle>
                    <CardDescription>
                      {t("اللون الرئيسي للمؤسسة.", "Institution primary color.")}
                    </CardDescription>
                  </div>
                  <Button
                    type="button"
                    className="gradient-hero shadow-[var(--shadow-elegant)]"
                    onClick={() => void handleSave()}
                    disabled={loading || saving || !effectiveInstitutionId}
                  >
                    {saving ? (
                      <Loader2 className={cn("h-4 w-4 animate-spin", isRTL ? "ml-2" : "mr-2")} />
                    ) : (
                      <Save className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                    )}
                    {t("حفظ التعديلات", "Save changes")}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="grid flex-1 gap-5 md:grid-cols-[minmax(0,1fr)_200px]">
                <div className="grid gap-2">
                  <Label htmlFor="branding-color">{t("اللون الرئيسي", "Primary color")}</Label>
                  <div className="flex gap-3">
                    <input
                      id="branding-color"
                      type="color"
                      value={normalizeHexColor(form.brandingPrimaryColor)}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          brandingPrimaryColor: event.target.value,
                        }))
                      }
                      className="h-11 w-16 cursor-pointer rounded-xl border border-primary/10 bg-background p-1"
                    />
                    <Input
                      value={form.brandingPrimaryColor}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          brandingPrimaryColor: event.target.value,
                        }))
                      }
                      placeholder="#1f4a8a"
                      className="h-11"
                    />
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-primary/10 bg-[linear-gradient(135deg,hsl(var(--background))_0%,hsl(var(--primary)/0.03)_100%)] p-4 shadow-sm">
                  <p className="text-xs text-muted-foreground">{t("معاينة اللون", "Color preview")}</p>
                  <div
                    className="mt-3 h-20 rounded-2xl shadow-inner"
                    style={{
                      background: `linear-gradient(135deg, ${normalizeHexColor(form.brandingPrimaryColor)}, rgba(255,255,255,0.92))`,
                    }}
                  />
                  <p className="mt-3 text-sm font-medium text-foreground">
                    {normalizeHexColor(form.brandingPrimaryColor)}
                  </p>
                </div>
              </CardContent>
            </Card>

            {isSystemAdmin && (
              <Card className="flex h-full flex-col overflow-hidden border-primary/10 shadow-[var(--shadow-card)]">
                <div className="gradient-primary h-1.5 w-full" />
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Wrench className="h-5 w-5 text-primary" />
                    {t("الفهرسة والصيانة", "Indexing and maintenance")}
                  </CardTitle>
                  <CardDescription>
                    {t("أدوات صيانة خاصة بمدير النظام.", "System admin maintenance tools.")}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col space-y-5">
                  <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-800">
                    {t("يفضل تنفيذها في وقت هادئ.", "Best run during low-traffic hours.")}
                  </div>

                  <div className="flex items-start justify-between gap-4 rounded-2xl border border-primary/10 bg-[linear-gradient(135deg,hsl(var(--background))_0%,hsl(var(--primary)/0.03)_100%)] p-4">
                    <div>
                      <p className="font-medium text-foreground">
                        {t("إعادة إنشاء الفهرس", "Recreate index")}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {t("يعيد بناء الفهرس قبل إعادة الفهرسة.", "Rebuilds the index before reindexing.")}
                      </p>
                    </div>
                    <Switch checked={recreateIndex} onCheckedChange={setRecreateIndex} />
                  </div>

                  <div className="mt-auto">
                    <Button
                      type="button"
                      className="gradient-hero h-11 w-full shadow-[var(--shadow-elegant)] transition-transform duration-300 hover:-translate-y-0.5"
                      onClick={() => setIsReindexDialogOpen(true)}
                      disabled={reindexing}
                    >
                      {reindexing ? (
                        <Loader2 className={cn("h-4 w-4 animate-spin", isRTL ? "ml-2" : "mr-2")} />
                      ) : (
                        <RefreshCw className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                      )}
                      {t("إعادة فهرسة الوثائق", "Reindex documents")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
        </TabsContent>

        <TabsContent value="classification" className="mt-0">
          {effectiveInstitutionId ? (
            <ClassificationSettings key={effectiveInstitutionId} institutionId={effectiveInstitutionId} />
          ) : (
            <Card className="border-dashed border-primary/20 bg-primary/5">
              <CardContent className="p-10 text-center text-muted-foreground">
                {t("حدد المؤسسة أولًا لعرض تصنيفاتها.", "Choose an institution first to view its classifications.")}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={isReindexDialogOpen} onOpenChange={setIsReindexDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-cairo text-2xl">
              {t("تأكيد إعادة الفهرسة", "Confirm reindexing")}
            </DialogTitle>
            <DialogDescription>
              {recreateIndex
                ? t(
                    "سيتم إعادة إنشاء الفهرس ثم إعادة فهرسة جميع الوثائق. قد تستغرق العملية بعض الوقت.",
                    "The index will be recreated and all documents will be reindexed. This may take some time.",
                  )
                : t(
                    "سيتم إعادة فهرسة جميع الوثائق باستخدام الفهرس الحالي.",
                    "All documents will be reindexed using the current index.",
                  )}
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-2xl border border-primary/10 bg-primary/5 p-4 text-sm text-muted-foreground">
            {t(
              "تأكد من أن هذه العملية مناسبة للوضع الحالي، لأنها تؤثر على فهرسة النظام بالكامل.",
              "Make sure this action is appropriate for the current situation because it affects the whole indexing system.",
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={() => setIsReindexDialogOpen(false)}>
              {t("إلغاء", "Cancel")}
            </Button>
            <Button
              type="button"
              className="gradient-hero shadow-[var(--shadow-elegant)]"
              onClick={() => void handleConfirmReindex()}
              disabled={reindexing}
            >
              {reindexing ? (
                <Loader2 className={cn("h-4 w-4 animate-spin", isRTL ? "ml-2" : "mr-2")} />
              ) : (
                <Wrench className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
              )}
              {t("تنفيذ العملية", "Run action")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const SummaryRow = ({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) => (
  <div className="flex items-start gap-3 rounded-2xl border border-primary/10 bg-[linear-gradient(135deg,hsl(var(--background))_0%,hsl(var(--primary)/0.03)_100%)] p-3">
    <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
      <Icon className="h-5 w-5" />
    </div>
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-medium text-foreground">{value}</p>
    </div>
  </div>
);

export default InstitutionSettings;
