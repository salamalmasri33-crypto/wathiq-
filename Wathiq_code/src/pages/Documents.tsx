import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { AxiosError } from "axios";
import {
  Download,
  Eye,
  FileText,
  Search as SearchIcon,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";

import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { getPrimaryBackendRole } from "@/lib/roles";
import { canDeleteDocument } from "@/lib/document-authorization";
import { getDepartmentsRequest } from "@/services/departments.service";
import {
  deleteDocumentRequest,
  downloadDocumentRequest,
  searchDocumentsRequest,
} from "@/services/documents.service";
import type { Department } from "@/types/platform";
import type { Document, DocumentPriority, DocumentStatus, Metadata } from "@/types/document";
import { GenreSelectors } from "@/components/GenreSelectors";
import { useInstitutionTaxonomy } from "@/hooks/use-institution-taxonomy";

type DocumentsSearchResult = {
  documents: Document[];
  total: number;
  page: number;
  pageSize: number;
};

type StatusLabel = Exclude<DocumentStatus, number>;
type PriorityLabel = Exclude<DocumentPriority, number>;

type AxiosLikeError = AxiosError<unknown>;

const CATEGORY_OPTIONS = [
  { value: "عقد", en: "Contract" },
  { value: "فاتورة", en: "Invoice" },
  { value: "تقرير", en: "Report" },
  { value: "شهادة", en: "Certificate" },
  { value: "أخرى", en: "Other" },
] as const;

const STATUS_BY_INDEX: Record<number, StatusLabel> = {
  0: "Draft",
  1: "Processing",
  2: "Submitted",
  3: "UnderReview",
  4: "Approved",
  5: "Rejected",
  6: "Published",
  7: "Archived",
};

const PRIORITY_BY_INDEX: Record<number, PriorityLabel> = {
  0: "Normal",
  1: "Important",
  2: "Urgent",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function asNullableBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringArray(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }

  return value.filter((item): item is string => typeof item === "string");
}

function normalizeStatus(status: DocumentStatus | null | undefined): StatusLabel | null {
  if (typeof status === "number") {
    return STATUS_BY_INDEX[status] ?? null;
  }

  return status ?? null;
}

function normalizePriority(priority: DocumentPriority | null | undefined): PriorityLabel | null {
  if (typeof priority === "number") {
    return PRIORITY_BY_INDEX[priority] ?? null;
  }

  return priority ?? null;
}

function normalizeSearchDocument(value: unknown): Document | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = asString(value.id);
  const title = asString(value.title);

  if (!id || !title) {
    return null;
  }

  const metadata: Metadata = {
    description: asString(value.description),
    broadGenre: asString(value.broadGenre),
    specificGenre: asString(value.specificGenre),
    department: asString(value.department),
    departmentId: asString(value.departmentId),
    documentType: asString(value.documentType),
    issuingEntity: asString(value.issuingEntity),
    referenceNumber: asString(value.referenceNumber),
    tags: asStringArray(value.tags),
  };

  return {
    id,
    title,
    content: asString(value.content),
    institutionId: asString(value.institutionId),
    departmentId: asString(value.departmentId),
    department: asString(value.department),
    userId: asString(value.userId),
    isSensitive: asNullableBoolean(value.isSensitive),
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
    metadata,
  };
}

function normalizeDocumentsSearchResponse(data: unknown): DocumentsSearchResult {
  if (Array.isArray(data)) {
    const documents = data
      .map(normalizeSearchDocument)
      .filter((item): item is Document => item !== null);

    return {
      documents,
      total: documents.length,
      page: 1,
      pageSize: documents.length || 10,
    };
  }

  if (!isRecord(data)) {
    return { documents: [], total: 0, page: 1, pageSize: 10 };
  }

  const candidates = Array.isArray(data.data)
    ? data.data
    : Array.isArray(data.items)
      ? data.items
      : Array.isArray(data.documents)
        ? data.documents
        : [];

  const documents = candidates
    .map(normalizeSearchDocument)
    .filter((item): item is Document => item !== null);

  const total = asNullableNumber(data.total) ?? documents.length;
  const page = asNullableNumber(data.page) ?? 1;
  const pageSize = asNullableNumber(data.pageSize) ?? 10;

  return { documents, total, page, pageSize };
}

function getAxiosMessage(error: unknown): string | null {
  const axiosError = error as AxiosLikeError;
  const responseData = axiosError?.response?.data;

  if (typeof responseData === "string") {
    return responseData;
  }

  if (isRecord(responseData) && typeof responseData.message === "string") {
    return responseData.message;
  }

  return null;
}

function getStatusBadgeClass(status: StatusLabel | null): string {
  switch (status) {
    case "Draft":
      return "border-border bg-muted/50 text-muted-foreground";
    case "Processing":
      return "border-warning/20 bg-warning/10 text-warning";
    case "Submitted":
      return "border-warning/20 bg-warning/10 text-warning";
    case "UnderReview":
      return "border-warning/20 bg-warning/10 text-warning";
    case "Approved":
      return "border-success/20 bg-success/10 text-success";
    case "Rejected":
      return "border-destructive/20 bg-destructive/10 text-destructive";
    case "Published":
      return "border-primary/20 bg-primary/5 text-primary";
    case "Archived":
      return "border-border bg-muted/50 text-muted-foreground";
    default:
      return "border-border bg-muted/40 text-muted-foreground";
  }
}

function getPriorityBadgeClass(priority: PriorityLabel | null): string {
  switch (priority) {
    case "Urgent":
      return "border-destructive/20 bg-destructive/10 text-destructive";
    case "Important":
      return "border-destructive/20 bg-destructive/10 text-destructive";
    case "Normal":
      return "border-success/20 bg-success/10 text-success";
    default:
      return "border-border bg-muted/50 text-muted-foreground";
  }
}

export const Documents = () => {
  const { user, token } = useAuth();
  const { language, t } = useLanguage();
  const { label: genreLabel } = useInstitutionTaxonomy(user?.institutionId ?? undefined);
  const { toast } = useToast();
  const navigate = useNavigate();

  const currentBackendRole = getPrimaryBackendRole(user);
  const isRTL = language === "ar";
  const canUpload = currentBackendRole === "Manager";

  const [searchTerm, setSearchTerm] = useState("");
  const [broadGenreFilter, setBroadGenreFilter] = useState<string>("all");
  const [specificGenreFilter, setSpecificGenreFilter] = useState<string>("all");
  const [departmentFilter, setDepartmentFilter] = useState<string>("all");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(false);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const pageTitle = useMemo(() => {
    switch (currentBackendRole) {
      case "SystemAdmin":
      case "InstitutionAdmin":
        return t("إدارة الوثائق", "Documents management");
      case "Manager":
        return t("وثائق القسم", "Department documents");
      default:
        return t("الوثائق", "Documents");
    }
  }, [currentBackendRole, t]);

  const pageDescription = useMemo(() => {
    switch (currentBackendRole) {
      case "SystemAdmin":
        return t("استعراض وثائق النظام كاملة مع وصول سريع لأهم الإجراءات.", "Review all system documents with quick actions.");
      case "InstitutionAdmin":
        return t("متابعة وثائق المؤسسة والوصول السريع للوثائق الأهم.", "Track institution documents and access key items quickly.");
      case "Manager":
        return t("متابعة وثائق القسم مع رفع سريع للوثائق الجديدة.", "Track department documents and quickly add new files.");
      default:
        return t("متابعة الوثائق المتاحة ضمن نطاق صلاحياتك.", "Track the documents available within your access scope.");
    }
  }, [currentBackendRole, t]);

  const formatDate = useCallback(
    (value: string | null | undefined) => {
      if (!value) {
        return "—";
      }

      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return "—";
      }

      return date.toLocaleDateString(language === "ar" ? "ar-SA" : "en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    },
    [language],
  );

  const getStatusLabel = useCallback(
    (status: DocumentStatus | null | undefined) => {
      switch (normalizeStatus(status)) {
        case "Draft":
          return t("مسودة", "Draft");
        case "Processing":
          return t("قيد المعالجة", "Processing");
        case "Submitted":
          return t("مرسلة", "Submitted");
        case "UnderReview":
          return t("قيد المراجعة", "Under review");
        case "Approved":
          return t("موافَق عليها", "Approved");
        case "Rejected":
          return t("مرفوضة", "Rejected");
        case "Published":
          return t("منشورة", "Published");
        case "Archived":
          return t("مؤرشفة", "Archived");
        default:
          return t("غير محددة", "Unknown");
      }
    },
    [t],
  );

  const getPriorityLabel = useCallback(
    (priority: DocumentPriority | null | undefined) => {
      switch (normalizePriority(priority)) {
        case "Urgent":
          return t("عاجلة", "Urgent");
        case "Important":
          return t("مهمة", "Important");
        case "Normal":
          return t("عادية", "Normal");
        default:
          return t("غير محددة", "Unknown");
      }
    },
    [t],
  );

  const fetchDocuments = useCallback(async () => {
    if (!token) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const response = await searchDocumentsRequest({
        query: searchTerm.trim() || null,
        broadGenre: currentBackendRole === "SystemAdmin" || broadGenreFilter === "all" ? null : broadGenreFilter,
        specificGenre: currentBackendRole === "SystemAdmin" || specificGenreFilter === "all" ? null : specificGenreFilter,
        departmentId: departmentFilter === "all" ? null : departmentFilter,
        sortBy: "CreatedAt",
        desc: true,
        page,
        pageSize,
      });

      const normalized = normalizeDocumentsSearchResponse(response);
      setDocuments(normalized.documents);
      setTotal(normalized.total);
    } catch (error) {
      console.error("Failed to fetch documents:", error);
      setDocuments([]);
      setTotal(0);
      setErrorMessage(
        getAxiosMessage(error) ??
          t("تعذر جلب الوثائق حالياً. حاول مرة أخرى.", "Unable to load documents right now. Please try again."),
      );
    } finally {
      setLoading(false);
    }
  }, [broadGenreFilter, specificGenreFilter, currentBackendRole, departmentFilter, page, pageSize, searchTerm, t, token]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void fetchDocuments();
    }, 250);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [fetchDocuments]);

  useEffect(() => {
    if (!token) {
      return;
    }

    const scopedInstitutionId = user?.institutionId?.trim() || undefined;

    if (currentBackendRole === "SystemAdmin" && !scopedInstitutionId) {
      setDepartments([]);
      setDepartmentFilter("all");
      return;
    }

    const loadDepartments = async () => {
      try {
        setDepartmentsLoading(true);
        const response = await getDepartmentsRequest(scopedInstitutionId);
        setDepartments(response);
      } catch (error) {
        console.error("Failed to fetch departments:", error);
        setDepartments([]);
      } finally {
        setDepartmentsLoading(false);
      }
    };

    void loadDepartments();
  }, [currentBackendRole, token, user?.institutionId]);

  const handleDownload = async (document: Document) => {
    try {
      const file = await downloadDocumentRequest(document.id);
      const blobUrl = URL.createObjectURL(file);
      const anchor = window.document.createElement("a");

      anchor.href = blobUrl;
      anchor.download = document.title ?? "document";
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error("Failed to download document:", error);
      toast({
        variant: "destructive",
        title: t("فشل تحميل الوثيقة", "Failed to download document"),
        description:
          getAxiosMessage(error) ??
          t("تعذر تحميل الملف حالياً.", "Unable to download the file right now."),
      });
    }
  };

  const handleDelete = async (document: Document) => {
    const confirmed = window.confirm(
      t(
        `هل أنت متأكد من حذف الوثيقة ${document.title ?? ""}؟`,
        `Are you sure you want to delete ${document.title ?? "this document"}?`,
      ),
    );

    if (!confirmed) {
      return;
    }

    try {
      await deleteDocumentRequest(document.id);

      toast({
        title: t("تم حذف الوثيقة", "Document deleted"),
        description: t("تم حذف الوثيقة بنجاح.", "The document was deleted successfully."),
      });

      if (documents.length === 1 && page > 1) {
        setPage((currentPage) => Math.max(1, currentPage - 1));
        return;
      }

      await fetchDocuments();
    } catch (error) {
      console.error("Failed to delete document:", error);
      toast({
        variant: "destructive",
        title: t("فشل حذف الوثيقة", "Failed to delete document"),
        description:
          getAxiosMessage(error) ??
          t("تعذر حذف الوثيقة حالياً.", "Unable to delete the document right now."),
      });
    }
  };

  return (
    <div className="animate-fade-in p-4 sm:p-6" style={{ direction: isRTL ? "rtl" : "ltr" }}>
      <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h1 className="mb-2 text-3xl font-cairo font-bold text-foreground">{pageTitle}</h1>
          <p className="text-muted-foreground">{pageDescription}</p>
        </div>

        <div className={cn("flex flex-col gap-3 sm:flex-row", isRTL ? "xl:justify-start" : "xl:justify-end")}>
          <Button
            className="gradient-hero shadow-[var(--shadow-elegant)] transition-transform duration-300 hover:-translate-y-0.5"
            onClick={() => navigate("/search")}
          >
            <SearchIcon className= {cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
            {t("الانتقال إلى البحث المتقدم", "Go to advanced search")}
          </Button>

          {canUpload && (
            <Button className="gradient-hero shadow-[var(--shadow-elegant)]" onClick={() => navigate("/add-document")}>
              <Upload className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
              {t("إضافة وثيقة جديدة", "Add a new document")}
            </Button>
          )}
        </div>
      </div>

      <div className="mb-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_220px_auto]">
        <Card className="hover-lift animate-slide-up">
          <CardContent className="pt-6">
            <div className="relative">
              <SearchIcon
                className={cn(
                  "absolute top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground",
                  isRTL ? "right-3" : "left-3",
                )}
              />
              <Input
                value={searchTerm}
                onChange={(event) => {
                  setPage(1);
                  setSearchTerm(event.target.value);
                }}
                placeholder={t("بحث سريع بعنوان الوثيقة أو وصفها...", "Quick search by title or description...")}
                className={cn(isRTL ? "pr-10" : "pl-10")}
              />
            </div>
          </CardContent>
        </Card>

        {currentBackendRole !== "SystemAdmin" && <Card className="hover-lift animate-slide-up">
          <CardContent className="pt-6">
            <div className="grid gap-4 md:grid-cols-2"><GenreSelectors allowAll showLabels={false} institutionId={user?.institutionId ?? undefined} language={language} broadGenre={broadGenreFilter === "all" ? "" : broadGenreFilter} specificGenre={specificGenreFilter === "all" ? "" : specificGenreFilter} onChange={({ broadGenre, specificGenre }) => { setPage(1); setBroadGenreFilter(broadGenre || "all"); setSpecificGenreFilter(specificGenre || "all"); }} /></div>
          </CardContent>
        </Card>}

        {currentBackendRole !== "SystemAdmin" && <Card className="hover-lift animate-slide-up">
          <CardContent className="pt-6">
            <Select
              value={departmentFilter}
              onValueChange={(value) => {
                setPage(1);
                setDepartmentFilter(value);
              }}
              disabled={departmentsLoading}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={
                    departmentsLoading
                      ? t("جارٍ تحميل الأقسام...", "Loading departments...")
                      : t("القسم", "Department")
                  }
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("كل الأقسام", "All departments")}</SelectItem>
                {departments.map((department) => (
                  <SelectItem key={department.id} value={department.id}>
                    {department.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>}

        <Card className="hover-lift animate-slide-up">
          <CardContent className="flex h-full items-center justify-center pt-6">
            <div className="text-center">
              <p className="text-sm text-muted-foreground">{t("\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0646\u062a\u0627\u0626\u062c", "Total results")}</p>
              <p className="text-2xl font-cairo font-bold text-foreground">{total}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {errorMessage && (
        <Card className="mb-6 border-destructive/20 bg-destructive/5">
          <CardContent className="p-4 text-sm text-destructive">{errorMessage}</CardContent>
        </Card>
      )}

      <Card className="hover-lift animate-slide-up">
        <CardHeader className="gap-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                {t("قائمة الوثائق", "Documents list")}
              </CardTitle>
              <CardDescription />
            </div>

          
          </div>
        </CardHeader>

        <CardContent>
          <div className="overflow-x-auto">
            <Table className="min-w-[920px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="text-center">{t("الوثيقة", "Document")}</TableHead>
                  <TableHead className="text-center">{t("التصنيف العام / الخاص", "Broad / specific genre")}</TableHead>
                  <TableHead className="text-center">{t("القسم", "Department")}</TableHead>
                  <TableHead className="text-center">{t("الحالة", "Status")}</TableHead>
                  <TableHead className="text-center">{t("الأولوية", "Priority")}</TableHead>
                  <TableHead className="text-center">{t("الحساسية", "Sensitivity")}</TableHead>
                  <TableHead className="text-center">{t("تاريخ الإنشاء", "Created at")}</TableHead>
                  <TableHead className="text-center">{t("الإجراءات", "Actions")}</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                      {t("جارٍ تحميل الوثائق...", "Loading documents...")}
                    </TableCell>
                  </TableRow>
                ) : documents.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="py-12 text-center text-muted-foreground">
                      {t("لا توجد وثائق مطابقة للبحث السريع الحالي.", "No documents match the current quick search.")}
                    </TableCell>
                  </TableRow>
                ) : (
                  documents.map((document, index) => {
                    const status = normalizeStatus(document.status);
                    const priority = normalizePriority(document.priority);

                    return (
                      <TableRow
                        key={document.id}
                        className="animate-stagger hover:bg-muted/60"
                        style={{ animationDelay: `${index * 0.04}s` }}
                      >
                        <TableCell>
                          <div className={cn("mx-auto max-w-[260px]", isRTL ? "text-right" : "text-left")}>
                            <p className="truncate font-medium text-foreground">{document.title ?? "-"}</p>
                            <div className="mt-1 space-y-1 text-xs text-muted-foreground">
                              {document.metadata?.referenceNumber && (
                                <p className="truncate">
                                  {t("\u0627\u0644\u0645\u0631\u062c\u0639", "Ref")}: {document.metadata.referenceNumber}
                                </p>
                              )}
                              {document.metadata?.issuingEntity && (
                                <p className="truncate">
                                  {t("\u0627\u0644\u062c\u0647\u0629", "Entity")}: {document.metadata.issuingEntity}
                                </p>
                              )}
                            </div>
                          </div>
                        </TableCell>

                        <TableCell className="text-center">
                          <Badge variant="outline" className="border-primary/15 bg-primary/5 text-primary">
                            {[genreLabel(document.metadata?.broadGenre, language), genreLabel(document.metadata?.specificGenre, language)].filter((value) => value !== "—").join(" / ") || "—"}
                          </Badge>
                        </TableCell>

                        <TableCell className="text-center">{document.department ?? document.metadata?.department ?? "—"}</TableCell>

                        <TableCell className="text-center">
                          <Badge variant="outline" className={cn("font-medium", getStatusBadgeClass(status))}>
                            {getStatusLabel(status)}
                          </Badge>
                        </TableCell>

                        <TableCell className="text-center">
                          <Badge variant="outline" className={cn("font-medium", getPriorityBadgeClass(priority))}>
                            {getPriorityLabel(priority)}
                          </Badge>
                        </TableCell>

                        <TableCell className="text-center">
                          {document.isSensitive ? (
                            <Badge variant="outline" className="border-destructive/20 bg-destructive/10 text-destructive">
                              <ShieldAlert className={cn("h-3.5 w-3.5", isRTL ? "ml-1" : "mr-1")} />
                              {t("حساسة", "Sensitive")}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="border-success/20 bg-success/10 text-success">
                              {t("عادية", "Normal")}
                            </Badge>
                          )}
                        </TableCell>

                        <TableCell className="text-center">{formatDate(document.createdAt)}</TableCell>

                        <TableCell>
                          <div className="flex items-center justify-center gap-2">
                            <Button variant="ghost" size="sm" onClick={() => navigate(`/documents/${document.id}`)}>
                              <Eye className="h-4 w-4" />
                            </Button>

                            <Button variant="ghost" size="sm" onClick={() => void handleDownload(document)}>
                              <Download className="h-4 w-4" />
                            </Button>

                            {canDeleteDocument(user, document) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                                onClick={() => void handleDelete(document)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>

          <div className="mt-6 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              {t("الصفحة", "Page")} {page} {t("من", "of")} {totalPages}
            </p>

            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))} disabled={page <= 1 || loading}>
                {t("السابق", "Previous")}
              </Button>
              <Button
                variant="outline"
                onClick={() => setPage((currentPage) => Math.min(totalPages, currentPage + 1))}
                disabled={page >= totalPages || loading}
              >
                {t("التالي", "Next")}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Documents;
