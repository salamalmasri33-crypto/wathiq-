import { useCallback, useEffect, useMemo, useState } from "react";
import { Search as SearchIcon, UserCog, UserPlus, ShieldPlus, Edit, Trash2, Building2, Users as UsersIcon } from "lucide-react";
import type { AxiosError } from "axios";

import type { Department } from "@/types/platform";
import type { AddUserDto, UpdateUserDto } from "@/types/dto";
import type { BackendRole } from "@/types/user";

import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/use-toast";
import {
  addUserRequest,
  assignRoleRequest,
  createAdminRequest,
  deleteUserRequest,
  editUserRequest,
  getUsersRequest,
} from "@/services/users.service";
import { getDepartmentsRequest } from "@/services/departments.service";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { createRoleBridge, getPrimaryBackendRole, getRolePresentation } from "@/lib/roles";

type ManagedUser = {
  id: string;
  name: string;
  email: string;
  role: BackendRole;
  backendRole: BackendRole;
  department?: string | null;
  departmentId?: string | null;
  institutionId?: string | null;
  avatar?: string | null;
};

type UserDialogMode = "add" | "edit" | null;

type UserFormState = {
  name: string;
  email: string;
  password: string;
  newPassword: string;
  role: BackendRole;
  institutionId: string;
  departmentId: string;
};

type CreateAdminFormState = {
  name: string;
  email: string;
  password: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeManagedUser(value: unknown): ManagedUser | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = typeof value.id === "string" ? value.id : "";
  const name = typeof value.name === "string" ? value.name : "";
  const email = typeof value.email === "string" ? value.email : "";
  const rawRole = typeof value.role === "string" ? value.role : "";
  const roleBridge = createRoleBridge(rawRole);
  const backendRole = getPrimaryBackendRole(roleBridge);

  if (!id || !name || !email || !backendRole) {
    return null;
  }

  return {
    id,
    name,
    email,
    role: backendRole,
    backendRole,
    department: typeof value.department === "string" ? value.department : null,
    departmentId: typeof value.departmentId === "string" ? value.departmentId : null,
    institutionId: typeof value.institutionId === "string" ? value.institutionId : null,
    avatar: typeof value.avatar === "string" ? value.avatar : null,
  };
}

function normalizeManagedUsers(data: unknown): ManagedUser[] {
  if (!Array.isArray(data)) {
    return [];
  }

  return data
    .map(normalizeManagedUser)
    .filter((item): item is ManagedUser => item !== null);
}

function getAllowedRoleOptions(currentRole: BackendRole | null): BackendRole[] {
  if (currentRole === "SystemAdmin") {
    return ["SystemAdmin", "InstitutionAdmin", "Manager", "Employee"];
  }

  return ["Manager", "Employee"];
}

function getRoleFilterOptions(currentRole: BackendRole | null): Array<BackendRole | "all"> {
  if (currentRole === "SystemAdmin") {
    return ["all", "SystemAdmin", "InstitutionAdmin", "Manager", "Employee"];
  }

  return ["all", "Manager", "Employee"];
}

function getAxiosMessage(error: unknown): string | null {
  const axiosError = error as AxiosError<unknown>;
  const data = axiosError?.response?.data;

  if (typeof data === "string") {
    return data;
  }

  if (isRecord(data) && typeof data.message === "string") {
    return data.message;
  }

  return null;
}

const EMPTY_USER_FORM: UserFormState = {
  name: "",
  email: "",
  password: "",
  newPassword: "",
  role: "Employee",
  institutionId: "",
  departmentId: "",
};

const EMPTY_ADMIN_FORM: CreateAdminFormState = {
  name: "",
  email: "",
  password: "",
};

export const Users = () => {
  const { token, user: authUser } = useAuth();
  const { t, language } = useLanguage();
  const { toast } = useToast();

  const currentBackendRole = getPrimaryBackendRole(authUser);
  const roleOptions = useMemo(() => getAllowedRoleOptions(currentBackendRole), [currentBackendRole]);
  const roleFilterOptions = useMemo(() => getRoleFilterOptions(currentBackendRole), [currentBackendRole]);
  const canCreateAdmin = currentBackendRole === "SystemAdmin";
  const isSystemAdmin = currentBackendRole === "SystemAdmin";
  const isRTL = language === "ar";

  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState<BackendRole | "all">("all");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [dialogMode, setDialogMode] = useState<UserDialogMode>(null);
  const [editingUser, setEditingUser] = useState<ManagedUser | null>(null);
  const [userForm, setUserForm] = useState<UserFormState>(EMPTY_USER_FORM);
  const [submittingUserForm, setSubmittingUserForm] = useState(false);

  const [isCreateAdminOpen, setIsCreateAdminOpen] = useState(false);
  const [createAdminForm, setCreateAdminForm] = useState<CreateAdminFormState>(EMPTY_ADMIN_FORM);
  const [submittingCreateAdmin, setSubmittingCreateAdmin] = useState(false);

  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);

  const resolvedInstitutionId = isSystemAdmin
    ? userForm.institutionId.trim()
    : (authUser?.institutionId ?? "").trim();

  const selectedDepartment = useMemo(
    () => departments.find((department) => department.id === userForm.departmentId) ?? null,
    [departments, userForm.departmentId],
  );

  const getRoleName = useCallback(
    (roleValue: BackendRole) => {
      const presentation = getRolePresentation(roleValue);
      return language === "ar" ? presentation.ar : presentation.en;
    },
    [language],
  );

  const fetchUsers = useCallback(async () => {
    if (!token) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const response = await getUsersRequest({
        role: roleFilter === "all" ? undefined : roleFilter,
        search: searchTerm.trim() || undefined,
      });

      setUsers(normalizeManagedUsers(response));
    } catch (error) {
      console.error("Failed to fetch users:", error);
      setUsers([]);
      setErrorMessage(
        getAxiosMessage(error) ??
          t("تعذر جلب المستخدمين حالياً. حاول مرة أخرى.", "Unable to load users right now. Please try again."),
      );
    } finally {
      setLoading(false);
    }
  }, [roleFilter, searchTerm, t, token]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void fetchUsers();
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [fetchUsers]);

  useEffect(() => {
    const shouldLoadDepartments =
      dialogMode !== null &&
      userForm.role !== "SystemAdmin" &&
      resolvedInstitutionId.length > 0;

    if (!shouldLoadDepartments) {
      setDepartments([]);
      return;
    }

    const loadDepartments = async () => {
      try {
        setDepartmentsLoading(true);
        const response = await getDepartmentsRequest(resolvedInstitutionId);
        setDepartments(response);
      } catch (error) {
        console.error("Failed to fetch departments:", error);
        setDepartments([]);
      } finally {
        setDepartmentsLoading(false);
      }
    };

    void loadDepartments();
  }, [dialogMode, resolvedInstitutionId, userForm.role]);

  useEffect(() => {
    if (userForm.role === "SystemAdmin") {
      if (userForm.institutionId || userForm.departmentId) {
        setUserForm((prev) => ({
          ...prev,
          institutionId: "",
          departmentId: "",
        }));
      }
      return;
    }

    if (!resolvedInstitutionId && userForm.departmentId) {
      setUserForm((prev) => ({
        ...prev,
        departmentId: "",
      }));
      return;
    }

    if (userForm.departmentId && !departments.some((department) => department.id === userForm.departmentId)) {
      setUserForm((prev) => ({
        ...prev,
        departmentId: "",
      }));
    }
  }, [departments, resolvedInstitutionId, userForm.departmentId, userForm.institutionId, userForm.role]);

  const resetUserForm = () => {
    setDialogMode(null);
    setEditingUser(null);
    setUserForm({
      ...EMPTY_USER_FORM,
      role: roleOptions.includes("Employee") ? "Employee" : roleOptions[0],
      institutionId: isSystemAdmin ? "" : authUser?.institutionId ?? "",
    });
  };

  const openAddDialog = () => {
    setEditingUser(null);
    setDialogMode("add");
    setUserForm({
      ...EMPTY_USER_FORM,
      role: roleOptions.includes("Employee") ? "Employee" : roleOptions[0],
      institutionId: isSystemAdmin ? "" : authUser?.institutionId ?? "",
    });
  };

  const openEditDialog = (managedUser: ManagedUser) => {
    setEditingUser(managedUser);
    setDialogMode("edit");
    setUserForm({
      name: managedUser.name,
      email: managedUser.email,
      password: "",
      newPassword: "",
      role: managedUser.role,
      institutionId: managedUser.institutionId ?? "",
      departmentId: managedUser.departmentId ?? "",
    });
  };

  const handleDeleteUser = async (managedUser: ManagedUser) => {
    const confirmed = window.confirm(
      t(
        `هل أنت متأكد من حذف المستخدم ${managedUser.name}؟`,
        `Are you sure you want to delete ${managedUser.name}?`,
      ),
    );

    if (!confirmed) {
      return;
    }

    try {
      await deleteUserRequest(managedUser.id);
      toast({
        title: t("تم حذف المستخدم", "User deleted"),
        description: t("تم حذف الحساب بنجاح.", "The account was deleted successfully."),
      });
      await fetchUsers();
    } catch (error) {
      console.error("Failed to delete user:", error);
      toast({
        variant: "destructive",
        title: t("فشل حذف المستخدم", "Failed to delete user"),
        description:
          getAxiosMessage(error) ??
          t("تعذر حذف الحساب حالياً.", "Unable to delete the account right now."),
      });
    }
  };

  const handleUserFormSubmit = async () => {
    const trimmedName = userForm.name.trim();
    const trimmedEmail = userForm.email.trim();
    const trimmedInstitutionId = resolvedInstitutionId;

    if (!trimmedName || !trimmedEmail) {
      toast({
        variant: "destructive",
        title: t("بيانات ناقصة", "Missing fields"),
        description: t("يرجى تعبئة الاسم والبريد الإلكتروني.", "Please fill in the name and email."),
      });
      return;
    }

    if (dialogMode === "add" && !userForm.password.trim()) {
      toast({
        variant: "destructive",
        title: t("كلمة المرور مطلوبة", "Password is required"),
        description: t("أدخل كلمة مرور للمستخدم الجديد.", "Enter a password for the new user."),
      });
      return;
    }

    if (isSystemAdmin && userForm.role !== "SystemAdmin" && !trimmedInstitutionId) {
      toast({
        variant: "destructive",
        title: t("المؤسسة مطلوبة", "Institution is required"),
        description: t("يرجى إدخال معرف المؤسسة قبل الحفظ.", "Please enter the institution id before saving."),
      });
      return;
    }

    const selectedDepartmentName = selectedDepartment?.name ?? null;

    try {
      setSubmittingUserForm(true);

      if (dialogMode === "add") {
        const payload: AddUserDto = {
          name: trimmedName,
          email: trimmedEmail,
          password: userForm.password,
          role: userForm.role,
          institutionId: userForm.role === "SystemAdmin" ? null : trimmedInstitutionId || null,
          departmentId: userForm.role === "SystemAdmin" ? null : userForm.departmentId || null,
          department: userForm.role === "SystemAdmin" ? null : selectedDepartmentName,
        };

        await addUserRequest(payload);

        toast({
          title: t("تمت إضافة المستخدم", "User created"),
          description: t("تم حفظ الحساب الجديد بنجاح.", "The new account was saved successfully."),
        });
      } else if (dialogMode === "edit" && editingUser) {
        const payload: UpdateUserDto = {
          name: trimmedName,
          email: trimmedEmail,
          newPassword: userForm.newPassword.trim() ? userForm.newPassword : null,
          institutionId:
            isSystemAdmin && userForm.role !== "SystemAdmin" ? trimmedInstitutionId || null : undefined,
          departmentId: userForm.role === "SystemAdmin" ? null : userForm.departmentId || null,
          department: userForm.role === "SystemAdmin" ? null : selectedDepartmentName,
        };

        await editUserRequest(editingUser.id, payload);

        if (editingUser.role !== userForm.role) {
          await assignRoleRequest(editingUser.id, userForm.role);
        }

        toast({
          title: t("تم تحديث المستخدم", "User updated"),
          description: t("تم حفظ التعديلات بنجاح.", "The changes were saved successfully."),
        });
      }

      resetUserForm();
      await fetchUsers();
    } catch (error) {
      console.error("Failed to submit user form:", error);
      toast({
        variant: "destructive",
        title:
          dialogMode === "add"
            ? t("فشل إضافة المستخدم", "Failed to add user")
            : t("فشل تعديل المستخدم", "Failed to update user"),
        description:
          getAxiosMessage(error) ??
          t("تعذر إكمال العملية حالياً.", "Unable to complete the action right now."),
      });
    } finally {
      setSubmittingUserForm(false);
    }
  };

  const handleCreateAdmin = async () => {
    const trimmedName = createAdminForm.name.trim();
    const trimmedEmail = createAdminForm.email.trim();

    if (!trimmedName || !trimmedEmail || !createAdminForm.password.trim()) {
      toast({
        variant: "destructive",
        title: t("بيانات ناقصة", "Missing fields"),
        description: t("يرجى تعبئة جميع حقول مدير النظام.", "Please fill all the system admin fields."),
      });
      return;
    }

    try {
      setSubmittingCreateAdmin(true);
      await createAdminRequest({
        name: trimmedName,
        email: trimmedEmail,
        password: createAdminForm.password,
      });

      setIsCreateAdminOpen(false);
      setCreateAdminForm(EMPTY_ADMIN_FORM);
      toast({
        title: t("تم إنشاء مدير النظام", "System admin created"),
        description: t("تمت إضافة حساب مدير النظام بنجاح.", "The system admin account was created successfully."),
      });
      await fetchUsers();
    } catch (error) {
      console.error("Failed to create system admin:", error);
      toast({
        variant: "destructive",
        title: t("فشل إنشاء مدير النظام", "Failed to create system admin"),
        description:
          getAxiosMessage(error) ??
          t("تعذر إنشاء الحساب حالياً.", "Unable to create the account right now."),
      });
    } finally {
      setSubmittingCreateAdmin(false);
    }
  };

  const dialogTitle = dialogMode === "edit" ? t("تعديل المستخدم", "Edit user") : t("إضافة مستخدم جديد", "Add new user");
  const dialogDescription =
    dialogMode === "edit"
      ? t("حدّث بيانات المستخدم ودوره وقسمه بما يتوافق مع الباك.", "Update the user data, role, and department.")
      : t("أضف مستخدماً جديداً وحدد دوره وقسمه حسب الصلاحيات المتاحة لك.", "Add a new user and choose role and department.");

  return (
    <div className="p-4 sm:p-6 animate-fade-in" style={{ direction: isRTL ? "rtl" : "ltr" }}>
      <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h1 className="mb-2 text-3xl font-cairo font-bold text-foreground">
            {t("إدارة المستخدمين", "User management")}
          </h1>
          <p className="text-muted-foreground">
            {t(
              "إدارة الحسابات والأدوار وربط المستخدمين بالمؤسسة والقسم.",
              "Manage accounts, roles, and institution/department assignments.",
            )}
          </p>
        </div>

        <div className={cn("flex flex-col gap-3 sm:flex-row", isRTL ? "xl:justify-start" : "xl:justify-end")}>
          {canCreateAdmin && (
            <Button variant="outline" onClick={() => setIsCreateAdminOpen(true)} className="border-primary/20 bg-primary/5 text-primary hover:bg-primary/10">
              <ShieldPlus className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
              {t("إنشاء مدير نظام", "Create system admin")}
            </Button>
          )}

          <Button className="gradient-hero" onClick={openAddDialog}>
            <UserPlus className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
            {t("إضافة مستخدم جديد", "Add new user")}
          </Button>
        </div>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_auto]">
        <Card className="hover-lift">
          <CardContent className="pt-6">
            <div className="relative">
              <SearchIcon className={cn("absolute top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground", isRTL ? "right-3" : "left-3")} />
              <Input
                placeholder={t("ابحث بالاسم أو البريد الإلكتروني", "Search by name or email")}
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                className={cn(isRTL ? "pr-10" : "pl-10")}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="hover-lift">
          <CardContent className="pt-6">
            <Select value={roleFilter} onValueChange={(value) => setRoleFilter(value as BackendRole | "all")}>
              <SelectTrigger>
                <SelectValue placeholder={t("فلترة حسب الدور", "Filter by role")} />
              </SelectTrigger>
              <SelectContent>
                {roleFilterOptions.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option === "all" ? t("كل الأدوار", "All roles") : getRoleName(option)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card className="hover-lift">
          <CardContent className="flex h-full items-center justify-center pt-6">
            <div className="text-center">
              <p className="text-sm text-muted-foreground">{t("عدد النتائج", "Results")}</p>
              <p className="text-2xl font-cairo font-bold text-foreground">{users.length}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {errorMessage && (
        <Card className="mb-6 border-destructive/20 bg-destructive/5">
          <CardContent className="p-4 text-sm text-destructive">{errorMessage}</CardContent>
        </Card>
      )}

      <Card className="hover-lift">
        <CardHeader>
          <CardTitle>{t("قائمة المستخدمين", "Users list")}</CardTitle>
          <CardDescription>
            {isSystemAdmin
              ? t("يعرض هذا الجدول المستخدمين ضمن النطاق الإداري الكامل المتاح لك.", "This table shows users within your full admin scope.")
              : t("يعرض هذا الجدول مستخدمي مؤسستك فقط.", "This table shows only users within your institution.")}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="overflow-x-auto">
            <Table className="min-w-[860px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="text-center">{t("المستخدم", "User")}</TableHead>
                  <TableHead className="text-center">{t("البريد الإلكتروني", "Email")}</TableHead>
                  <TableHead className="text-center">{t("الدور", "Role")}</TableHead>
                  {isSystemAdmin && <TableHead className="text-center">{t("المؤسسة", "Institution")}</TableHead>}
                  <TableHead className="text-center">{t("القسم", "Department")}</TableHead>
                  <TableHead className="text-center">{t("الإجراءات", "Actions")}</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={isSystemAdmin ? 6 : 5} className="py-10 text-center text-muted-foreground">
                      {t("جارٍ تحميل المستخدمين...", "Loading users...")}
                    </TableCell>
                  </TableRow>
                ) : users.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={isSystemAdmin ? 6 : 5} className="py-10 text-center text-muted-foreground">
                      {t("لا يوجد مستخدمون مطابقون للفلاتر الحالية.", "No users match the current filters.")}
                    </TableCell>
                  </TableRow>
                ) : (
                  users.map((managedUser) => (
                    <TableRow key={managedUser.id}>
                      <TableCell>
                        <div className="flex items-center justify-center gap-3">
                          <Avatar className="h-10 w-10">
                            <AvatarImage src={managedUser.avatar ?? undefined} alt={managedUser.name} />
                            <AvatarFallback className="bg-primary text-primary-foreground">
                              {managedUser.name.charAt(0)}
                            </AvatarFallback>
                          </Avatar>
                          <div className={cn("min-w-0", isRTL ? "text-right" : "text-left")}>
                            <p className="truncate font-medium">{managedUser.name}</p>
                            <p className="text-xs text-muted-foreground">{managedUser.id}</p>
                          </div>
                        </div>
                      </TableCell>

                      <TableCell className="text-center">{managedUser.email}</TableCell>

                      <TableCell className="text-center">
                        <Badge variant="outline" className="border-primary/20 bg-primary/5 text-primary">
                          {getRoleName(managedUser.role)}
                        </Badge>
                      </TableCell>

                      {isSystemAdmin && (
                        <TableCell className="text-center">
                          <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                            <Building2 className="h-4 w-4 text-primary" />
                            <span>{managedUser.institutionId || "—"}</span>
                          </div>
                        </TableCell>
                      )}

                      <TableCell className="text-center">{managedUser.department ?? "—"}</TableCell>

                      <TableCell>
                        <div className="flex items-center justify-center gap-2">
                          <Button variant="ghost" size="sm" onClick={() => openEditDialog(managedUser)}>
                            <Edit className="h-4 w-4" />
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => void handleDeleteUser(managedUser)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogMode !== null} onOpenChange={(open) => !open && resetUserForm()}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="font-cairo text-2xl">{dialogTitle}</DialogTitle>
            <DialogDescription>{dialogDescription}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-5">
            <div className="grid gap-2">
              <Label htmlFor="user-name">{t("الاسم الكامل", "Full name")}</Label>
              <Input id="user-name" value={userForm.name} onChange={(event) => setUserForm((prev) => ({ ...prev, name: event.target.value }))} placeholder={t("أدخل الاسم الكامل", "Enter the full name")} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="user-email">{t("البريد الإلكتروني", "Email")}</Label>
              <Input id="user-email" type="email" dir="ltr" value={userForm.email} onChange={(event) => setUserForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="name@example.com" />
            </div>

            <div className="grid gap-2">
              <Label>{t("الدور", "Role")}</Label>
              <Select value={userForm.role} onValueChange={(value) => setUserForm((prev) => ({ ...prev, role: value as BackendRole, institutionId: value === "SystemAdmin" ? "" : isSystemAdmin ? prev.institutionId : authUser?.institutionId ?? "", departmentId: value === "SystemAdmin" ? "" : prev.departmentId }))}>
                <SelectTrigger>
                  <SelectValue placeholder={t("اختر الدور", "Choose role")} />
                </SelectTrigger>
                <SelectContent>
                  {roleOptions.map((option) => (
                    <SelectItem key={option} value={option}>{getRoleName(option)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {isSystemAdmin && userForm.role !== "SystemAdmin" && (
              <div className="grid gap-2">
                <Label htmlFor="institution-id">{t("معرف المؤسسة", "Institution id")}</Label>
                <Input id="institution-id" dir="ltr" value={userForm.institutionId} onChange={(event) => setUserForm((prev) => ({ ...prev, institutionId: event.target.value, departmentId: "" }))} placeholder={t("أدخل معرف المؤسسة", "Enter the institution id")} />
              </div>
            )}

            {!isSystemAdmin && (
              <div className="rounded-xl border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
                <div className="mb-1 flex items-center gap-2 font-medium text-foreground">
                  <UsersIcon className="h-4 w-4 text-primary" />
                  {t("المؤسسة الحالية", "Current institution")}
                </div>
                <p dir="ltr">{authUser?.institutionId || "—"}</p>
              </div>
            )}

            {userForm.role !== "SystemAdmin" && (
              <div className="grid gap-2">
                <Label>{t("القسم", "Department")}</Label>
                <Select value={userForm.departmentId || "none"} onValueChange={(value) => setUserForm((prev) => ({ ...prev, departmentId: value === "none" ? "" : value }))} disabled={!resolvedInstitutionId || departmentsLoading}>
                  <SelectTrigger>
                    <SelectValue placeholder={!resolvedInstitutionId ? t("أدخل المؤسسة أولاً", "Enter the institution first") : departmentsLoading ? t("جارٍ تحميل الأقسام...", "Loading departments...") : t("اختر القسم", "Choose department")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">{t("بدون قسم", "No department")}</SelectItem>
                    {departments.map((department) => (
                      <SelectItem key={department.id} value={department.id}>{department.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {dialogMode === "add" ? (
              <div className="grid gap-2">
                <Label htmlFor="user-password">{t("كلمة المرور", "Password")}</Label>
                <Input id="user-password" type="password" dir="ltr" value={userForm.password} onChange={(event) => setUserForm((prev) => ({ ...prev, password: event.target.value }))} placeholder={t("أدخل كلمة المرور", "Enter the password")} />
              </div>
            ) : (
              <div className="grid gap-2">
                <Label htmlFor="user-new-password">{t("كلمة مرور جديدة", "New password")}</Label>
                <Input id="user-new-password" type="password" dir="ltr" value={userForm.newPassword} onChange={(event) => setUserForm((prev) => ({ ...prev, newPassword: event.target.value }))} placeholder={t("اتركه فارغاً إذا لم ترغب بالتغيير", "Leave empty if you don't want to change it")} />
              </div>
            )}
          </div>

          <DialogFooter className={cn("gap-3", isRTL ? "sm:justify-start" : "sm:justify-end")}>
            <Button variant="outline" onClick={resetUserForm}>{t("إلغاء", "Cancel")}</Button>
            <Button className="gradient-hero" onClick={() => void handleUserFormSubmit()} disabled={submittingUserForm}>
              <UserCog className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
              {submittingUserForm ? t("جارٍ الحفظ...", "Saving...") : dialogMode === "edit" ? t("حفظ التعديلات", "Save changes") : t("إضافة المستخدم", "Create user")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isCreateAdminOpen} onOpenChange={setIsCreateAdminOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-cairo text-2xl">{t("إنشاء مدير نظام", "Create system admin")}</DialogTitle>
            <DialogDescription>
              {t(
                "هذا الإجراء متاح فقط لمدير النظام وينشئ حساباً بدور SystemAdmin مباشرة.",
                "This action is only available for the system admin and creates a SystemAdmin account directly.",
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-5">
            <div className="grid gap-2">
              <Label htmlFor="admin-name">{t("الاسم الكامل", "Full name")}</Label>
              <Input id="admin-name" value={createAdminForm.name} onChange={(event) => setCreateAdminForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="admin-email">{t("البريد الإلكتروني", "Email")}</Label>
              <Input id="admin-email" type="email" dir="ltr" value={createAdminForm.email} onChange={(event) => setCreateAdminForm((prev) => ({ ...prev, email: event.target.value }))} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="admin-password">{t("كلمة المرور", "Password")}</Label>
              <Input id="admin-password" type="password" dir="ltr" value={createAdminForm.password} onChange={(event) => setCreateAdminForm((prev) => ({ ...prev, password: event.target.value }))} />
            </div>
          </div>

          <DialogFooter className={cn("gap-3", isRTL ? "sm:justify-start" : "sm:justify-end")}>
            <Button variant="outline" onClick={() => setIsCreateAdminOpen(false)}>{t("إلغاء", "Cancel")}</Button>
            <Button className="gradient-hero" onClick={() => void handleCreateAdmin()} disabled={submittingCreateAdmin}>
              <ShieldPlus className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
              {submittingCreateAdmin ? t("جارٍ الإنشاء...", "Creating...") : t("إنشاء الحساب", "Create account")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Users;
