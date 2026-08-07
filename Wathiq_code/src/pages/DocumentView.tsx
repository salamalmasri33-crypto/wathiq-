import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { AxiosError } from "axios";
import {
  AlertTriangle,
  Archive,
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock,
  Download,
  Edit,
  Eye,
  FileText,
  Send,
  Share2,
  ShieldAlert,
  Sparkles,
  Tag,
  Trash2,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DocumentSegmentationSection } from "@/components/DocumentSegmentationSection";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/use-toast";
import {
  canArchiveDocument,
  canDeleteDocument,
  canEditDocument,
  canPublishDocument,
  canTransferDocument,
  getDocumentOwnerName,
} from "@/lib/document-authorization";
import { getPrimaryBackendRole } from "@/lib/roles";
import { cn } from "@/lib/utils";
import {
  deleteDocumentRequest,
  downloadDocumentRequest,
  getDocumentOcrTextRequest,
  getDocumentTimelineRequest,
  getDocumentViewRequest,
} from "@/services/documents.service";
import { getDepartmentsRequest } from "@/services/departments.service";
import { getDocumentAccessRequest } from "@/services/permissions.service";
import {
  approveDocumentRequest,
  archiveDocumentRequest,
  publishDocumentRequest,
  rejectDocumentRequest,
  startReviewRequest,
  submitDocumentRequest,
  transferDocumentRequest,
} from "@/services/workflow.service";
import type { Document, DocumentOcrText, DocumentPriority, DocumentStatus, DocumentTimelineEntry, OcrProcessingResponse } from "@/types/document";
import type { ReviewDecisionDto, TransferDocumentDto } from "@/types/dto";
import type { Department, DocumentAccessReview } from "@/types/platform";
import type { BackendRole, User } from "@/types/user";

type StatusLabel = Exclude<DocumentStatus, number>;
type PriorityLabel = Exclude<DocumentPriority, number>;
type WorkflowAction = "submit" | "startReview" | "approve" | "reject" | "publish" | "archive" | "transfer";

type WorkflowButton = {
  action: WorkflowAction;
  label: string;
  icon: ReactNode;
  tone?: "primary" | "success" | "danger" | "secondary";
};

type TimelineItem = {
  id: string;
  title: string;
  at: string | null | undefined;
  actor: string;
  description: string | null | undefined;
};

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

function isOcrProcessingResponse(data: unknown): data is OcrProcessingResponse {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  return obj.status === "processing";
}

function coerceDocumentOcrText(data: unknown): DocumentOcrText | null {
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;

  const rawText = typeof obj.rawText === "string" ? obj.rawText : "";
  const normalizedText = typeof obj.normalizedText === "string" ? obj.normalizedText : "";
  const documentId = typeof obj.documentId === "string" ? obj.documentId : "";

  if (!documentId) return null;

  return {
    documentId,
    title: typeof obj.title === "string" ? obj.title : null,
    status: (obj.status as DocumentStatus | null | undefined) ?? null,
    rawText,
    normalizedText,
    provider: typeof obj.provider === "string" ? obj.provider : null,
    language: typeof obj.language === "string" ? obj.language : null,
    pages: typeof obj.pages === "number" ? obj.pages : null,
    extractedAt: typeof obj.extractedAt === "string" ? obj.extractedAt : null,
  };
}

function buildMockDocument(documentId: string, backendRole: BackendRole | null, user: User | null): Document {
  const role = backendRole ?? "Employee";
  const statusByRole: Record<BackendRole, StatusLabel> = {
    SystemAdmin: "Published",
    InstitutionAdmin: "Approved",
    Manager: "Submitted",
    Employee: "Draft",
  };

  return {
    id: documentId,
    title: "محضر اجتماع لجنة التحول الرقمي",
    fileName: "digital-transformation-committee-minutes.pdf",
    contentType: "application/pdf",
    size: 2480000,
    institutionId: user?.institutionId ?? "inst-wathiq-01",
    departmentId: user?.departmentId ?? "dept-legal",
    department: user?.department ?? "القسم القانوني",
    userId: role === "Employee" ? user?.id ?? "employee-demo" : "employee-archive-24",
    ownerName: role === "Employee" ? user?.name ?? "سارة الخطيب" : "أحمد النجار",
    content:
      "محضر اجتماع لجنة التحول الرقمي\n\n" +
      "تمت مناقشة تحديث سياسات الأرشفة الرقمية واعتماد المسار المرحلي لتفعيل الفهرسة الذكية وربط الوثائق بالمراجعة القانونية.\n\n" +
      "أبرز البنود:\n" +
      "1. اعتماد مسار موحد للوثائق الإدارية الجديدة.\n" +
      "2. تفعيل مراجعة قانونية قبل النشر النهائي.\n" +
      "3. جدولة أرشفة النسخ المعتمدة فقط.\n" +
      "4. اعتماد مرجع موحد للقرارات الصادرة عن اللجنة.\n",
    createdAt: "2026-04-14T08:30:00.000Z",
    updatedAt: "2026-04-17T13:05:00.000Z",
    priority: role === "Employee" ? "Normal" : role === "Manager" ? "Important" : "Urgent",
    isSensitive: role !== "Employee",
    status: statusByRole[role],
    submittedAt: role === "Employee" ? null : "2026-04-15T10:15:00.000Z",
    reviewStartedAt: role === "InstitutionAdmin" || role === "SystemAdmin" ? "2026-04-15T12:10:00.000Z" : null,
    reviewedAt: role === "InstitutionAdmin" || role === "SystemAdmin" ? "2026-04-16T14:20:00.000Z" : null,
    publishedAt: role === "SystemAdmin" ? "2026-04-17T11:40:00.000Z" : null,
    metadata: {
      description:
        "وثيقة داخلية تلخص قرارات اللجنة بخصوص تطوير مسارات الأرشفة الرقمية والاعتماد المرحلي للسياسات الجديدة.",
      broadGenre: "AdministrativeAndOrganizational",
      specificGenre: "AdministrativeReport",
      department: user?.department ?? "القسم القانوني",
      departmentId: user?.departmentId ?? "dept-legal",
      documentType: "PDF",
      expirationDate: "2027-04-14T00:00:00.000Z",
      issuingEntity: "مكتب الأمين العام",
      referenceNumber: "WA-2026-0142",
      documentDate: "2026-04-14T00:00:00.000Z",
      tags: ["تحول رقمي", "أرشفة", "لجنة", "حوكمة"],
      insights: ["تمت مراجعة النسخة الأولية واعتمادها كمرجع داخلي."],
      rawExtractionJson:
        "محضر اجتماع لجنة التحول الرقمي\nتمت مناقشة تحديث سياسات الأرشفة الرقمية واعتماد المسار المرحلي لتفعيل الفهرسة الذكية.",
    },
  };
}

function buildMockTimeline(document: Document, actorName: string): DocumentTimelineEntry[] {
  const entries: DocumentTimelineEntry[] = [];

  if (document.archivedAt) {
    entries.push({
      id: "archived",
      action: "archived",
      description: "تمت أرشفة الوثيقة.",
      createdAt: document.archivedAt,
      userName: "مدير المؤسسة",
    });
  }

  if (document.publishedAt) {
    entries.push({
      id: "published",
      action: "published",
      description: "تم نشر الوثيقة.",
      createdAt: document.publishedAt,
      userName: "مدير المؤسسة",
    });
  }

  if (document.reviewedAt) {
    entries.push({
      id: "reviewed",
      action: normalizeStatus(document.status) === "Rejected" ? "rejected" : "approved",
      description:
        normalizeStatus(document.status) === "Rejected" ? "تم رفض الوثيقة." : "تم اعتماد الوثيقة.",
      createdAt: document.reviewedAt,
      userName: "مدير القسم",
    });
  }

  if (document.reviewStartedAt) {
    entries.push({
      id: "review-started",
      action: "review-started",
      description: "تم بدء مراجعة الوثيقة.",
      createdAt: document.reviewStartedAt,
      userName: "مدير القسم",
    });
  }

  if (document.submittedAt) {
    entries.push({
      id: "submitted",
      action: "submitted",
      description: "تم إرسال الوثيقة للمراجعة.",
      createdAt: document.submittedAt,
      userName: actorName,
    });
  }

  if (document.createdAt) {
    entries.push({
      id: "created",
      action: "created",
      description: "تم رفع الوثيقة وإضافتها إلى النظام.",
      createdAt: document.createdAt,
      userName: actorName,
    });
  }

  return entries;
}

function sortTimeline(entries: DocumentTimelineEntry[]): DocumentTimelineEntry[] {
  return [...entries].sort((first, second) => {
    const firstDate = first.createdAt ? new Date(first.createdAt).getTime() : 0;
    const secondDate = second.createdAt ? new Date(second.createdAt).getTime() : 0;
    return secondDate - firstDate;
  });
}

export const DocumentView = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const { t, language } = useLanguage();
  const { toast } = useToast();

  const currentBackendRole = getPrimaryBackendRole(user);
  const isRTL = language === "ar";
  const documentId = id ?? "demo-document";
  const previewUrlRef = useRef<string | null>(null);

  const [docData, setDocData] = useState<Document | null>(null);
  const [accessReview, setAccessReview] = useState<DocumentAccessReview | null>(null);
  const [timeline, setTimeline] = useState<DocumentTimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isMockMode, setIsMockMode] = useState(false);
  const [actionLoading, setActionLoading] = useState<WorkflowAction | null>(null);
  const [isExtractedTextOpen, setIsExtractedTextOpen] = useState(false);
  const [ocrTextState, setOcrTextState] = useState<"idle" | "loading" | "processing" | "ready" | "error">("idle");
  const [ocrText, setOcrText] = useState<DocumentOcrText | null>(null);
  const [ocrTextError, setOcrTextError] = useState<string | null>(null);
  const [ocrTextViewMode, setOcrTextViewMode] = useState<"normalized" | "raw">("normalized");
  const [isTransferOpen, setIsTransferOpen] = useState(false);
  const [transferTargetDepartmentId, setTransferTargetDepartmentId] = useState("");
  const [transferJustification, setTransferJustification] = useState("");
  const [transferDepartments, setTransferDepartments] = useState<Department[]>([]);
  const [transferDepartmentsLoading, setTransferDepartmentsLoading] = useState(false);

  const normalizedStatus = normalizeStatus(docData?.status);
  const normalizedPriority = normalizePriority(docData?.priority);
  const ownerName =
    (docData ? getDocumentOwnerName(docData) : null) ?? user?.name ?? t("غير معروف", "Unknown");

  const canEdit = useMemo(() => accessReview?.canEdit ?? canEditDocument(user, docData), [accessReview, user, docData]);
  const canDelete = useMemo(
    () => accessReview?.canDelete ?? canDeleteDocument(user, docData),
    [accessReview, user, docData],
  );
  const canTransfer = useMemo(() => canTransferDocument(user, docData), [user, docData]);
  const canPublish = useMemo(
    () => accessReview?.canPublish ?? canPublishDocument(user, docData),
    [accessReview, user, docData],
  );
  const canArchive = useMemo(
    () => accessReview?.canArchive ?? canArchiveDocument(user, docData),
    [accessReview, user, docData],
  );

  const canSubmit =
    accessReview?.canSubmit ??
    (currentBackendRole === "Employee" &&
      docData?.userId === user?.id &&
      (normalizedStatus === "Draft" || normalizedStatus === "Rejected"));

  const canStartReview = accessReview?.canStartReview ?? (currentBackendRole === "Manager" && normalizedStatus === "Submitted");
  const canApprove = accessReview?.canApprove ?? false;
  const canReject = accessReview?.canReject ?? false;

  const extractedText = useMemo(() => {
    if (!docData) {
      return "";
    }

    if (docData.content && docData.content.trim()) {
      return docData.content;
    }

    if (docData.metadata?.rawExtractionJson && docData.metadata.rawExtractionJson.trim()) {
      return docData.metadata.rawExtractionJson;
    }

    return [
      docData.title ?? "",
      "",
      docData.metadata?.description ?? "",
      "",
      ...(docData.metadata?.insights ?? []),
    ]
      .filter(Boolean)
      .join("\n");
  }, [docData]);

  const loadOcrText = useCallback(
    async (docId: string): Promise<"processing" | "ready" | "error"> => {
      if (!token) return "error";

      setOcrTextState("loading");
      setOcrTextError(null);

      try {
        const res = await getDocumentOcrTextRequest(docId);

        if (isOcrProcessingResponse(res)) {
          setOcrTextState("processing");
          setOcrText(null);
          setOcrTextError(res.message ?? t("جاري معالجة OCR...", "OCR is still processing..."));
          return "processing";
        }

        const payload = coerceDocumentOcrText(res);
        if (!payload) {
          setOcrTextState("error");
          setOcrText(null);
          setOcrTextError(t("تعذر قراءة نص OCR من الاستجابة.", "Unable to parse OCR response."));
          return "error";
        }

        setOcrText(payload);
        setOcrTextState("ready");
        setOcrTextViewMode(payload.normalizedText.trim() ? "normalized" : "raw");
        return "ready";
      } catch (error) {
        setOcrTextState("error");
        setOcrText(null);
        setOcrTextError(getAxiosMessage(error) ?? t("فشل جلب نص OCR.", "Failed to fetch OCR text."));
        return "error";
      }
    },
    [t, token],
  );

  useEffect(() => {
    if (!isExtractedTextOpen) return;

    if (isMockMode || !id || id === "demo-document" || !token) {
      setOcrTextState("idle");
      setOcrText(null);
      setOcrTextError(null);
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const poll = async () => {
      if (cancelled) return;

      const outcome = await loadOcrText(id);
      if (cancelled) return;

      if (outcome === "processing") {
        timeoutId = window.setTimeout(() => {
          void poll();
        }, 3000);
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [id, isExtractedTextOpen, isMockMode, loadOcrText, token]);

  const setPreviewObjectUrl = useCallback((nextUrl: string | null) => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }

    previewUrlRef.current = nextUrl;
    setPreviewUrl(nextUrl);
  }, []);

  const applyMockDocument = useCallback(() => {
    const mockDocument = buildMockDocument(documentId, currentBackendRole, user);
    setDocData(mockDocument);
    setAccessReview(null);
    setTimeline(buildMockTimeline(mockDocument, user?.name ?? t("غير معروف", "Unknown")));
    setPreviewObjectUrl(null);
    setLoadError(null);
    setIsMockMode(true);
  }, [currentBackendRole, documentId, setPreviewObjectUrl, t, user]);

  const loadDocument = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setLoading(true);
      }

      setLoadError(null);

      try {
        if (!id || id === "demo-document" || !token) {
          applyMockDocument();
          return;
        }

        const [documentResponse, timelineResponse, accessResponse] = await Promise.all([
          getDocumentViewRequest(id),
          getDocumentTimelineRequest(id).catch(() => [] as DocumentTimelineEntry[]),
          getDocumentAccessRequest(id).catch(() => null as DocumentAccessReview | null),
        ]);

        setDocData(documentResponse);
        setTimeline(Array.isArray(timelineResponse) ? sortTimeline(timelineResponse) : []);
        setAccessReview(accessResponse);
        setIsMockMode(false);

        try {
          const fileBlob = await downloadDocumentRequest(id);
          const blobUrl = URL.createObjectURL(fileBlob);
          setPreviewObjectUrl(blobUrl);
        } catch (previewError) {
          console.error("Failed to load preview file:", previewError);
          setPreviewObjectUrl(null);
        }
      } catch (error) {
        const axiosError = error as AxiosError<unknown>;
        const hasBackendResponse = Boolean(axiosError?.response);

        if (!hasBackendResponse) {
          console.error("Falling back to mock document view:", error);
          applyMockDocument();
          return;
        }

        setDocData(null);
        setAccessReview(null);
        setTimeline([]);
        setPreviewObjectUrl(null);
        setIsMockMode(false);
        setLoadError(
          getAxiosMessage(error) ??
            t("تعذر تحميل بيانات الوثيقة حالياً.", "Unable to load the document details right now."),
        );
      } finally {
        if (!options?.silent) {
          setLoading(false);
        }
      }
    },
    [applyMockDocument, id, setPreviewObjectUrl, t, token],
  );

  useEffect(() => {
    void loadDocument();

    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, [loadDocument]);

  useEffect(() => {
    if (!isTransferOpen || isMockMode) {
      return;
    }

    const institutionId = (docData?.institutionId ?? user?.institutionId ?? "").trim();
    if (!institutionId) {
      setTransferDepartments([]);
      return;
    }

    let cancelled = false;

    const loadDepartments = async () => {
      setTransferDepartmentsLoading(true);
      try {
        const data = await getDepartmentsRequest(institutionId);
        const list = Array.isArray(data) ? data : [];

        if (!cancelled) {
          const currentDepartmentId = (docData?.departmentId ?? "").trim();
          setTransferDepartments(
            currentDepartmentId ? list.filter((dept) => dept.id !== currentDepartmentId) : list,
          );
        }
      } catch (error) {
        console.error("Failed to load departments for transfer:", error);
        if (!cancelled) setTransferDepartments([]);
      } finally {
        if (!cancelled) setTransferDepartmentsLoading(false);
      }
    };

    void loadDepartments();

    return () => {
      cancelled = true;
    };
  }, [docData?.departmentId, docData?.institutionId, isMockMode, isTransferOpen, user?.institutionId]);

  const visibleTimeline = useMemo(() => {
    if (timeline.length > 0) {
      return sortTimeline(timeline);
    }

    if (!docData) {
      return [];
    }

    return buildMockTimeline(docData, ownerName);
  }, [docData, ownerName, timeline]);

  const timelineEntries = useMemo<TimelineItem[]>(() => {
    const getTimelineTitle = (action: string | null | undefined, description: string | null | undefined) => {
      switch ((action ?? "").toLowerCase()) {
        case "created":
          return t("تم إنشاء الوثيقة", "Document created");
        case "submitted":
          return t("تم إرسال الوثيقة", "Document submitted");
        case "review-started":
        case "start-review":
          return t("بدأت المراجعة", "Review started");
        case "reviewed":
        case "approved":
          return t("تم اعتماد الوثيقة", "Document approved");
        case "rejected":
          return t("تم رفض الوثيقة", "Document rejected");
        case "published":
          return t("تم نشر الوثيقة", "Document published");
        case "archived":
          return t("تمت أرشفة الوثيقة", "Document archived");
        case "transferred":
          return t("تم نقل الوثيقة", "Document transferred");
        default:
          return description ?? t("تحديث على الوثيقة", "Document update");
      }
    };

    return visibleTimeline.map((entry, index) => ({
      id: entry.id ?? `${entry.action ?? "timeline"}-${entry.createdAt ?? "time"}-${index}`,
      title: getTimelineTitle(entry.action, entry.description),
      at: entry.createdAt,
      actor: entry.userName ?? t("غير معروف", "Unknown"),
      description: entry.description,
    }));
  }, [t, visibleTimeline]);

  const workflowButtons = useMemo<WorkflowButton[]>(() => {
    const buttons: WorkflowButton[] = [];

    if (canSubmit) {
      buttons.push({
        action: "submit",
        label: t("إرسال للمراجعة", "Submit for review"),
        icon: <Send className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />,
        tone: "primary",
      });
    }

    if (canStartReview) {
      buttons.push({
        action: "startReview",
        label: t("بدء المراجعة", "Start review"),
        icon: <Sparkles className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />,
        tone: "primary",
      });
    }

    if (canApprove) {
      buttons.push({
        action: "approve",
        label: t("اعتماد الوثيقة", "Approve document"),
        icon: <CheckCircle2 className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />,
        tone: "success",
      });
    }

    if (canReject) {
      buttons.push({
        action: "reject",
        label: t("رفض الوثيقة", "Reject document"),
        icon: <XCircle className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />,
        tone: "danger",
      });
    }

    if (canPublish) {
      buttons.push({
        action: "publish",
        label: t("نشر الوثيقة", "Publish document"),
        icon: <Sparkles className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />,
        tone: "primary",
      });
    }

    if (canArchive) {
      buttons.push({
        action: "archive",
        label: t("أرشفة الوثيقة", "Archive document"),
        icon: <Archive className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />,
        tone: "secondary",
      });
    }

    if (canTransfer) {
      buttons.push({
        action: "transfer",
        label: t("نقل الوثيقة", "Transfer document"),
        icon: <Share2 className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />,
        tone: "secondary",
      });
    }

    return buttons;
  }, [canApprove, canArchive, canPublish, canReject, canStartReview, canSubmit, canTransfer, isRTL, t]);

  const primaryAction = workflowButtons[0] ?? null;

  const formatDate = (value: string | null | undefined) => {
    if (!value) {
      return "-";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "-";
    }

    return date.toLocaleDateString(language === "ar" ? "ar-SA" : "en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getStatusLabel = (status: StatusLabel | null) => {
    switch (status) {
      case "Draft":
        return t("مسودة", "Draft");
      case "Processing":
        return t("قيد المعالجة", "Processing");
      case "Submitted":
        return t("مرسلة", "Submitted");
      case "UnderReview":
        return t("قيد المراجعة", "Under review");
      case "Approved":
        return t("موافق عليها", "Approved");
      case "Rejected":
        return t("مرفوضة", "Rejected");
      case "Published":
        return t("منشورة", "Published");
      case "Archived":
        return t("مؤرشفة", "Archived");
      default:
        return t("غير محددة", "Unknown");
    }
  };

  const getPriorityLabel = (priority: PriorityLabel | null) => {
    switch (priority) {
      case "Urgent":
        return t("عاجلة", "Urgent");
      case "Important":
        return t("مهمة", "Important");
      case "Normal":
        return t("عادية", "Normal");
      default:
        return t("غير محددة", "Unknown");
    }
  };

  const getStatusBadgeClass = (status: StatusLabel | null) => {
    switch (status) {
      case "Draft":
        return "border-slate-200 bg-slate-50 text-slate-700";
      case "Submitted":
        return "border-sky-200 bg-sky-50 text-sky-700";
      case "UnderReview":
        return "border-indigo-200 bg-indigo-50 text-indigo-700";
      case "Approved":
        return "border-emerald-200 bg-emerald-50 text-emerald-700";
      case "Published":
        return "border-primary/20 bg-primary/5 text-primary";
      case "Archived":
        return "border-border bg-muted/60 text-muted-foreground";
      case "Rejected":
        return "border-destructive/20 bg-destructive/10 text-destructive";
      default:
        return "border-amber-200 bg-amber-50 text-amber-700";
    }
  };

  const getPriorityBadgeClass = (priority: PriorityLabel | null) => {
    switch (priority) {
      case "Urgent":
        return "border-destructive/20 bg-destructive/10 text-destructive";
      case "Important":
        return "border-warning/20 bg-warning/10 text-warning";
      case "Normal":
        return "border-success/20 bg-success/10 text-success";
      default:
        return "border-border bg-muted/50 text-muted-foreground";
    }
  };

  const getWorkflowButtonClassName = (tone: WorkflowButton["tone"]) => {
    switch (tone) {
      case "success":
        return "border-success/20 bg-success/10 text-success hover:bg-success/15";
      case "danger":
        return "border-destructive/20 bg-destructive/5 text-destructive hover:bg-destructive/10";
      case "secondary":
        return "border-border/60 bg-muted/30 text-foreground hover:bg-muted/40";
      case "primary":
      default:
        return "gradient-primary text-primary-foreground shadow-[var(--shadow-elegant)] hover:-translate-y-0.5";
    }
  };

  const appendMockTimeline = useCallback(
    (action: WorkflowAction, description: string, actor?: string) => {
      const now = new Date().toISOString();

      setTimeline((current) => [
        {
          id: `${action}-${now}`,
          action:
            action === "startReview"
              ? "review-started"
              : action === "approve"
                ? "approved"
                : action === "reject"
                  ? "rejected"
                  : action === "transfer"
                    ? "transferred"
                    : action,
          description,
          createdAt: now,
          userName: actor ?? user?.name ?? t("غير معروف", "Unknown"),
        },
        ...current,
      ]);
    },
    [t, user?.name],
  );

  const performMockWorkflowAction = useCallback(
    async (action: WorkflowAction): Promise<boolean> => {
      if (!docData) {
        return false;
      }

      const now = new Date().toISOString();

      if (action === "submit") {
        setDocData((current) =>
          current ? { ...current, status: "Submitted", submittedAt: now, updatedAt: now } : current,
        );
        appendMockTimeline(action, t("تم إرسال الوثيقة للمراجعة.", "Document submitted for review."));
        return true;
      }

      if (action === "startReview") {
        setDocData((current) =>
          current ? { ...current, status: "UnderReview", reviewStartedAt: now, updatedAt: now } : current,
        );
        appendMockTimeline(action, t("تم بدء مراجعة الوثيقة.", "Document review started."));
        return true;
      }

      if (action === "approve") {
        setDocData((current) =>
          current
            ? { ...current, status: "Approved", reviewedAt: now, rejectionReason: null, updatedAt: now }
            : current,
        );
        appendMockTimeline(action, t("تم اعتماد الوثيقة.", "Document approved."));
        return true;
      }

      if (action === "reject") {
        const comment = window.prompt(
          t("أدخل سبب الرفض", "Enter the rejection reason"),
          t("تحتاج الوثيقة إلى استكمال بعض المتطلبات.", "The document still needs a few adjustments."),
        );

        if (comment === null) {
          return false;
        }

        if (!comment.trim()) {
          throw new Error(t("يجب إدخال سبب الرفض.", "A rejection reason is required."));
        }

        setDocData((current) =>
          current
            ? { ...current, status: "Rejected", reviewedAt: now, rejectionReason: comment.trim(), updatedAt: now }
            : current,
        );
        appendMockTimeline(action, comment.trim());
        return true;
      }

      if (action === "publish") {
        setDocData((current) =>
          current ? { ...current, status: "Published", publishedAt: now, updatedAt: now } : current,
        );
        appendMockTimeline(action, t("تم نشر الوثيقة.", "Document published."));
        return true;
      }

      if (action === "archive") {
        setDocData((current) =>
          current ? { ...current, status: "Archived", archivedAt: now, updatedAt: now } : current,
        );
        appendMockTimeline(action, t("تمت أرشفة الوثيقة.", "Document archived."));
        return true;
      }

      const targetDepartmentId = window.prompt(
        t("أدخل معرف القسم المستهدف", "Enter the target department id"),
        docData.departmentId ?? "",
      );

      if (targetDepartmentId === null) {
        return false;
      }

      if (!targetDepartmentId.trim()) {
        throw new Error(t("يجب تحديد القسم المستهدف.", "A target department is required."));
      }

      const justification = window.prompt(
        t("أدخل مبرر النقل", "Enter the transfer justification"),
        t("تحويل الوثيقة إلى الجهة المختصة.", "Transfer the document to the responsible department."),
      );

      if (justification === null) {
        return false;
      }

      if (!justification.trim()) {
        throw new Error(t("يجب إدخال مبرر النقل.", "A transfer justification is required."));
      }

      setDocData((current) =>
        current
          ? {
              ...current,
              departmentId: targetDepartmentId.trim(),
              department: targetDepartmentId.trim(),
              updatedAt: now,
              metadata: {
                ...(current.metadata ?? {}),
                departmentId: targetDepartmentId.trim(),
                department: targetDepartmentId.trim(),
              },
            }
          : current,
      );
      appendMockTimeline(action, justification.trim());
      return true;
    },
    [appendMockTimeline, docData, t],
  );

  const getWorkflowSuccessMessage = (action: WorkflowAction) => {
    switch (action) {
      case "submit":
        return t("تم إرسال الوثيقة للمراجعة بنجاح.", "Document submitted for review successfully.");
      case "startReview":
        return t("تم بدء مراجعة الوثيقة بنجاح.", "Document review started successfully.");
      case "approve":
        return t("تم اعتماد الوثيقة بنجاح.", "Document approved successfully.");
      case "reject":
        return t("تم رفض الوثيقة بنجاح.", "Document rejected successfully.");
      case "publish":
        return t("تم نشر الوثيقة بنجاح.", "Document published successfully.");
      case "archive":
        return t("تمت أرشفة الوثيقة بنجاح.", "Document archived successfully.");
      case "transfer":
        return t("تم نقل الوثيقة بنجاح.", "Document transferred successfully.");
      default:
        return t("تم تنفيذ الإجراء بنجاح.", "Action completed successfully.");
    }
  };

  const getWorkflowErrorTitle = (action: WorkflowAction) => {
    switch (action) {
      case "submit":
        return t("فشل إرسال الوثيقة", "Failed to submit document");
      case "startReview":
        return t("فشل بدء المراجعة", "Failed to start review");
      case "approve":
        return t("فشل اعتماد الوثيقة", "Failed to approve document");
      case "reject":
        return t("فشل رفض الوثيقة", "Failed to reject document");
      case "publish":
        return t("فشل نشر الوثيقة", "Failed to publish document");
      case "archive":
        return t("فشل أرشفة الوثيقة", "Failed to archive document");
      case "transfer":
        return t("فشل نقل الوثيقة", "Failed to transfer document");
      default:
        return t("فشل تنفيذ الإجراء", "Failed to complete action");
    }
  };

  const handleWorkflowAction = useCallback(
    async (action: WorkflowAction) => {
      if (!docData) {
        return;
      }

      if (!isMockMode && !id) {
        return;
      }

      if (action === "transfer") {
        setTransferTargetDepartmentId("");
        setTransferJustification("");
        setIsTransferOpen(true);
        return;
      }

      setActionLoading(action);

      try {
        let didExecute = true;

        if (isMockMode) {
          didExecute = await performMockWorkflowAction(action);
        } else {
          if (action === "submit") {
            await submitDocumentRequest(id!);
          } else if (action === "startReview") {
            await startReviewRequest(id!);
          } else if (action === "approve") {
            const comment = window.prompt(
              t("أدخل ملاحظة الاعتماد (اختياري)", "Add approval note (optional)"),
              "",
            );
            const payload: ReviewDecisionDto | undefined =
              comment && comment.trim() ? { comment: comment.trim() } : undefined;
            await approveDocumentRequest(id!, payload);
          } else if (action === "reject") {
            const comment = window.prompt(
              t("أدخل سبب الرفض", "Enter the rejection reason"),
              "",
            );

            if (comment === null) {
              return;
            }

            if (!comment.trim()) {
              throw new Error(t("يجب إدخال سبب الرفض.", "A rejection reason is required."));
            }

            await rejectDocumentRequest(id!, { comment: comment.trim() });
          } else if (action === "publish") {
            await publishDocumentRequest(id!);
          } else if (action === "archive") {
            await archiveDocumentRequest(id!);
          } else if (action === "transfer") {
            const targetDepartmentId = window.prompt(
              t("أدخل معرف القسم المستهدف", "Enter the target department id"),
              docData.departmentId ?? "",
            );

            if (targetDepartmentId === null) {
              return;
            }

            if (!targetDepartmentId.trim()) {
              throw new Error(t("يجب تحديد القسم المستهدف.", "A target department is required."));
            }

            const justification = window.prompt(
              t("أدخل مبرر النقل", "Enter the transfer justification"),
              "",
            );

            if (justification === null) {
              return;
            }

            if (!justification.trim()) {
              throw new Error(t("يجب إدخال مبرر النقل.", "A transfer justification is required."));
            }

            const payload: TransferDocumentDto = {
              targetDepartmentId: targetDepartmentId.trim(),
              justification: justification.trim(),
            };

            await transferDocumentRequest(id!, payload);
          }

          await loadDocument({ silent: true });
        }

        if (!didExecute) {
          return;
        }

        toast({
          title: isMockMode ? t("وضع معاينة", "Preview mode") : t("تم بنجاح", "Completed"),
          description: getWorkflowSuccessMessage(action),
        });
      } catch (error) {
        toast({
          variant: "destructive",
          title: getWorkflowErrorTitle(action),
          description:
            getAxiosMessage(error) ??
            (error instanceof Error
              ? error.message
              : t("تعذر تنفيذ الإجراء حالياً.", "Unable to complete the action right now.")),
        });
      } finally {
        setActionLoading(null);
      }
    },
    [docData, id, isMockMode, loadDocument, performMockWorkflowAction, t, toast],
  );

  const handleConfirmTransfer = useCallback(async () => {
    if (!docData) {
      return;
    }

    if (!isMockMode && !id) {
      return;
    }

    const targetDepartmentId = transferTargetDepartmentId.trim();
    const justification = transferJustification.trim();

    if (!targetDepartmentId) {
      toast({
        variant: "destructive",
        title: t("القسم المستهدف مطلوب", "Target department is required"),
        description: t("يرجى اختيار القسم الذي سيتم نقل الوثيقة إليه.", "Please choose the department to transfer to."),
      });
      return;
    }

    if (!justification) {
      toast({
        variant: "destructive",
        title: t("مبرر النقل مطلوب", "Transfer justification is required"),
        description: t("يرجى كتابة سبب النقل.", "Please provide a reason for the transfer."),
      });
      return;
    }

    setActionLoading("transfer");

    try {
      let didExecute = true;

      if (isMockMode) {
        didExecute = await performMockWorkflowAction("transfer");
      } else {
        const payload: TransferDocumentDto = {
          targetDepartmentId,
          justification,
        };

        await transferDocumentRequest(id!, payload);
        await loadDocument({ silent: true });
      }

      if (!didExecute) {
        return;
      }

      setIsTransferOpen(false);

      toast({
        title: isMockMode ? t("وضع معاينة", "Preview mode") : t("تم بنجاح", "Completed"),
        description: getWorkflowSuccessMessage("transfer"),
      });
    } catch (error) {
      toast({
        variant: "destructive",
        title: getWorkflowErrorTitle("transfer"),
        description:
          getAxiosMessage(error) ??
          (error instanceof Error
            ? error.message
            : t("تعذر تنفيذ الإجراء حالياً.", "Unable to complete the action right now.")),
      });
    } finally {
      setActionLoading(null);
    }
  }, [
    docData,
    id,
    isMockMode,
    loadDocument,
    performMockWorkflowAction,
    t,
    toast,
    transferJustification,
    transferTargetDepartmentId,
  ]);

  const downloadBlob = (blob: Blob, fileName: string) => {
    const blobUrl = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = fileName;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(blobUrl);
  };

  const handleDownload = async () => {
    if (!docData) {
      return;
    }

    if (isMockMode) {
      const mockContent = [
        docData.title ?? "",
        docData.metadata?.referenceNumber ?? "",
        docData.metadata?.description ?? "",
      ].join("\n");

      downloadBlob(
        new Blob([mockContent], { type: "text/plain;charset=utf-8" }),
        `${docData.fileName ?? "document"}.txt`,
      );
      return;
    }

    if (!id) {
      return;
    }

    try {
      const blob = await downloadDocumentRequest(id);
      downloadBlob(blob, docData.fileName ?? "document");
    } catch (error) {
      toast({
        variant: "destructive",
        title: t("فشل تحميل الوثيقة", "Failed to download document"),
        description:
          getAxiosMessage(error) ??
          t("تعذر تحميل الوثيقة حالياً.", "Unable to download the document right now."),
      });
    }
  };

  const handleDelete = async () => {
    if (!docData) {
      return;
    }

    const confirmed = window.confirm(
      t(
        `هل أنت متأكد من حذف الوثيقة ${docData.title ?? ""}؟`,
        `Are you sure you want to delete ${docData.title ?? "this document"}?`,
      ),
    );

    if (!confirmed) {
      return;
    }

    if (isMockMode) {
      toast({
        title: t("وضع معاينة", "Preview mode"),
        description: t("تمت محاكاة حذف الوثيقة.", "Delete action simulated successfully."),
      });
      navigate("/documents");
      return;
    }

    if (!id) {
      return;
    }

    try {
      await deleteDocumentRequest(id);
      navigate("/documents");
    } catch (error) {
      toast({
        variant: "destructive",
        title: t("فشل حذف الوثيقة", "Failed to delete document"),
        description:
          getAxiosMessage(error) ??
          t("تعذر حذف الوثيقة حالياً.", "Unable to delete the document right now."),
      });
    }
  };

  if (loading && !docData) {
    return <p className="p-6 text-muted-foreground">{t("جارٍ تحميل الوثيقة...", "Loading document...")}</p>;
  }

  if (!docData) {
    return (
      <div className="p-6">
        <Card className="border-destructive/15 bg-destructive/5">
          <CardContent className="flex items-start gap-3 p-5">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-destructive" />
            <div>
              <p className="font-medium text-destructive">
                {t("تعذر العثور على الوثيقة.", "Unable to find the document.")}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {loadError ?? t("تحقق من الرابط أو أعد المحاولة لاحقاً.", "Check the link or try again later.")}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="animate-fade-in p-4 sm:p-6" style={{ direction: isRTL ? "rtl" : "ltr" }}>
      <Button variant="ghost" onClick={() => navigate(-1)} className="mb-4">
        <ArrowRight className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
        {t("العودة", "Back")}
      </Button>

      <Card className="animate-slide-up relative mb-6 overflow-hidden border-border/60 shadow-[var(--shadow-card)]">
        <div className="pointer-events-none absolute -right-14 top-0 h-40 w-40 rounded-full bg-primary/5 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-0 h-32 w-32 rounded-full bg-secondary/10 blur-3xl" />
        <CardContent className="p-5 sm:p-6">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                {isMockMode && (
                  <Badge variant="outline" className="border-secondary/30 bg-secondary/10 text-foreground">
                    {t("معاينة مؤقتة", "Temporary preview")}
                  </Badge>
                )}

                <Badge variant="outline" className={cn("font-medium", getStatusBadgeClass(normalizedStatus))}>
                  {getStatusLabel(normalizedStatus)}
                </Badge>

                <Badge variant="outline" className={cn("font-medium", getPriorityBadgeClass(normalizedPriority))}>
                  {getPriorityLabel(normalizedPriority)}
                </Badge>

                {docData.isSensitive && (
                  <Badge variant="outline" className="border-destructive/20 bg-destructive/10 text-destructive">
                    <ShieldAlert className={cn("h-3.5 w-3.5", isRTL ? "ml-1" : "mr-1")} />
                    {t("وثيقة حساسة", "Sensitive document")}
                  </Badge>
                )}
              </div>

              <h1 className="mb-2 break-words text-3xl font-cairo font-bold text-foreground">
                {docData.title ?? "-"}
              </h1>
              <p className="max-w-3xl text-muted-foreground">{docData.metadata?.description ?? "-"}</p>
            </div>

            <div className="flex flex-wrap gap-2 xl:justify-end">
              {primaryAction && (
                <Button
                  className={cn(
                    "transition-transform duration-300 hover:-translate-y-0.5",
                    getWorkflowButtonClassName(primaryAction.tone),
                  )}
                  onClick={() => void handleWorkflowAction(primaryAction.action)}
                  disabled={Boolean(actionLoading)}
                >
                  {primaryAction.icon}
                  {actionLoading === primaryAction.action
                    ? t("جارٍ التنفيذ...", "Processing...")
                    : primaryAction.label}
                </Button>
              )}

              <Button
                variant="outline"
                className="border-primary/20 bg-primary/5 text-primary transition-transform duration-300 hover:-translate-y-0.5 hover:bg-primary/10"
                onClick={handleDownload}
              >
                <Download className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                {t("تنزيل", "Download")}
              </Button>

              {canEdit && (
                <Button
                  variant="outline"
                  className="border-primary/20 bg-primary/5 text-primary transition-transform duration-300 hover:-translate-y-0.5 hover:bg-primary/10"
                  onClick={() => navigate(`/documents/${docData.id}/edit`)}
                >
                  <Edit className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                  {t("تعديل", "Edit")}
                </Button>
              )}

              {canDelete && (
                <Button
                  variant="outline"
                  className="border-destructive/20 bg-destructive/5 text-destructive transition-transform duration-300 hover:-translate-y-0.5 hover:bg-destructive/10"
                  onClick={handleDelete}
                >
                  <Trash2 className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                  {t("حذف", "Delete")}
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <SectionCard
            title={t("الحالة الحالية", "Current status")}
            action={
              <span className="text-xs text-muted-foreground">
                {t("آخر تحديث:", "Last update:")} {formatDate(docData.updatedAt)}
              </span>
            }
          >
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="outline" className={cn("font-medium", getStatusBadgeClass(normalizedStatus))}>
                {getStatusLabel(normalizedStatus)}
              </Badge>

              <Badge variant="outline" className={cn("font-medium", getPriorityBadgeClass(normalizedPriority))}>
                {getPriorityLabel(normalizedPriority)}
              </Badge>

              {docData.isSensitive && (
                <Badge variant="outline" className="border-destructive/20 bg-destructive/10 text-destructive">
                  <ShieldAlert className={cn("h-3.5 w-3.5", isRTL ? "ml-1" : "mr-1")} />
                  {t("وثيقة حساسة", "Sensitive document")}
                </Badge>
              )}
            </div>
          </SectionCard>

          <SectionCard
            icon={Eye}
            title={t("معاينة الملف", "File preview")}
            action={
              <Button
                variant="outline"
                className="border-secondary/30 bg-secondary/10 text-foreground transition-all duration-300 hover:-translate-y-0.5 hover:bg-secondary/15 hover:shadow-[var(--shadow-card)]"
                onClick={() => setIsExtractedTextOpen(true)}
              >
                <FileText className={cn("h-4 w-4", isRTL ? "ml-2" : "mr-2")} />
                {t("عرض النص المستخرج", "View extracted text")}
              </Button>
            }
          >
            <div className="group overflow-hidden rounded-[1.65rem] border border-border/60 bg-muted/20 shadow-[var(--shadow-card)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[var(--shadow-elegant)]">
              {previewUrl ? (
                docData.contentType?.startsWith("image/") ? (
                  <img
                    src={previewUrl}
                    alt={docData.fileName ?? docData.title ?? "document"}
                    className="h-[620px] w-full object-contain transition-transform duration-500 group-hover:scale-[1.01]"
                  />
                ) : (
                  <iframe
                    src={previewUrl}
                    className="h-[620px] w-full bg-white"
                    title={docData.title ?? "preview"}
                  />
                )
              ) : (
                <div className="flex min-h-[520px] items-center justify-center p-6 sm:p-8">
                  <div className="w-full max-w-xl rounded-[28px] border border-dashed border-border bg-muted/20 p-8 text-center shadow-[var(--shadow-card)]">
                    <FileText className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
                    <p className="text-sm font-medium text-foreground">{docData.fileName ?? "-"}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t(
                        "تعذر عرض المعاينة حالياً. يمكنك تنزيل الملف من الأعلى.",
                        "Preview unavailable right now. You can download the file from above.",
                      )}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </SectionCard>

          <SectionCard icon={Tag} title={t("بيانات الوثيقة", "Document details")}>
            <FieldGrid>
              <FieldItem label={t("الوصف", "Description")} value={docData.metadata?.description ?? "-"} />
              <FieldItem label={t("التصنيف العام", "Broad genre")} value={docData.metadata?.broadGenre ?? "-"} />
              <FieldItem label={t("التصنيف الخاص", "Specific genre")} value={docData.metadata?.specificGenre ?? "-"} />
              <FieldItem label={t("الجهة المُصدرة", "Issuing entity")} value={docData.metadata?.issuingEntity ?? "-"} />
              <FieldItem label={t("الرقم المرجعي", "Reference number")} value={docData.metadata?.referenceNumber ?? "-"} />
              <FieldItem label={t("تاريخ الوثيقة", "Document date")} value={formatDate(docData.metadata?.documentDate)} />
              <FieldItem label={t("تاريخ انتهاء الصلاحية", "Expiration date")} value={formatDate(docData.metadata?.expirationDate)} />
            </FieldGrid>

            <div className="mt-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
                <Tag className="h-4 w-4 text-muted-foreground" />
                {t("الوسوم", "Tags")}
              </div>
              <div className="flex flex-wrap gap-2">
                {(docData.metadata?.tags ?? []).length > 0 ? (
                  (docData.metadata?.tags ?? []).map((tag, index) => (
                    <Badge
                      key={`${tag}-${index}`}
                      variant="outline"
                      className="border-primary/15 bg-primary/5 text-primary transition-transform duration-300 hover:-translate-y-0.5"
                    >
                      {tag}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">-</span>
                )}
              </div>
            </div>
          </SectionCard>

          <DocumentSegmentationSection
            documentId={id ?? null}
            isMockMode={isMockMode}
            hasToken={Boolean(token)}
            canEdit={canEdit}
            documentFileName={docData.fileName}
            documentTitle={docData.title}
          />
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <SectionCard icon={Building2} title={t("الأطراف", "Participants")}>
            <FieldGrid columns="single">
              <FieldItem label={t("المالك", "Owner")} value={ownerName} />
              <FieldItem label={t("القسم", "Department")} value={docData.department ?? docData.metadata?.department ?? "-"} />
              <FieldItem label={t("نوع الوثيقة", "Document type")} value={docData.metadata?.documentType ?? "-"} />
            </FieldGrid>
          </SectionCard>

          <SectionCard icon={Clock} title={t("الجدول الزمني", "Timeline")}>
            <ol className="relative space-y-4 ps-5 before:absolute before:inset-y-1 before:start-2 before:w-px before:bg-border">
              {timelineEntries.length > 0 ? (
                timelineEntries.map((entry) => (
                  <li key={entry.id} className="relative">
                    <span className="absolute -start-[18px] top-1 grid h-3 w-3 place-items-center rounded-full bg-primary ring-4 ring-background" />
                    <p className="text-sm font-medium text-foreground">{entry.title}</p>
                    <p className="text-[11px] text-muted-foreground">{formatDate(entry.at)}</p>
                    <p className="text-xs text-muted-foreground">
                      {t("بواسطة", "By")} {entry.actor}
                    </p>
                    {entry.description && (
                      <p className="mt-1 text-xs leading-6 text-muted-foreground">{entry.description}</p>
                    )}
                  </li>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">{t("لا توجد أحداث حالياً.", "No events yet.")}</p>
              )}
            </ol>
          </SectionCard>

          <SectionCard icon={Sparkles} title={t("إجراءات سير العمل", "Workflow actions")}>
            <div className="flex flex-wrap gap-2">
              {workflowButtons.length > 0 ? (
                workflowButtons.map((button) => (
                  <Button
                    key={button.action}
                    variant={button.tone === "primary" ? "default" : "outline"}
                    className={cn(
                      "transition-transform duration-300 hover:-translate-y-0.5",
                      getWorkflowButtonClassName(button.tone),
                    )}
                    onClick={() => void handleWorkflowAction(button.action)}
                    disabled={Boolean(actionLoading)}
                  >
                    {button.icon}
                    {actionLoading === button.action
                      ? t("جارٍ التنفيذ...", "Processing...")
                      : button.label}
                  </Button>
                ))
              ) : (
                <div className="inline-flex items-center gap-2 rounded-xl border border-border/60 bg-muted/30 px-4 py-2 text-sm text-muted-foreground">
                  <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                  {t(
                    "لا يوجد إجراء مباشر متاح حالياً على هذه الوثيقة.",
                    "No direct action is currently available for this document.",
                  )}
                </div>
              )}
            </div>

            {docData.rejectionReason ? (
              <div className="mt-4 rounded-2xl border border-destructive/15 bg-destructive/5 p-3 text-sm text-destructive">
                <p className="mb-1 font-medium">{t("سبب الرفض", "Rejection reason")}</p>
                <p>{docData.rejectionReason}</p>
              </div>
            ) : null}
          </SectionCard>
        </aside>
      </div>

      <Dialog open={isTransferOpen} onOpenChange={setIsTransferOpen}>
        <DialogContent className="overflow-hidden sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-cairo text-2xl">{t("نقل الوثيقة", "Transfer document")}</DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              {t("اختر القسم المستهدف وأضف مبرر النقل.", "Choose the target department and add a justification.")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
              <p className="text-sm font-medium text-foreground">{t("القسم الحالي", "Current department")}</p>
              <p className="mt-1 text-sm text-muted-foreground">{docData.department ?? "-"}</p>
            </div>

            <div className="space-y-2">
              <Label>{t("القسم المستهدف", "Target department")}</Label>
              <Select value={transferTargetDepartmentId} onValueChange={setTransferTargetDepartmentId}>
                <SelectTrigger>
                  <SelectValue
                    placeholder={
                      transferDepartmentsLoading
                        ? t("جارٍ تحميل الأقسام...", "Loading departments...")
                        : t("اختر القسم", "Choose department")
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {(transferDepartments ?? []).map((dept) => (
                    <SelectItem key={dept.id} value={dept.id}>
                      {dept.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{t("مبرر النقل", "Justification")}</Label>
              <Textarea
                value={transferJustification}
                onChange={(event) => setTransferJustification(event.target.value)}
                placeholder={t("مثال: نقل الوثيقة إلى قسم آخر للمتابعة.", "Example: transfer to another department for follow-up.")}
                rows={4}
              />
            </div>

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline" onClick={() => setIsTransferOpen(false)} disabled={actionLoading === "transfer"}>
                {t("إلغاء", "Cancel")}
              </Button>
              <Button
                onClick={() => void handleConfirmTransfer()}
                disabled={actionLoading === "transfer"}
                className="gradient-primary text-primary-foreground"
              >
                {actionLoading === "transfer" ? t("جارٍ النقل...", "Transferring...") : t("نقل", "Transfer")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isExtractedTextOpen} onOpenChange={setIsExtractedTextOpen}>
        <DialogContent className="max-h-[85vh] overflow-hidden sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle className="font-cairo text-2xl">
              {t("النص المستخرج من الوثيقة", "Extracted document text")}
            </DialogTitle>
            <DialogDescription>
              {t(
                "هذا العرض مخصص لمراجعة النص المستخرج بسرعة بدون مغادرة صفحة الوثيقة.",
                "A quick view of the extracted text without leaving the document page.",
              )}
            </DialogDescription>

            {!isMockMode && ocrTextState === "ready" && ocrText && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {ocrText.provider && (
                  <Badge variant="outline" className="border-border/60 bg-muted/40 text-muted-foreground">
                    {ocrText.provider}
                  </Badge>
                )}
                {ocrText.language && (
                  <Badge variant="outline" className="border-border/60 bg-muted/40 text-muted-foreground">
                    {ocrText.language}
                  </Badge>
                )}
                {typeof ocrText.pages === "number" && (
                  <Badge variant="outline" className="border-border/60 bg-muted/40 text-muted-foreground">
                    {t("صفحات:", "Pages:")} {ocrText.pages}
                  </Badge>
                )}

                <div className={cn("flex items-center gap-2", isRTL ? "mr-auto" : "ml-auto")}>
                  <Button
                    type="button"
                    size="sm"
                    variant={ocrTextViewMode === "normalized" ? "default" : "outline"}
                    onClick={() => setOcrTextViewMode("normalized")}
                    disabled={!ocrText.normalizedText.trim()}
                    className={ocrTextViewMode === "normalized" ? "gradient-primary text-primary-foreground" : undefined}
                  >
                    {t("منسّق", "Normalized")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={ocrTextViewMode === "raw" ? "default" : "outline"}
                    onClick={() => setOcrTextViewMode("raw")}
                    disabled={!ocrText.rawText.trim()}
                    className={ocrTextViewMode === "raw" ? "gradient-primary text-primary-foreground" : undefined}
                  >
                    {t("خام", "Raw")}
                  </Button>
                </div>
              </div>
            )}
          </DialogHeader>

          <div className="overflow-hidden rounded-2xl border border-border/60 bg-muted/20 shadow-[var(--shadow-card)]">
            <div className="max-h-[60vh] overflow-y-auto p-5">
              <pre className="whitespace-pre-wrap font-tajawal text-sm leading-7 text-foreground">
                {isMockMode || !id || id === "demo-document" || !token
                  ? extractedText || t("لا يوجد نص مستخرج متاح حالياً.", "No extracted text is available right now.")
                  : ocrTextState === "loading"
                    ? t("جاري جلب نص OCR...", "Fetching OCR text...")
                    : ocrTextState === "processing"
                      ? ocrTextError ?? t("جاري معالجة OCR...", "OCR is still processing...")
                      : ocrTextState === "error"
                        ? ocrTextError ?? t("تعذر جلب نص OCR.", "Unable to load OCR text.")
                        : ocrText
                          ? (ocrTextViewMode === "raw" ? ocrText.rawText : ocrText.normalizedText) ||
                            t("لا يوجد نص مستخرج متاح حالياً.", "No extracted text is available right now.")
                          : t("لا يوجد نص مستخرج متاح حالياً.", "No extracted text is available right now.")}
              </pre>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const SectionCard = ({
  title,
  icon: Icon,
  action,
  children,
}: {
  title: string;
  icon?: ComponentType<{ className?: string }>;
  action?: ReactNode;
  children: ReactNode;
}) => (
  <Card className="animate-slide-up overflow-hidden border-border/60 bg-card shadow-[var(--shadow-card)]">
    <CardHeader className="pb-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
          <CardTitle>{title}</CardTitle>
        </div>
        {action}
      </div>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);

const FieldGrid = ({
  children,
  columns = "double",
}: {
  children: ReactNode;
  columns?: "single" | "double";
}) => (
  <div className={cn("grid gap-3", columns === "single" ? "grid-cols-1" : "sm:grid-cols-2")}>{children}</div>
);

const FieldItem = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-2xl border border-border/60 bg-muted/20 p-3">
    <p className="mb-1 text-xs text-muted-foreground">{label}</p>
    <p className="text-sm font-medium text-foreground">{value}</p>
  </div>
);

export default DocumentView;
