import { useCallback, useEffect, useMemo, useState } from "react";
import type { AxiosError } from "axios";
import {
  Building2,
  ChevronDown,
  ChevronLeft,
  Edit3,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
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
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/use-toast";
import { getPrimaryBackendRole } from "@/lib/roles";
import { cn } from "@/lib/utils";
import {
  addDepartmentRequest,
  deleteDepartmentRequest,
  getDepartmentsRequest,
  getDepartmentTreeRequest,
  updateDepartmentRequest,
} from "@/services/departments.service";
import type { Department, DepartmentTreeNode } from "@/types/platform";

type DepartmentDialogMode = "create" | "edit" | null;

type DepartmentFormState = {
  name: string;
  institutionId: string;
  parentDepartmentId: string;
};

const NO_PARENT_VALUE = "__none__";

const EMPTY_FORM: DepartmentFormState = {
  name: "",
  institutionId: "",
  parentDepartmentId: NO_PARENT_VALUE,
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

export const Departments = () => {
  const { user, token } = useAuth();
  const { t, language } = useLanguage();
  const { toast } = useToast();

  const currentBackendRole = getPrimaryBackendRole(user);
  const isSystemAdmin = currentBackendRole === "SystemAdmin";
  const isRTL = language === "ar";

  const [tree, setTree] = useState<DepartmentTreeNode[]>([]);
  const [flatDepartments, setFlatDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [institutionInput, setInstitutionInput] = useState(user?.institutionId ?? "");
  const [institutionScope, setInstitutionScope] = useState(user?.institutionId ?? "");

  const [dialogMode, setDialogMode] = useState<DepartmentDialogMode>(null);
  const [editingDepartment, setEditingDepartment] = useState<Department | null>(null);
  const [formState, setFormState] = useState<DepartmentFormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [deletingDepartmentId, setDeletingDepartmentId] = useState<string | null>(null);

  useEffect(() => {
    if (!isSystemAdmin) {
      const userInstitutionId = user?.institutionId ?? "";
      setInstitutionInput(userInstitutionId);
      setInstitutionScope(userInstitutionId);
    }
  }, [isSystemAdmin, user?.institutionId]);

  const effectiveInstitutionId = (isSystemAdmin ? institutionScope : user?.institutionId ?? "").trim();

  const parentOptions = useMemo(
    () => flatDepartments.filter((department) => department.id !== editingDepartment?.id),
    [editingDepartment?.id, flatDepartments],
  );

  const summary = useMemo(() => {
    const topLevelDepartments = tree.filter((department) => !department.parentDepartmentId).length;
    return {
      total: flatDepartments.length,
      topLevel: topLevelDepartments,
      nested: Math.max(flatDepartments.length - topLevelDepartments, 0),
    };
  }, [flatDepartments, tree]);

  const loadDepartments = useCallback(async () => {
    if (!token) {
      return;
    }

    if (!effectiveInstitutionId) {
      setTree([]);
      setFlatDepartments([]);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const [flatResponse, treeResponse] = await Promise.all([
        getDepartmentsRequest(effectiveInstitutionId),
        getDepartmentTreeRequest(effectiveInstitutionId),
      ]);

      setFlatDepartments(flatResponse);
      setTree(treeResponse);
    } catch (error) {
      console.error("Failed to load departments:", error);
      setTree([]);
      setFlatDepartments([]);
      setErrorMessage(
        getAxiosMessage(error) ??
          t("تعذر جلب الأقسام حالياً. حاول مرة أخرى.", "Unable to load departments right now. Please try again."),
      );
    } finally {
      setLoading(false);
    }
  }, [effectiveInstitutionId, t, token]);

  useEffect(() => {
    void loadDepartments();
  }, [loadDepartments]);

  const openCreateDialog = () => {
    setEditingDepartment(null);
    setDialogMode("create");
    setFormState({
      name: "",
      institutionId: effectiveInstitutionId,
      parentDepartmentId: NO_PARENT_VALUE,
    });
  };

  const openEditDialog = (department: Department) => {
    setEditingDepartment(department);
    setDialogMode("edit");
    setFormState({
      name: department.name,
      institutionId: department.institutionId ?? effectiveInstitutionId,
      parentDepartmentId: department.parentDepartmentId ?? NO_PARENT_VALUE,
    });
  };

  const closeDialog = () => {
    setDialogMode(null);
    setEditingDepartment(null);
    setFormState(EMPTY_FORM);
  };

  const handleApplyInstitutionScope = () => {
    setInstitutionScope(institutionInput.trim());
  };

  const handleSubmit = async () => {
    const trimmedName = formState.name.trim();
    const targetInstitutionId = (isSystemAdmin ? formState.institutionId : effectiveInstitutionId).trim();
    const parentDepartmentId =
      formState.parentDepartmentId === NO_PARENT_VALUE ? null : formState.parentDepartmentId;

    if (!trimmedName) {
      toast({
        variant: "destructive",
        title: t("الاسم مطلوب", "Name is required"),
      });
      return;
    }

    if (!targetInstitutionId) {
      toast({
        variant: "destructive",
        title: t("معرف المؤسسة مطلوب", "Institution id is required"),
      });
      return;
    }

    setSubmitting(true);

    try {
      if (dialogMode === "edit" && editingDepartment) {
        await updateDepartmentRequest(editingDepartment.id, {
          name: trimmedName,
          parentDepartmentId,
        });
      } else {
        await addDepartmentRequest({
          name: trimmedName,
          institutionId: targetInstitutionId,
          parentDepartmentId,
        });
      }

      if (isSystemAdmin && targetInstitutionId !== institutionScope) {
        setInstitutionInput(targetInstitutionId);
        setInstitutionScope(targetInstitutionId);
      } else {
        void loadDepartments();
      }

      toast({
        title:
          dialogMode === "edit"
            ? t("تم تعديل القسم", "Department updated")
            : t("تمت إضافة القسم", "Department created"),
        description: t("تم حفظ التغييرات بنجاح.", "Changes were saved successfully."),
      });

      closeDialog();
    } catch (error) {
      toast({
        variant: "destructive",
        title:
          dialogMode === "edit"
            ? t("فشل تعديل القسم", "Failed to update department")
            : t("فشل إضافة القسم", "Failed to create department"),
        description:
          getAxiosMessage(error) ??
          t("تعذر حفظ القسم حالياً.", "Unable to save the department right now."),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (department: Department) => {
    const confirmed = window.confirm(
      t(
        `هل أنت متأكد من حذف القسم ${department.name}؟`,
        `Are you sure you want to delete ${department.name}?`,
      ),
    );

    if (!confirmed) {
      return;
    }

    setDeletingDepartmentId(department.id);

    try {
      await deleteDepartmentRequest(department.id);
      toast({
        title: t("تم حذف القسم", "Department deleted"),
        description: t("تم حذف القسم بنجاح.", "The department was deleted successfully."),
      });
      await loadDepartments();
    } catch (error) {
      toast({
        variant: "destructive",
        title: t("فشل حذف القسم", "Failed to delete department"),
        description:
          getAxiosMessage(error) ??
          t("تعذر حذف القسم حالياً.", "Unable to delete the department right now."),
      });
    } finally {
      setDeletingDepartmentId(null);
    }
  };

  return (
    <div className="animate-fade-in space-y-6 p-4 sm:p-6" style={{ direction: isRTL ? "rtl" : "ltr" }}>
      <Card className="animate-slide-up overflow-hidden border-primary/10 shadow-[var(--shadow-card)]">
        <div className="gradient-hero h-1.5 w-full" />
        <CardContent className="p-5 sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
                <Building2 className="h-3.5 w-3.5" />
                {t("الهيكل التنظيمي", "Organizational structure")}
              </div>
              <h1 className="font-cairo text-3xl font-bold text-foreground">
                {t("إدارة الأقسام", "Departments management")}
              </h1>
              <p className="mt-2 max-w-3xl text-muted-foreground">
                {t(
                  "أنشئ الأقسام ونظمها ضمن شجرة واضحة تسهّل توزيع الوثائق والصلاحيات داخل المؤسسة.",
                  "Create and organize departments in a clear hierarchy for document routing and permissions.",
                )}
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <div className="rounded-2xl border border-primary/10 bg-[linear-gradient(135deg,hsl(var(--primary)/0.06),white)] px-4 py-3 shadow-sm">
                <p className="text-xs text-muted-foreground">{t("إجمالي الأقسام", "Total departments")}</p>
                <p className="mt-1 text-2xl font-semibold text-foreground">{summary.total}</p>
              </div>
              <div className="rounded-2xl border border-primary/10 bg-[linear-gradient(135deg,hsl(var(--secondary)/0.18),white)] px-4 py-3 shadow-sm">
                <p className="text-xs text-muted-foreground">{t("أقسام رئيسية", "Top-level")}</p>
                <p className="mt-1 text-2xl font-semibold text-foreground">{summary.topLevel}</p>
              </div>
              <div className="rounded-2xl border border-primary/10 bg-[linear-gradient(135deg,hsl(var(--primary)/0.05),hsl(var(--secondary)/0.1))] px-4 py-3 shadow-sm">
                <p className="text-xs text-muted-foreground">{t("أقسام فرعية", "Nested")}</p>
                <p className="mt-1 text-2xl font-semibold text-foreground">{summary.nested}</p>
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            {isSystemAdmin ? (
              <div className="grid gap-2 md:min-w-[360px]">
                <Label htmlFor="department-scope">{t("معرف المؤسسة", "Institution id")}</Label>
                <div className="flex gap-2">
                  <Input
                    id="department-scope"
                    value={institutionInput}
                    onChange={(event) => setInstitutionInput(event.target.value)}
                    placeholder={t("أدخل معرف المؤسسة لعرض أقسامها", "Enter institution id")}
                    className="h-11"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 border-primary/20 bg-primary/5 text-primary hover:bg-primary/10"
                    onClick={handleApplyInstitutionScope}
                  >
                    {t("عرض", "Load")}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-primary/10 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
                {t("يتم عرض أقسام مؤسستك الحالية فقط.", "Showing departments for your current institution only.")}
              </div>
            )}

            <Button
              type="button"
              className="gradient-hero h-11 px-5 shadow-[var(--shadow-elegant)] transition-transform duration-300 hover:-translate-y-0.5"
              onClick={openCreateDialog}
            >
              <Plus className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
              {t("قسم جديد", "New department")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {!effectiveInstitutionId ? (
        <Card className="border-dashed border-primary/20 bg-primary/5">
          <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <Building2 className="h-10 w-10 text-primary/60" />
            <h2 className="font-cairo text-xl font-semibold text-foreground">
              {t("حدد المؤسسة أولاً", "Choose an institution first")}
            </h2>
            <p className="max-w-xl text-sm text-muted-foreground">
              {t(
                "حساب SystemAdmin يحتاج إلى معرف المؤسسة لعرض شجرة الأقسام وإدارتها.",
                "SystemAdmin accounts need an institution id before loading or managing departments.",
              )}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden border-primary/10 shadow-[var(--shadow-card)]">
          <div className="gradient-primary h-1.5 w-full" />
          <CardHeader>
            <CardTitle>{t("الهيكل التنظيمي", "Department tree")}</CardTitle>
            <CardDescription>
              {t(
                "استعرض البنية الحالية، ثم أضف أو عدّل الأقسام من نفس الصفحة.",
                "Browse the current hierarchy, then create or edit departments from the same page.",
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-16 animate-pulse rounded-2xl border border-border bg-muted/40"
                  />
                ))}
              </div>
            ) : errorMessage ? (
              <div className="rounded-2xl border border-destructive/15 bg-destructive/5 p-4 text-sm text-destructive">
                {errorMessage}
              </div>
            ) : tree.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-primary/20 bg-primary/5 p-8 text-center">
                <p className="font-medium text-foreground">
                  {t("لا توجد أقسام بعد.", "No departments yet.")}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {t(
                    "ابدأ بإضافة أول قسم لتكوين الهيكل التنظيمي.",
                    "Create the first department to start building the hierarchy.",
                  )}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {tree.map((department) => (
                  <DepartmentNode
                    key={department.id}
                    department={department}
                    depth={0}
                    deletingDepartmentId={deletingDepartmentId}
                    isRTL={isRTL}
                    language={language}
                    onDelete={handleDelete}
                    onEdit={openEditDialog}
                    t={t}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogMode !== null} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-cairo text-2xl">
              {dialogMode === "edit"
                ? t("تعديل قسم", "Edit department")
                : t("قسم جديد", "New department")}
            </DialogTitle>
            <DialogDescription>
              {dialogMode === "edit"
                ? t(
                    "عدّل اسم القسم أو القسم الأب، وسيتم حفظ التغيير مباشرة على الباك.",
                    "Update the department name or parent and save directly to the backend.",
                  )
                : t(
                    "أضف قسماً جديداً وربطه بالمؤسسة وبالقسم الأب عند الحاجة.",
                    "Create a new department and optionally attach it to a parent department.",
                  )}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="department-name">{t("اسم القسم", "Department name")}</Label>
              <Input
                id="department-name"
                value={formState.name}
                onChange={(event) => setFormState((current) => ({ ...current, name: event.target.value }))}
                placeholder={t("مثال: الشؤون القانونية", "Example: Legal Affairs")}
                className="h-11"
              />
            </div>

            {isSystemAdmin && dialogMode === "create" && (
              <div className="grid gap-2">
                <Label htmlFor="department-institution">{t("معرف المؤسسة", "Institution id")}</Label>
                <Input
                  id="department-institution"
                  value={formState.institutionId}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, institutionId: event.target.value }))
                  }
                  placeholder={t("أدخل معرف المؤسسة", "Enter institution id")}
                  className="h-11"
                />
              </div>
            )}

            <div className="grid gap-2">
              <Label>{t("القسم الأب", "Parent department")}</Label>
              <Select
                value={formState.parentDepartmentId}
                onValueChange={(value) =>
                  setFormState((current) => ({ ...current, parentDepartmentId: value }))
                }
              >
                <SelectTrigger className="h-11">
                  <SelectValue placeholder={t("بدون قسم أب", "No parent department")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_PARENT_VALUE}>{t("بدون قسم أب", "No parent department")}</SelectItem>
                  {parentOptions.map((department) => (
                    <SelectItem key={department.id} value={department.id}>
                      {department.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={closeDialog}>
              {t("إلغاء", "Cancel")}
            </Button>
            <Button
              type="button"
              className="gradient-hero shadow-[var(--shadow-elegant)]"
              onClick={() => void handleSubmit()}
              disabled={submitting}
            >
              {submitting ? (
                <Loader2 className={cn("h-4 w-4 animate-spin", isRTL ? "ml-2" : "mr-2")} />
              ) : (
                <Plus className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
              )}
              {dialogMode === "edit" ? t("حفظ التعديلات", "Save changes") : t("حفظ القسم", "Save department")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const DepartmentNode = ({
  department,
  depth,
  deletingDepartmentId,
  isRTL,
  language,
  onDelete,
  onEdit,
  t,
}: {
  department: DepartmentTreeNode;
  depth: number;
  deletingDepartmentId: string | null;
  isRTL: boolean;
  language: "ar" | "en";
  onDelete: (department: Department) => void;
  onEdit: (department: Department) => void;
  t: (ar: string, en: string) => string;
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const hasChildren = (department.children?.length ?? 0) > 0;
  const childCount = department.children?.length ?? 0;

  return (
    <div>
      <div
        className="group flex items-center gap-3 rounded-2xl border border-primary/10 bg-[linear-gradient(135deg,hsl(var(--background))_0%,hsl(var(--primary)/0.03)_100%)] px-3 py-3 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/20 hover:shadow-[var(--shadow-card)]"
        style={{ marginInlineStart: depth * 20 }}
      >
        <button
          type="button"
          className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-background hover:text-foreground"
          onClick={() => hasChildren && setIsOpen((current) => !current)}
        >
          {hasChildren ? (
            isOpen ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronLeft className={cn("h-4 w-4", language === "ar" ? "rotate-180" : "")} />
            )
          ) : (
            <span className="block h-4 w-4" />
          )}
        </button>

        <div className="grid h-10 w-10 place-items-center rounded-2xl bg-primary/10 text-primary">
          <Building2 className="h-5 w-5" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold text-foreground">{department.name}</p>
            {depth === 0 && (
              <Badge variant="outline" className="border-primary/15 bg-primary/5 text-primary">
                {t("رئيسي", "Root")}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {hasChildren
              ? t(`${childCount} أقسام فرعية`, `${childCount} child departments`)
              : t("بدون أقسام فرعية", "No child departments")}
          </p>
        </div>

        <div className="flex items-center gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-xl text-muted-foreground hover:bg-primary/10 hover:text-primary"
            onClick={() => onEdit(department)}
          >
            <Edit3 className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-xl text-destructive hover:bg-destructive/10"
            onClick={() => onDelete(department)}
            disabled={deletingDepartmentId === department.id}
          >
            {deletingDepartmentId === department.id ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {isOpen &&
        department.children?.map((child) => (
          <DepartmentNode
            key={child.id}
            department={child}
            depth={depth + 1}
            deletingDepartmentId={deletingDepartmentId}
            isRTL={isRTL}
            language={language}
            onDelete={onDelete}
            onEdit={onEdit}
            t={t}
          />
        ))}
    </div>
  );
};

export default Departments;
