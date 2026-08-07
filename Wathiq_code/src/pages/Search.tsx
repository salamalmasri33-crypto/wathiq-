import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

import { useToast } from "@/hooks/use-toast";

import {
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileText,
  Calendar,
  FileType,
  HardDrive,
  Search as SearchIcon,
  ShieldAlert,
  SortDesc,
  SortAsc,
  User,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { downloadDocumentRequest, searchDocumentsRequest } from "@/services/documents.service";
import { getDepartmentsRequest } from "@/services/departments.service";
import { getUsersRequest } from "@/services/users.service";
import { GenreSelectors } from "@/components/GenreSelectors";
import { useInstitutionTaxonomy } from "@/hooks/use-institution-taxonomy";
import type { Document, DocumentPriority, DocumentStatus } from "@/types/document";
import type { SearchDocumentsDto } from "@/types/dto";
import type { Department } from "@/types/platform";

/* =======================
   Types (no any)
======================= */

type UiLanguage = "en" | "ar";
type SearchSortBy = "CreatedAt" | "Title" | "Size";

type SearchDocument = Document & {
  fileName?: string | null;
  contentType?: string | null;
  fileSize?: number | null;
  size?: number | null;
  ownerId?: string | null;
  ownerName?: string | null;
  updatedAt?: string | null;
  snippet?: string | null;
  referenceNumber?: string | null;
  issuingEntity?: string | null;
  documentType?: string | null;
};

type NormalizedSearchResponse = {
  items: SearchDocument[];
  total?: number;
  page?: number;
  pageSize?: number;
};

type InstitutionOption = { id: string; name: string };

const STATUS_BY_INDEX: Record<number, Exclude<DocumentStatus, number>> = {
  0: "Draft",
  1: "Processing",
  2: "Submitted",
  3: "UnderReview",
  4: "Approved",
  5: "Rejected",
  6: "Published",
  7: "Archived",
};

const PRIORITY_BY_INDEX: Record<number, Exclude<DocumentPriority, number>> = {
  0: "Normal",
  1: "Important",
  2: "Urgent",
};

/* =======================
   Helpers
======================= */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string");
}

function normalizeInstitutionOptions(data: unknown): InstitutionOption[] {
  const rows = Array.isArray(data)
    ? data
    : isRecord(data) && Array.isArray(data.data)
      ? data.data
      : [];
  const ids = new Set<string>();
  for (const row of rows) {
    if (!isRecord(row)) continue;
    const id = asString(row.institutionId)?.trim();
    if (id) ids.add(id);
  }
  return [...ids].sort((a, b) => a.localeCompare(b)).map((id) => ({ id, name: id }));
}

function normalizeStatus(status: DocumentStatus | null | undefined): Exclude<DocumentStatus, number> | null {
  if (typeof status === "number") {
    return STATUS_BY_INDEX[status] ?? null;
  }

  return status ?? null;
}

function normalizePriority(priority: DocumentPriority | null | undefined): Exclude<DocumentPriority, number> | null {
  if (typeof priority === "number") {
    return PRIORITY_BY_INDEX[priority] ?? null;
  }

  return priority ?? null;
}

function normalizeSearchDocument(value: unknown): SearchDocument | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = asString(value.id);
  const title = asString(value.title);

  if (!id || !title) {
    return null;
  }

  const sourceMetadata = isRecord(value.metadata) ? value.metadata : {};
  const metadata = {
    description: asString(sourceMetadata.description) ?? asString(value.description),
    broadGenre: asString(sourceMetadata.broadGenre) ?? asString(value.broadGenre),
    specificGenre: asString(sourceMetadata.specificGenre) ?? asString(value.specificGenre),
    tags: asStringArray(sourceMetadata.tags).length > 0 ? asStringArray(sourceMetadata.tags) : asStringArray(value.tags),
    department: asString(sourceMetadata.department) ?? asString(value.department),
    departmentId: asString(sourceMetadata.departmentId) ?? asString(value.departmentId),
    documentType: asString(sourceMetadata.documentType) ?? asString(value.documentType),
    issuingEntity: asString(sourceMetadata.issuingEntity) ?? asString(value.issuingEntity),
    referenceNumber: asString(sourceMetadata.referenceNumber) ?? asString(value.referenceNumber),
    documentDate: asString(sourceMetadata.documentDate) ?? asString(value.documentDate),
    expirationDate: asString(sourceMetadata.expirationDate) ?? asString(value.expirationDate),
  };

  return {
    id,
    title,
    content: asString(value.content),
    fileName: asString(value.fileName),
    contentType: asString(value.contentType),
    fileSize: asNumber(value.fileSize),
    size: asNumber(value.size),
    ownerId: asString(value.ownerId),
    ownerName: asString(value.ownerName),
    institutionId: asString(value.institutionId),
    departmentId: asString(value.departmentId) ?? metadata.departmentId,
    department: asString(value.department) ?? metadata.department,
    userId: asString(value.userId),
    isSensitive: asBoolean(value.isSensitive),
    status:
      typeof value.status === "string" || typeof value.status === "number"
        ? (value.status as DocumentStatus)
        : null,
    priority:
      typeof value.priority === "string" || typeof value.priority === "number"
        ? (value.priority as DocumentPriority)
        : null,
    createdAt: asString(value.createdAt),
    updatedAt: asString(value.updatedAt),
    snippet: asString(value.snippet),
    referenceNumber: metadata.referenceNumber,
    issuingEntity: metadata.issuingEntity,
    documentType: metadata.documentType,
    metadata,
  };
}

function normalizeSearchResponse(data: unknown): NormalizedSearchResponse {
  if (Array.isArray(data)) {
    return {
      items: data
        .map(normalizeSearchDocument)
        .filter((item): item is SearchDocument => item !== null),
    };
  }

  if (!isRecord(data)) {
    return { items: [] };
  }

  const items = Array.isArray(data.data)
    ? (data.data as SearchDocument[])
    : Array.isArray(data.items)
      ? (data.items as SearchDocument[])
      : Array.isArray(data.documents)
        ? (data.documents as SearchDocument[])
        : [];

  const normalizedItems = items
    .map(normalizeSearchDocument)
    .filter((item): item is SearchDocument => item !== null);

  return {
    items: normalizedItems,
    total: typeof data.total === "number" ? data.total : undefined,
    page: typeof data.page === "number" ? data.page : undefined,
    pageSize: typeof data.pageSize === "number" ? data.pageSize : undefined,
  };
}

function formatDate(d: string | Date | null | undefined, lang: UiLanguage): string {
  if (!d) return "—";
  const dt = typeof d === "string" ? new Date(d) : d;
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleDateString(lang === "ar" ? "ar-SA" : "en-US");
}

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  const rounded = i === 0 ? `${Math.round(v)}` : `${Math.round(v * 10) / 10}`;
  return `${rounded} ${units[i]}`;
}

function labelFromContentType(contentType: string | null | undefined, fileName?: string | null): string {
  const ct = (contentType ?? "").trim().toLowerCase();
  const fn = (fileName ?? "").trim().toLowerCase();

  if (ct === "application/pdf") return "PDF";
  if (ct.startsWith("image/")) return "Image";
  if (ct.includes("spreadsheet") || ct.includes("excel")) return "Excel";
  if (ct.includes("word") || ct.includes("msword")) return "Word";
  if (ct.includes("powerpoint") || ct.includes("presentation")) return "PowerPoint";
  if (ct.startsWith("text/")) return "Text";
  if (ct.includes("zip")) return "Archive";

  const ext = fn.includes(".") ? fn.split(".").pop() ?? "" : "";
  if (ext === "pdf") return "PDF";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(ext)) return "Image";
  if (["xls", "xlsx", "csv"].includes(ext)) return "Excel";
  if (["doc", "docx"].includes(ext)) return "Word";
  if (["ppt", "pptx"].includes(ext)) return "PowerPoint";
  if (ext) return ext.toUpperCase();

  return "Unspecified";
}

/* =======================
   Component
======================= */

export const Search = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { toast } = useToast();
  const { token, user } = useAuth();
  const { language, t } = useLanguage();
  const queryFromUrl = searchParams.get("q") ?? "";

  const [searchTerm, setSearchTerm] = useState(queryFromUrl);
  const [submittedSearchTerm, setSubmittedSearchTerm] = useState(queryFromUrl.trim());
  const [broadGenreFilter, setBroadGenreFilter] = useState("all");
  const [specificGenreFilter, setSpecificGenreFilter] = useState("all");
  const [institutionFilter, setInstitutionFilter] = useState("all");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<"all" | Exclude<DocumentStatus, number>>("all");
  const [priorityFilter, setPriorityFilter] = useState<"all" | Exclude<DocumentPriority, number>>("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [sortBy, setSortBy] = useState<SearchSortBy>("CreatedAt");
  const [sortDesc, setSortDesc] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const [departments, setDepartments] = useState<Department[]>([]);
  const [institutions, setInstitutions] = useState<InstitutionOption[]>([]);
  const [institutionsLoading, setInstitutionsLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<SearchDocument[]>([]);
  const [total, setTotal] = useState<number | undefined>(undefined);

  const isSystemAdmin = user?.backendRole === "SystemAdmin";
  const currentInstitutionId = isSystemAdmin
    ? institutionFilter === "all" ? undefined : institutionFilter
    : user?.institutionId ?? undefined;
  const { label: genreLabel } = useInstitutionTaxonomy(currentInstitutionId, Boolean(currentInstitutionId));

  const hasFilters = useMemo(
    () =>
      Boolean(
        searchTerm.trim() ||
          (isSystemAdmin && institutionFilter !== "all") ||
          broadGenreFilter !== "all" ||
          specificGenreFilter !== "all" ||
          departmentFilter !== "all" ||
          statusFilter !== "all" ||
          priorityFilter !== "all" ||
          fromDate ||
          toDate ||
          sortBy !== "CreatedAt" ||
          !sortDesc ||
          pageSize !== 12,
      ),
    [searchTerm, isSystemAdmin, institutionFilter, broadGenreFilter, specificGenreFilter, departmentFilter, statusFilter, priorityFilter, fromDate, toDate, sortBy, sortDesc, pageSize],
  );

  const selectedDepartment = useMemo(
    () => departments.find((department) => department.id === departmentFilter) ?? null,
    [departmentFilter, departments],
  );

  const totalResults = total ?? results.length;
  const totalPages = Math.max(1, Math.ceil((totalResults || 0) / pageSize));
  const currentPageStart = results.length > 0 ? (page - 1) * pageSize + 1 : 0;
  const currentPageEnd = results.length > 0 ? currentPageStart + results.length - 1 : 0;

  const getStatusPresentation = useCallback(
    (status: DocumentStatus | null | undefined) => {
      const normalized = normalizeStatus(status);

      switch (normalized) {
        case "Draft":
          return { label: t("مسودة", "Draft"), className: "border-slate-200 bg-slate-50 text-slate-700" };
        case "Processing":
          return { label: t("قيد المعالجة", "Processing"), className: "border-amber-200 bg-amber-50 text-amber-700" };
        case "Submitted":
          return { label: t("مرسلة", "Submitted"), className: "border-sky-200 bg-sky-50 text-sky-700" };
        case "UnderReview":
          return { label: t("قيد المراجعة", "Under review"), className: "border-indigo-200 bg-indigo-50 text-indigo-700" };
        case "Approved":
          return { label: t("معتمدة", "Approved"), className: "border-emerald-200 bg-emerald-50 text-emerald-700" };
        case "Rejected":
          return { label: t("مرفوضة", "Rejected"), className: "border-destructive/20 bg-destructive/10 text-destructive" };
        case "Published":
          return { label: t("منشورة", "Published"), className: "border-primary/20 bg-primary/5 text-primary" };
        case "Archived":
          return { label: t("مؤرشفة", "Archived"), className: "border-border bg-muted/60 text-muted-foreground" };
        default:
          return { label: t("غير محددة", "Unknown"), className: "border-border bg-muted/60 text-muted-foreground" };
      }
    },
    [t],
  );

  const getPriorityPresentation = useCallback(
    (priority: DocumentPriority | null | undefined) => {
      const normalized = normalizePriority(priority);

      switch (normalized) {
        case "Urgent":
          return { label: t("عاجلة", "Urgent"), className: "border-destructive/20 bg-destructive/10 text-destructive" };
        case "Important":
          return { label: t("مهمة", "Important"), className: "border-warning/20 bg-warning/10 text-warning" };
        case "Normal":
          return { label: t("عادية", "Normal"), className: "border-primary/20 bg-primary/5 text-primary" };
        default:
          return { label: t("غير محددة", "Unknown"), className: "border-border bg-muted/60 text-muted-foreground" };
      }
    },
    [t],
  );

  const executeSearch = useCallback(async () => {
    if (!token) {
      toast({
        title: t("خطأ", "Error"),
        description: t("يرجى تسجيل الدخول مجدداً.", "Please login again."),
      });
      navigate("/login");
      return;
    }

    setIsSearching(true);

    const payload: SearchDocumentsDto = {
      query: submittedSearchTerm || null,
      institutionId: isSystemAdmin && institutionFilter !== "all" ? institutionFilter : null,
      broadGenre: broadGenreFilter === "all" ? null : broadGenreFilter,
      specificGenre: specificGenreFilter === "all" ? null : specificGenreFilter,
      department: selectedDepartment?.name ?? null,
      departmentId: departmentFilter === "all" ? null : departmentFilter,
      status: statusFilter === "all" ? null : statusFilter,
      priority: priorityFilter === "all" ? null : priorityFilter,
      fromDate: fromDate || null,
      toDate: toDate || null,
      sortBy,
      desc: sortDesc,
      page,
      pageSize,
    };

    try {
      const response = await searchDocumentsRequest(payload);
      const normalized = normalizeSearchResponse(response);
      setResults(normalized.items);
      setTotal(normalized.total ?? normalized.items.length);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 401) {
          toast({
            title: t("غير مصرح", "Unauthorized"),
            description: t("قد تكون الجلسة انتهت أو التوكن غير صالح.", "Your session may have expired or the token is invalid."),
          });
          navigate("/login");
          return;
        }

        toast({
          title: t("فشل البحث", "Search failed"),
          description: t("تأكد من الاتصال أو الصلاحيات.", "Check your connection or permissions."),
        });
      } else {
        toast({
          title: t("خطأ غير متوقع", "Unexpected error"),
          description: t("حدث خطأ غير متوقع.", "An unexpected error occurred."),
        });
      }
    } finally {
      setIsSearching(false);
    }
  }, [
    broadGenreFilter,
    isSystemAdmin,
    institutionFilter,
    specificGenreFilter,
    departmentFilter,
    fromDate,
    navigate,
    page,
    pageSize,
    priorityFilter,
    selectedDepartment,
    sortBy,
    sortDesc,
    statusFilter,
    submittedSearchTerm,
    t,
    toast,
    token,
    toDate,
  ]);

  useEffect(() => {
    if (!token || !isSystemAdmin) {
      setInstitutions([]);
      return;
    }

    const loadInstitutions = async () => {
      try {
        setInstitutionsLoading(true);
        setInstitutions(normalizeInstitutionOptions(await getUsersRequest()));
      } catch {
        setInstitutions([]);
      } finally {
        setInstitutionsLoading(false);
      }
    };

    void loadInstitutions();
  }, [isSystemAdmin, token]);

  useEffect(() => {
    if (!token) {
      return;
    }

    if (isSystemAdmin && !currentInstitutionId) {
      setDepartments([]);
      setDepartmentFilter("all");
      return;
    }

    const loadDepartments = async () => {
      try {
        const departmentData = await getDepartmentsRequest(currentInstitutionId);
        setDepartments(departmentData);
      } catch {
        setDepartments([]);
      }
    };

    void loadDepartments();
  }, [currentInstitutionId, isSystemAdmin, token]);

  useEffect(() => {
    setBroadGenreFilter("all");
    setSpecificGenreFilter("all");
    setDepartmentFilter("all");
    setPage(1);
  }, [institutionFilter]);

  useEffect(() => {
    setSearchTerm(queryFromUrl);
    setSubmittedSearchTerm(queryFromUrl.trim());
    setPage(1);
  }, [queryFromUrl]);

  useEffect(() => {
    if (departmentFilter === "all") {
      return;
    }

    const exists = departments.some((department) => department.id === departmentFilter);
    if (!exists) {
      setDepartmentFilter("all");
    }
  }, [departmentFilter, departments]);

  useEffect(() => {
    if (!token) {
      return;
    }

    const timer = window.setTimeout(() => {
      void executeSearch();
    }, 250);

    return () => window.clearTimeout(timer);
  }, [executeSearch, token]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const handleSearchSubmit = () => {
    const nextTerm = searchTerm.trim();
    if (nextTerm !== submittedSearchTerm) {
      setSubmittedSearchTerm(nextTerm);
    }

    if (page !== 1) {
      setPage(1);
      return;
    }

    void executeSearch();
  };

  const handleResetFilters = () => {
    setSearchTerm("");
    setSubmittedSearchTerm("");
    setInstitutionFilter("all");
    setBroadGenreFilter("all");
    setSpecificGenreFilter("all");
    setDepartmentFilter("all");
    setStatusFilter("all");
    setPriorityFilter("all");
    setFromDate("");
    setToDate("");
    setSortBy("CreatedAt");
    setSortDesc(true);
    setPage(1);
    setPageSize(12);
  };

  const handleDownload = async (docId: string, suggestedName?: string | null) => {
    if (!token) {
      toast({
        title: t("خطأ", "Error"),
        description: t("يرجى تسجيل الدخول مجدداً.", "Please login again."),
      });
      navigate("/login");
      return;
    }

    try {
      const blob = await downloadDocumentRequest(docId);
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement("a");
      a.href = url;
      a.download = suggestedName?.trim() ? suggestedName.trim() : `document_${docId}`;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast({
        title: t("فشل التنزيل", "Download failed"),
        description: t("تعذر تنزيل الملف.", "Could not download the file."),
      });
    }
  };

  const searchIconClass =
    language === "ar"
      ? "absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground w-4 h-4"
      : "absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground w-4 h-4";

  const searchInputPadding = language === "ar" ? "pr-10" : "pl-10";

  return (
    <div className="animate-fade-in p-6" style={{ direction: language === "ar" ? "rtl" : "ltr" }}>
      <div className="mb-6">
        <h1 className="mb-2 font-cairo text-3xl font-bold text-foreground">
          {t("البحث في الوثائق", "Search documents")}
        </h1>
      
      </div>

      <Card className="mb-6 overflow-hidden border-primary/10 shadow-[var(--shadow-card)] hover-lift">
        <div className="gradient-hero h-1.5 w-full" />
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SearchIcon className="h-5 w-5 text-primary" />
            {t("خيارات البحث المتقدم", "Advanced search options")}
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-5">
          <div className="flex flex-col gap-4 lg:flex-row">
            <div className="relative flex-1">
              <SearchIcon className={searchIconClass} />
              <Input
                placeholder={t("ابحث عن وثيقة أو مرجع أو جهة مصدرة...", "Search by title, reference, or issuing entity...")}
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && handleSearchSubmit()}
                className={searchInputPadding}
              />
            </div>

            <div className="flex gap-3">
              <Button onClick={handleSearchSubmit} disabled={isSearching} className="gradient-hero px-8 shadow-[var(--shadow-elegant)]">
                {isSearching ? t("جاري البحث...", "Searching...") : t("بحث", "Search")}
              </Button>

              <Button variant="outline" onClick={handleResetFilters}>
                {t("إعادة تعيين", "Reset")}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            {isSystemAdmin && (
              <Select value={institutionFilter} onValueChange={setInstitutionFilter} disabled={institutionsLoading}>
                <SelectTrigger>
                  <SelectValue placeholder={institutionsLoading ? t("جارٍ تحميل المؤسسات...", "Loading institutions...") : t("اختر المؤسسة", "Select institution")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("كل المؤسسات", "All institutions")}</SelectItem>
                  {institutions.map((institution) => (
                    <SelectItem key={institution.id} value={institution.id}>{institution.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {currentInstitutionId && <GenreSelectors allowAll showLabels={false} institutionId={currentInstitutionId} language={language} broadGenre={broadGenreFilter === "all" ? "" : broadGenreFilter} specificGenre={specificGenreFilter === "all" ? "" : specificGenreFilter} onChange={({ broadGenre, specificGenre }) => { setBroadGenreFilter(broadGenre || "all"); setSpecificGenreFilter(specificGenre || "all"); setPage(1); }} />}

            {(!isSystemAdmin || currentInstitutionId) && <Select value={departmentFilter} onValueChange={(value) => { setDepartmentFilter(value); setPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder={t("القسم", "Department")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("جميع الأقسام", "All departments")}</SelectItem>
                {departments.map((department) => (
                  <SelectItem key={department.id} value={department.id}>
                    {department.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>}

            <Select value={statusFilter} onValueChange={(value) => { setStatusFilter(value as typeof statusFilter); setPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder={t("الحالة", "Status")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("كل الحالات", "All statuses")}</SelectItem>
                <SelectItem value="Draft">{t("مسودة", "Draft")}</SelectItem>
                <SelectItem value="Processing">{t("قيد المعالجة", "Processing")}</SelectItem>
                <SelectItem value="Submitted">{t("مرسلة", "Submitted")}</SelectItem>
                <SelectItem value="UnderReview">{t("قيد المراجعة", "Under review")}</SelectItem>
                <SelectItem value="Approved">{t("معتمدة", "Approved")}</SelectItem>
                <SelectItem value="Rejected">{t("مرفوضة", "Rejected")}</SelectItem>
                <SelectItem value="Published">{t("منشورة", "Published")}</SelectItem>
                <SelectItem value="Archived">{t("مؤرشفة", "Archived")}</SelectItem>
              </SelectContent>
            </Select>

            <Select value={priorityFilter} onValueChange={(value) => { setPriorityFilter(value as typeof priorityFilter); setPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder={t("الأولوية", "Priority")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("كل الأولويات", "All priorities")}</SelectItem>
                <SelectItem value="Normal">{t("عادية", "Normal")}</SelectItem>
                <SelectItem value="Important">{t("مهمة", "Important")}</SelectItem>
                <SelectItem value="Urgent">{t("عاجلة", "Urgent")}</SelectItem>
              </SelectContent>
            </Select>

            <Input type="date" value={fromDate} onChange={(event) => { setFromDate(event.target.value); setPage(1); }} />
            <Input type="date" value={toDate} onChange={(event) => { setToDate(event.target.value); setPage(1); }} />

            <Select value={sortBy} onValueChange={(value) => { setSortBy(value as SearchSortBy); setPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder={t("الترتيب حسب", "Sort by")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="CreatedAt">{t("تاريخ الإضافة", "Date added")}</SelectItem>
                <SelectItem value="Title">{t("عنوان الوثيقة", "Document title")}</SelectItem>
                <SelectItem value="Size">{t("حجم الملف", "File size")}</SelectItem>
              </SelectContent>
            </Select>

            <Select value={String(pageSize)} onValueChange={(value) => { setPageSize(Number(value)); setPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder={t("حجم الصفحة", "Page size")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="12">12</SelectItem>
                <SelectItem value="24">24</SelectItem>
                <SelectItem value="48">48</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between rounded-2xl bg-muted/40 p-4">
            <div className="flex items-center gap-2">
              {sortDesc ? <SortDesc className="h-5 w-5 text-secondary" /> : <SortAsc className="h-5 w-5 text-secondary" />}
              <Label htmlFor="sortDesc">{t("ترتيب تنازلي", "Descending")}</Label>
            </div>
            <div dir="ltr" className="flex items-center">
              <Switch id="sortDesc" checked={sortDesc} onCheckedChange={(checked) => { setSortDesc(checked); setPage(1); }} />
            </div>
          </div>

          {!hasFilters && (
            <p className="text-xs text-muted-foreground">
              {t(
                "يمكنك البحث بكلمة مفتاحية أو الاكتفاء بالفلاتر فقط، وستظهر النتائج ضمن نطاق صلاحياتك.",
                "You can search by keyword or rely on filters only; results will stay within your access scope.",
              )}
            </p>
          )}
        </CardContent>
      </Card>

      {isSearching ? (
        <div className="rounded-2xl border border-primary/10 bg-card p-10 text-center text-lg text-muted-foreground shadow-[var(--shadow-card)]">
          {t("جاري جلب النتائج...", "Loading results...")}
        </div>
      ) : results.length > 0 ? (
        <Card className="overflow-hidden border-primary/10 shadow-[var(--shadow-card)] hover-lift">
          <div className="gradient-primary h-1.5 w-full" />
          <CardHeader className="gap-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                {t("نتائج البحث", "Search results")} ({totalResults})
              </CardTitle>

              <div className="text-sm text-muted-foreground">
                {t("عرض", "Showing")} {currentPageStart}-{currentPageEnd} {t("من", "of")} {totalResults}
              </div>
            </div>
          </CardHeader>

          <CardContent>
            <div className="space-y-4">
              {results.map((doc, index) => {
                const status = getStatusPresentation(doc.status);
                const priority = getPriorityPresentation(doc.priority);
                const fileSize = doc.size ?? doc.fileSize ?? null;
                const contentLabel = labelFromContentType(doc.contentType ?? null, doc.fileName ?? null);
                const created = formatDate(doc.createdAt, language as UiLanguage);
                const updated = formatDate(doc.updatedAt ?? null, language as UiLanguage);
                const snippet = doc.snippet?.trim() || doc.metadata?.description || "—";
                const referenceNumber = doc.metadata?.referenceNumber ?? doc.referenceNumber ?? null;
                const issuingEntity = doc.metadata?.issuingEntity ?? doc.issuingEntity ?? null;

                return (
                  <Card
                    key={doc.id}
                    className="animate-stagger cursor-pointer border-primary/10 transition-all duration-300 hover:-translate-y-1 hover:shadow-[var(--shadow-card)]"
                    style={{ animationDelay: `${index * 0.05}s` }}
                    onClick={() => navigate(`/documents/${doc.id}`)}
                  >
                    <CardContent className="pt-6">
                      <div className="flex items-start gap-4">
                        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl gradient-hero shadow-[var(--shadow-elegant)]">
                          <FileText className="h-6 w-6 text-white" />
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                            <div className="min-w-0">
                              <h3 className="mb-1 truncate text-lg font-bold text-foreground">{doc.title}</h3>
                              <p className="mb-3 line-clamp-2 text-sm text-muted-foreground">{snippet}</p>

                              <div className="mb-3 flex flex-wrap gap-2">
                                <Badge variant="secondary">
                                  {[genreLabel(doc.metadata?.broadGenre, language), genreLabel(doc.metadata?.specificGenre, language)].filter((value) => value !== "—").join(" / ") || t("غير مصنف", "Uncategorized")}
                                </Badge>
                                <Badge variant="outline">{doc.department || t("عام", "General")}</Badge>
                                <Badge variant="outline" className={cn("font-medium", status.className)}>
                                  {status.label}
                                </Badge>
                                <Badge variant="outline" className={cn("font-medium", priority.className)}>
                                  {priority.label}
                                </Badge>
                                {doc.isSensitive && (
                                  <Badge variant="outline" className="border-destructive/20 bg-destructive/10 text-destructive">
                                    <ShieldAlert className={language === "ar" ? "ml-1 h-3 w-3" : "mr-1 h-3 w-3"} />
                                    {t("حساسة", "Sensitive")}
                                  </Badge>
                                )}
                              </div>
                            </div>

                            <div className="flex gap-2 xl:flex-shrink-0">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  navigate(`/documents/${doc.id}`);
                                }}
                              >
                                <Eye className={language === "ar" ? "ml-2 h-4 w-4" : "mr-2 h-4 w-4"} />
                                {t("عرض", "View")}
                              </Button>

                              <Button
                                variant="outline"
                                size="sm"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void handleDownload(doc.id, doc.fileName ?? null);
                                }}
                              >
                                <Download className={language === "ar" ? "ml-2 h-4 w-4" : "mr-2 h-4 w-4"} />
                                {t("تنزيل", "Download")}
                              </Button>
                            </div>
                          </div>

                          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                              <FileType className="h-3.5 w-3.5" />
                              {contentLabel}
                            </div>

                            <div className="flex items-center gap-1">
                              <HardDrive className="h-3.5 w-3.5" />
                              {formatBytes(fileSize)}
                            </div>

                            <div className="flex items-center gap-1">
                              <Calendar className="h-3.5 w-3.5" />
                              {created}
                            </div>

                            {updated !== "—" && (
                              <div className="flex items-center gap-1">
                                <Calendar className="h-3.5 w-3.5" />
                                {t("تحديث:", "Updated:")} {updated}
                              </div>
                            )}

                            {(doc.ownerName || doc.ownerId) && (
                              <div className="flex items-center gap-1">
                                <User className="h-3.5 w-3.5" />
                                {doc.ownerName || doc.ownerId}
                              </div>
                            )}
                          </div>

                          {(referenceNumber || issuingEntity || doc.fileName || doc.contentType) && (
                            <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                              {referenceNumber && (
                                <div className="truncate">
                                  <span className="font-medium text-foreground">{t("المرجع:", "Reference:")}</span> {referenceNumber}
                                </div>
                              )}
                              {issuingEntity && (
                                <div className="truncate">
                                  <span className="font-medium text-foreground">{t("الجهة:", "Issuing entity:")}</span> {issuingEntity}
                                </div>
                              )}
                              {doc.fileName && (
                                <div className="truncate">
                                  <span className="font-medium text-foreground">{t("الملف:", "File:")}</span> {doc.fileName}
                                </div>
                              )}
                              {doc.contentType && (
                                <div className="truncate">
                                  <span className="font-medium text-foreground">{t("النوع:", "Content-Type:")}</span> {doc.contentType}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            <div className="mt-6 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-muted-foreground">
                {t("الصفحة", "Page")} {page} {t("من", "of")} {totalPages}
              </div>

              <div className="flex gap-2">
                <Button variant="outline" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                  {language === "ar" ? <ChevronRight className="ml-2 h-4 w-4" /> : <ChevronLeft className="mr-2 h-4 w-4" />}
                  {t("السابق", "Previous")}
                </Button>

                <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>
                  {t("التالي", "Next")}
                  {language === "ar" ? <ChevronLeft className="mr-2 h-4 w-4" /> : <ChevronRight className="ml-2 h-4 w-4" />}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-2xl border border-primary/10 bg-card p-10 text-center shadow-[var(--shadow-card)]">
          <p className="text-lg text-muted-foreground">
            {t("لم يتم العثور على نتائج ضمن نطاق صلاحياتك الحالية.", "No results were found within your current access scope.")}
          </p>
          {(submittedSearchTerm || hasFilters) && (
            <p className="mt-2 text-sm text-muted-foreground">
              {submittedSearchTerm
                ? t("حاول تعديل الكلمة المفتاحية أو الفلاتر للحصول على نتائج أدق.", "Try adjusting the keyword or filters for better results.")
                : t("جرّب تخفيف الفلاتر للحصول على نتائج أكثر.", "Try relaxing the filters to see more results.")}
            </p>
          )}
        </div>
      )}
    </div>
  );
};
