import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";

import { useToast } from "@/hooks/use-toast";
import { Upload, FileText, Sparkles, ArrowRight, Loader2 } from "lucide-react";
import api from "@/config/api";
import { getPrimaryBackendRole } from "@/lib/roles";
import { getDepartmentsRequest } from "@/services/departments.service";
import type { Department } from "@/types/platform";
import { GenreSelectors } from "@/components/GenreSelectors";

/* =======================
   Types
======================= */

type MetadataApiResponse = {
  description?: string;
  broadGenre?: string;
  specificGenre?: string;
  tags?: string[];
  department?: string;
  departmentId?: string;
  documentType?: string;
  expirationDate?: string; // ISO
  issuingEntity?: string;
  referenceNumber?: string;
  documentDate?: string; // ISO
  insights?: string[];
  hasSignature?: boolean;
  signatures?: string[];
  headers?: string[];
  footers?: string[];
  stamps?: string[];
  rawExtractionJson?: string;
  hasSavedMetadata?: boolean;
  hasExtractedText?: boolean;
  genreClassificationStatus?: string;
  genreClassificationMessage?: string;
};

type MetadataProcessingResponse = {
  status?: "processing";
  message?: string;
};

type UploadPriority = "Normal" | "Important" | "Urgent";

type MetadataFormSnapshot = {
  issuingEntity: string;
  referenceNumber: string;
  documentDate: string;
  keywords: string[];
  broadGenre: string;
  specificGenre: string;
  description: string;
  departmentId: string;
  documentType: string;
  expirationDate: string;
};

function isMetadataProcessingResponse(data: unknown): data is MetadataProcessingResponse {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  return obj.status === "processing";
}

function coerceMetadataApiResponse(data: unknown): MetadataApiResponse | null {
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;
  const base =
    typeof obj.metadata === "object" && obj.metadata !== null
      ? (obj.metadata as Record<string, unknown>)
      : obj;

  const out: MetadataApiResponse = {};
  if (typeof base.description === "string") out.description = base.description;
  if (typeof base.broadGenre === "string") out.broadGenre = base.broadGenre;
  if (typeof base.specificGenre === "string") out.specificGenre = base.specificGenre;
  if (Array.isArray(base.tags)) {
    const tags = base.tags.filter((t) => typeof t === "string") as string[];
    out.tags = tags;
  }
  if (typeof base.department === "string") out.department = base.department;
  if (typeof base.departmentId === "string") out.departmentId = base.departmentId;
  if (typeof base.documentType === "string") out.documentType = base.documentType;
  if (typeof base.expirationDate === "string") out.expirationDate = base.expirationDate;
  if (typeof base.issuingEntity === "string") out.issuingEntity = base.issuingEntity;
  if (typeof base.referenceNumber === "string") out.referenceNumber = base.referenceNumber;
  if (typeof base.documentDate === "string") out.documentDate = base.documentDate;

  if (Array.isArray(base.insights)) {
    out.insights = base.insights.filter((value) => typeof value === "string") as string[];
  }
  if (typeof base.hasSignature === "boolean") out.hasSignature = base.hasSignature;
  if (Array.isArray(base.signatures)) {
    out.signatures = base.signatures.filter((value) => typeof value === "string") as string[];
  }
  if (Array.isArray(base.headers)) {
    out.headers = base.headers.filter((value) => typeof value === "string") as string[];
  }
  if (Array.isArray(base.footers)) {
    out.footers = base.footers.filter((value) => typeof value === "string") as string[];
  }
  if (Array.isArray(base.stamps)) {
    out.stamps = base.stamps.filter((value) => typeof value === "string") as string[];
  }
  if (typeof base.rawExtractionJson === "string") out.rawExtractionJson = base.rawExtractionJson;
  if (typeof base.hasSavedMetadata === "boolean") out.hasSavedMetadata = base.hasSavedMetadata;
  if (typeof base.hasExtractedText === "boolean") out.hasExtractedText = base.hasExtractedText;
  if (typeof base.genreClassificationStatus === "string") out.genreClassificationStatus = base.genreClassificationStatus;
  if (typeof base.genreClassificationMessage === "string") out.genreClassificationMessage = base.genreClassificationMessage;

  return out;
}

function toDateInputValue(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().split("T")[0];
}

/* =======================
   Error helpers (no any)
======================= */
type AxiosLikeError = {
  response?: {
    status?: number;
    data?: unknown;
  };
};

function getHttpStatus(err: unknown): number | undefined {
  if (typeof err === "object" && err !== null && "response" in err) {
    return (err as AxiosLikeError).response?.status;
  }
  return undefined;
}

type DuplicateResponse = {
  message?: string;
  existingDocumentId?: string;
  existingTitle?: string;
};

function extractUploadedDocumentId(data: unknown): string | null {
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;
  const doc = obj.document;

  if (typeof doc === "object" && doc !== null) {
    const d = doc as Record<string, unknown>;
    if (typeof d.id === "string") return d.id;
  }
  if (typeof obj.id === "string") return obj.id;
  return null;
}

function extractDuplicateInfo(data: unknown): DuplicateResponse | null {
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;

  const message = typeof obj.message === "string" ? obj.message : undefined;
  const existingDocumentId =
    typeof obj.existingDocumentId === "string" ? obj.existingDocumentId : undefined;
  const existingTitle =
    typeof obj.existingTitle === "string" ? obj.existingTitle : undefined;

  if (!message && !existingDocumentId && !existingTitle) return null;
  return { message, existingDocumentId, existingTitle };
}

function getUploadedDocumentTitle(data: unknown): string | null {
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;
  const doc = obj.document;

  if (typeof doc === "object" && doc !== null) {
    const d = doc as Record<string, unknown>;
    if (typeof d.title === "string") return d.title;
  }

  return typeof obj.title === "string" ? obj.title : null;
}

function normalizeKeywordList(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function getMetadataSnapshot(formData: {
  issuingEntity: string;
  referenceNumber: string;
  documentDate: string;
  keywords: string;
  broadGenre: string;
  specificGenre: string;
  description: string;
  departmentId: string;
  documentType: string;
  expirationDate: string;
}): MetadataFormSnapshot {
  return {
    issuingEntity: formData.issuingEntity.trim(),
    referenceNumber: formData.referenceNumber.trim(),
    documentDate: formData.documentDate,
    keywords: normalizeKeywordList(formData.keywords),
    broadGenre: formData.broadGenre.trim(),
    specificGenre: formData.specificGenre.trim(),
    description: formData.description.trim(),
    departmentId: formData.departmentId.trim(),
    documentType: formData.documentType.trim(),
    expirationDate: formData.expirationDate,
  };
}

function areSnapshotsEqual(left: MetadataFormSnapshot | null, right: MetadataFormSnapshot): boolean {
  return left !== null && JSON.stringify(left) === JSON.stringify(right);
}

/* =======================
   Auth role helper (no any)
======================= */
function getUserRoleLower(user: unknown): string {
  if (typeof user !== "object" || user === null) return "";
  const u = user as Record<string, unknown>;
  const role = u.role;
  return typeof role === "string" ? role.toLowerCase() : "";
}

export const AddDocument = () => {
  // ✅ أخذنا user حتى نقرر وين نعمل redirect بعد الحفظ
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { language, t } = useLanguage();

  const primaryRole = getPrimaryBackendRole(user);
  const isManager = primaryRole === "Manager";
  const userDepartmentId = (user?.departmentId ?? "").trim();
  const isDepartmentLocked = isManager && Boolean(userDepartmentId);

  const [file, setFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  const [isUploadingAndProcessing, setIsUploadingAndProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [documentId, setDocumentId] = useState<string | null>(null);
  const [uploadedTitle, setUploadedTitle] = useState("");
  const [ocrMetadataSnapshot, setOcrMetadataSnapshot] = useState<MetadataFormSnapshot | null>(null);

  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);

  const [uploadOptions, setUploadOptions] = useState<{
    enableOcr: boolean;
    priority: UploadPriority;
    isSensitive: boolean;
    targetUserId: string;
  }>({
    enableOcr: true,
    priority: "Normal",
    isSensitive: false,
    targetUserId: "",
  });
  const [ocrEnabledForDocument, setOcrEnabledForDocument] = useState(true);

  const [isOcrProcessing, setIsOcrProcessing] = useState(false);
  const [isOcrReady, setIsOcrReady] = useState(false);

  const pollIntervalRef = useRef<number | null>(null);
  const pollStartedAtRef = useRef<number | null>(null);
  const completedProcessingDocumentRef = useRef<string | null>(null);

  const [formData, setFormData] = useState({
    title: "",
    issuingEntity: "",
    referenceNumber: "",
    documentDate: "",
    keywords: "",
    broadGenre: "",
    specificGenre: "",
    description: "",
    departmentId: "",
    documentType: "",
    expirationDate: "",
  });

  const [metadataPreview, setMetadataPreview] = useState<MetadataApiResponse | null>(null);
  const [metadataWasPersisted, setMetadataWasPersisted] = useState(false);

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      window.clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    pollStartedAtRef.current = null;
  };

  const pollForOcrMetadata = async (docId: string) => {
    if (!token || completedProcessingDocumentRef.current === docId) return;

    try {
      const res = await api.get(`/documents/${docId}/metadata-preview`, {
        headers: { Authorization: `Bearer ${token}` },
        validateStatus: (status) => status >= 200 && status < 500,
      });

      const startedAt = pollStartedAtRef.current ?? Date.now();
      pollStartedAtRef.current = startedAt;

      if (res.status === 202 || isMetadataProcessingResponse(res.data)) {
        setIsOcrProcessing(true);
        return;
      }

      if (res.status === 404) {
        setIsOcrProcessing(true);
        return;
      }

      if (res.status === 403) {
        stopPolling();
        setIsOcrProcessing(false);
        toast({
          title: t("خطأ", "Error"),
          description: t(
            "ليس لديك صلاحية لعرض بيانات هذه الوثيقة",
            "You don't have permission to view this document's metadata"
          ),
          variant: "destructive",
        });
        return;
      }

      if (res.status !== 200) {
        setIsOcrProcessing(true);
        return;
      }

      const meta = coerceMetadataApiResponse(res.data);
      if (!meta) {
        setIsOcrProcessing(true);
        return;
      }

      // metadata-preview can return 200 before OCR has produced any text.
      // Keep polling so classification runs when the extracted text becomes available.
      if (meta.hasExtractedText === false || meta.genreClassificationStatus === "NoText") {
        setIsOcrProcessing(true);
        setIsOcrReady(false);
        return;
      }

      // More than one polling request can already be in flight when the first
      // successful response stops the interval. Claim completion synchronously
      // so only one response updates the form and displays the success toast.
      if (completedProcessingDocumentRef.current === docId) return;
      completedProcessingDocumentRef.current = docId;

      setIsOcrProcessing(false);
      setIsOcrReady(true);
      stopPolling();
      setMetadataPreview(meta);
      setMetadataWasPersisted(meta.hasSavedMetadata === true);

      setFormData((prev) => {
        const nextFormData = {
          ...prev,
          broadGenre: meta.broadGenre?.trim() ?? prev.broadGenre,
          specificGenre: meta.specificGenre?.trim() ?? prev.specificGenre,
          keywords: meta.tags?.length ? meta.tags.join(", ") : prev.keywords,
          description: meta.description?.trim() ?? prev.description,
          departmentId: meta.departmentId?.trim() ? meta.departmentId.trim() : prev.departmentId,
          documentType: meta.documentType?.trim() ?? prev.documentType,
          expirationDate: meta.expirationDate ? toDateInputValue(meta.expirationDate) : prev.expirationDate,
          issuingEntity: meta.issuingEntity?.trim() ?? prev.issuingEntity,
          referenceNumber: meta.referenceNumber?.trim() ?? prev.referenceNumber,
          documentDate: meta.documentDate ? toDateInputValue(meta.documentDate) : prev.documentDate,
        };

        setOcrMetadataSnapshot(getMetadataSnapshot(nextFormData));
        return nextFormData;
      });

      toast({
        title: t("اكتملت المعالجة ✅", "Processing completed ✅"),
        description: t(
          "تم استخراج نتائج OCR وتعبئة الفورم تلقائياً. يمكنك الآن التعديل ثم الحفظ.",
          "OCR results were extracted and the form was filled automatically. You can now edit and save."
        ),
      });
    } catch {
      setIsOcrProcessing(true);
    }
  };

  useEffect(() => {
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!token) return;

    const loadDepartments = async () => {
      try {
        setDepartmentsLoading(true);
        const list = await getDepartmentsRequest(user?.institutionId ?? undefined);
        setDepartments(list);
      } catch {
        setDepartments([]);
      } finally {
        setDepartmentsLoading(false);
      }
    };

    void loadDepartments();
  }, [token, user?.institutionId]);

  useEffect(() => {
    if (!userDepartmentId) return;
    setFormData((prev) => (prev.departmentId ? prev : { ...prev, departmentId: userDepartmentId }));
  }, [userDepartmentId]);

  useEffect(() => {
    if (!documentId || !token) return;

    if (!ocrEnabledForDocument) {
      setIsOcrProcessing(false);
      setIsOcrReady(false);
      stopPolling();
      return;
    }

    setIsOcrProcessing(true);
    setIsOcrReady(false);

    pollStartedAtRef.current = Date.now();

    pollForOcrMetadata(documentId);

    stopPolling();
    pollIntervalRef.current = window.setInterval(() => {
      pollForOcrMetadata(documentId);
    }, 2000);

    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, token, ocrEnabledForDocument]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    if (selectedFile.size > 10 * 1024 * 1024) {
      toast({
        title: t("خطأ", "Error"),
        description: t("حجم الملف يجب أن يكون أقل من 10 ميجابايت", "File size must be less than 10MB"),
        variant: "destructive",
      });
      return;
    }

    setFile(selectedFile);
    setDocumentId(null);
    setUploadedTitle("");
    setOcrMetadataSnapshot(null);
    setIsOcrProcessing(false);
    setIsOcrReady(false);
    setMetadataPreview(null);
    setMetadataWasPersisted(false);
    completedProcessingDocumentRef.current = null;
    setOcrEnabledForDocument(uploadOptions.enableOcr);
    stopPolling();

    setIsExtracting(true);
    setTimeout(() => {
      const fileName = selectedFile.name.replace(/\.[^/.]+$/, "");
      setFormData((prev) => ({
        ...prev,
        title: prev.title?.trim() ? prev.title : fileName,
        documentDate: new Date().toISOString().split("T")[0],
      }));
      setIsExtracting(false);
    }, 500);
  };

  const handleUploadAndProcess = async () => {
    if (!token) {
      toast({
        title: t("غير مسجّل", "Not logged in"),
        description: t("يجب تسجيل الدخول أولاً", "You must login first"),
        variant: "destructive",
      });
      return;
    }

    if (!file) {
      toast({
        title: t("ملف غير موجود", "Missing file"),
        description: t("الرجاء رفع ملف", "Please upload a file"),
        variant: "destructive",
      });
      return;
    }

    if (documentId) {
      if (!ocrEnabledForDocument) {
        return;
      }

      toast({
        title: t("بدء معالجة OCR...", "Starting OCR..."),
        description: t(
          "جاري التحقق من نتائج OCR وسيتم تعبئة الفورم عند جاهزيتها.",
          "Checking OCR results. The form will be filled once ready."
        ),
      });

      setIsOcrProcessing(true);
      setIsOcrReady(false);

      pollStartedAtRef.current = Date.now();
      pollForOcrMetadata(documentId);

      stopPolling();
      pollIntervalRef.current = window.setInterval(() => {
        pollForOcrMetadata(documentId);
      }, 2000);

      return;
    }

    const opts = {
      enableOcr: uploadOptions.enableOcr,
      priority: uploadOptions.priority,
      isSensitive: uploadOptions.isSensitive,
      targetUserId: uploadOptions.targetUserId.trim(),
    };

    setIsUploadingAndProcessing(true);

    toast({
      title: opts.enableOcr ? t("رفع الوثيقة ومعالجتها...", "Uploading & processing...") : t("رفع الوثيقة...", "Uploading..."),
      description: t(
        opts.enableOcr
          ? "يتم الآن رفع الوثيقة وبدء OCR. الرجاء الانتظار..."
          : "يتم الآن رفع الوثيقة. الرجاء الانتظار...",
        opts.enableOcr
          ? "Uploading document and starting OCR. Please wait..."
          : "Uploading document. Please wait..."
      ),
    });

    try {
      const data = new FormData();
      data.append("File", file);
      data.append("Title", formData.title.trim());
      data.append("EnableOcr", String(opts.enableOcr));
      data.append("Priority", opts.priority);
      data.append("IsSensitive", String(opts.isSensitive));
      if (isManager && opts.targetUserId) {
        data.append("TargetUserId", opts.targetUserId);
      }

      const uploadResponse = await api.post("/documents/Add", data, {
        headers: { Authorization: `Bearer ${token}` },
        validateStatus: (status) => status >= 200 && status < 500,
      });

      if (uploadResponse.status === 409) {
        const dup = extractDuplicateInfo(uploadResponse.data);
        toast({
          title: t("ملف مكرر", "Duplicate file"),
          description: dup?.message || t("هذا الملف موجود مسبقاً", "This file already exists"),
          variant: "destructive",
        });
        return;
      }

      if (uploadResponse.status < 200 || uploadResponse.status >= 300) {
        const status = uploadResponse.status;
        const msg =
          status === 403
            ? t("ليس لديك صلاحية لرفع وثائق", "You don't have permission to upload documents")
            : t("فشل رفع الوثيقة", "Document upload failed");
        throw new Error(msg);
      }

      const newDocumentId = extractUploadedDocumentId(uploadResponse.data);
      if (!newDocumentId) {
        throw new Error(
          t("تم رفع الملف لكن لم يتم العثور على documentId في الرد", "File uploaded but documentId was not found in the response")
        );
      }

      setUploadedTitle(getUploadedDocumentTitle(uploadResponse.data)?.trim() || formData.title.trim());
      toast({
        title: t("تم رفع الوثيقة ✅", "Uploaded ✅"),
        description: t(
          opts.enableOcr
            ? "بدأت الآن معالجة OCR... سيتم تعبئة الفورم تلقائياً عند انتهاء المعالجة."
            : "يمكنك الآن تعبئة البيانات الوصفية ثم الحفظ.",
          opts.enableOcr
            ? "OCR processing started... the form will be filled automatically once it finishes."
            : "You can now fill in metadata and save."
        ),
      });

      setOcrEnabledForDocument(opts.enableOcr);
      setDocumentId(newDocumentId);
      setIsOcrProcessing(opts.enableOcr);
      setIsOcrReady(false);
      pollStartedAtRef.current = Date.now();
    } catch (err: unknown) {
      const status = getHttpStatus(err);
      const message =
        err instanceof Error
          ? err.message
          : status === 403
            ? t("ليس لديك صلاحية لتنفيذ العملية", "You don't have permission to perform this action")
            : t("فشل العملية، حاول مرة أخرى", "Operation failed, please try again");

      toast({
        title: t("خطأ", "Error"),
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsUploadingAndProcessing(false);
    }
  };

  const handleSaveMetadata = async () => {
    if (!token) {
      toast({
        title: t("غير مسجّل", "Not logged in"),
        description: t("يجب تسجيل الدخول أولاً", "You must login first"),
        variant: "destructive",
      });
      return;
    }

    if (!documentId) {
      toast({
        title: t("لا يوجد وثيقة", "No document"),
        description: t(
          uploadOptions.enableOcr
            ? "ارفع الوثيقة ومعالجتها أولاً ليتم تعبئة الفورم تلقائياً."
            : "ارفع الوثيقة أولاً ثم قم بحفظ البيانات.",
          uploadOptions.enableOcr
            ? "Upload & process the document first so the form fills automatically."
            : "Upload the document first, then save metadata."
        ),
        variant: "destructive",
      });
      return;
    }

    setIsSaving(true);

    try {
      const currentMetadataSnapshot = getMetadataSnapshot(formData);
      const titleChanged = formData.title.trim() !== uploadedTitle.trim();
      const metadataChanged = !areSnapshotsEqual(ocrMetadataSnapshot, currentMetadataSnapshot);
      const metadataNeedsPersisting = metadataPreview !== null && !metadataWasPersisted;
      const targetPath = primaryRole === "Employee" ? "/my-documents" : "/documents";

      if (!titleChanged && !metadataChanged && !metadataNeedsPersisting) {
        toast({
          title: t("تم الحفظ", "Saved"),
          description: t("الوثيقة محفوظة بالفعل، تم نقلك إلى صفحة الوثائق.", "The document is already saved. Redirecting to documents."),
        });
        navigate(targetPath);
        return;
      }

      const titleTrimmed = formData.title.trim();
      if (titleChanged && titleTrimmed) {
        const docForm = new FormData();
        docForm.append("Title", titleTrimmed);
        await api.put(`/documents/${documentId}`, docForm, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }

      const tags = currentMetadataSnapshot.keywords;

      const metadataPayload: Record<string, unknown> = {};
      if (formData.description.trim()) metadataPayload.description = formData.description.trim();
      if (formData.broadGenre.trim()) metadataPayload.broadGenre = formData.broadGenre.trim();
      if (formData.specificGenre.trim()) metadataPayload.specificGenre = formData.specificGenre.trim();
      if (tags.length) metadataPayload.tags = tags;
      if (formData.departmentId.trim()) metadataPayload.departmentId = formData.departmentId.trim();
      if (formData.documentType.trim()) metadataPayload.documentType = formData.documentType.trim();
      if (formData.issuingEntity.trim()) metadataPayload.issuingEntity = formData.issuingEntity.trim();
      if (formData.referenceNumber.trim()) metadataPayload.referenceNumber = formData.referenceNumber.trim();
      if (formData.documentDate) metadataPayload.documentDate = new Date(formData.documentDate).toISOString();

      if (formData.expirationDate) {
        metadataPayload.expirationDate = new Date(formData.expirationDate).toISOString();
      }

      if (metadataPreview) {
        if (Array.isArray(metadataPreview.insights)) metadataPayload.insights = metadataPreview.insights;
        if (typeof metadataPreview.hasSignature === "boolean") metadataPayload.hasSignature = metadataPreview.hasSignature;
        if (Array.isArray(metadataPreview.signatures)) metadataPayload.signatures = metadataPreview.signatures;
        if (Array.isArray(metadataPreview.headers)) metadataPayload.headers = metadataPreview.headers;
        if (Array.isArray(metadataPreview.footers)) metadataPayload.footers = metadataPreview.footers;
        if (Array.isArray(metadataPreview.stamps)) metadataPayload.stamps = metadataPreview.stamps;
        if (typeof metadataPreview.rawExtractionJson === "string" && metadataPreview.rawExtractionJson.trim()) {
          metadataPayload.rawExtractionJson = metadataPreview.rawExtractionJson;
        }
      }

      if (metadataChanged || metadataNeedsPersisting) {
        await api.put(`/documents/${documentId}/metadata`, metadataPayload, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setMetadataWasPersisted(true);
      }

      toast({
        title: t("تم الحفظ ✅", "Saved ✅"),
        description: t("تم حفظ البيانات الوصفية بنجاح", "Metadata saved successfully"),
      });

      navigate(targetPath);
    } catch (err: unknown) {
      const status = getHttpStatus(err);
      const targetPath = primaryRole === "Employee" ? "/my-documents" : "/documents";

      if (documentId && (status === 500 || status === 409)) {
        toast({
          title: t("تم حفظ الوثيقة", "Document saved"),
          description: t(
            "تم حفظ الوثيقة، وسيتم نقلك إلى صفحة الوثائق.",
            "The document was saved. Redirecting to documents."
          ),
        });
        navigate(targetPath);
        return;
      }

      const message =
        err instanceof Error
          ? err.message
          : status === 403
            ? t("ليس لديك صلاحية لتنفيذ العملية", "You don't have permission to perform this action")
            : t("فشل العملية، حاول مرة أخرى", "Operation failed, please try again");

      toast({
        title: t("خطأ", "Error"),
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const iconGapClass = language === "ar" ? "ml-2" : "mr-2";

  return (
    <div className="p-6 animate-fade-in" style={{ direction: language === "ar" ? "rtl" : "ltr" }}>
      <div className="mb-6">
        <Button variant="ghost" className="mb-3" onClick={() => navigate(-1)}>
          <ArrowRight className={`w-4 h-4 ${iconGapClass}`} />
          {t("عودة", "Back")}
        </Button>

        <h1 className="text-3xl font-cairo font-bold text-foreground mb-2">
          {t("رفع وثيقة جديدة", "Upload a new document")}
        </h1>
        <p className="text-muted-foreground">{t("أضف وثيقة جديدة إلى النظام", "Add a new document to the system")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="hover-lift">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="w-5 h-5 text-primary" />
              {t("رفع الملف", "Upload file")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary transition-colors">
                <input
                  type="file"
                  id="file-upload"
                  className="hidden"
                  accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                  onChange={handleFileChange}
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <FileText className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground mb-2">
                    {t("اسحب الملف هنا أو انقر للتحميل", "Drag file here or click to upload")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("PDF, DOC, DOCX, JPG, PNG (حتى 10MB)", "PDF, DOC, DOCX, JPG, PNG (up to 10MB)")}
                  </p>
                </label>
              </div>

              {file && (
                <div className="bg-muted/50 rounded-lg p-4 animate-scale-in">
                  <div className="flex items-center gap-3">
                    <FileText className="w-8 h-8 text-primary" />
                    <div className="flex-1">
                      <p className="font-medium">{file.name}</p>
                      <p className="text-sm text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  </div>
                </div>
              )}

              {file && (
                <div className="rounded-lg border bg-muted/30 p-4 animate-fade-in">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label>{t("الأولوية", "Priority")}</Label>
                      <Select
                        value={uploadOptions.priority}
                        onValueChange={(v) => setUploadOptions((prev) => ({ ...prev, priority: v as UploadPriority }))}
                        disabled={Boolean(documentId) || isUploadingAndProcessing || isSaving}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t("اختر الأولوية", "Select priority")} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Normal">{t("عادية", "Normal")}</SelectItem>
                          <SelectItem value="Important">{t("مهمة", "Important")}</SelectItem>
                          <SelectItem value="Urgent">{t("عاجلة", "Urgent")}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex items-center justify-between rounded-lg border bg-background/60 px-3 py-2">
                      <Label htmlFor="sensitive-toggle" className="text-sm font-medium">
                        {t("وثيقة حساسة", "Sensitive")}
                      </Label>
                      <div dir="ltr" className="flex items-center">
                        <Switch
                          id="sensitive-toggle"
                          checked={uploadOptions.isSensitive}
                          onCheckedChange={(v) => setUploadOptions((prev) => ({ ...prev, isSensitive: v }))}
                          disabled={Boolean(documentId) || isUploadingAndProcessing || isSaving}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between rounded-lg border bg-background/60 px-3 py-2">
                    <Label htmlFor="ocr-toggle" className="text-sm font-medium">
                      {t("تشغيل OCR", "Enable OCR")}
                    </Label>
                    <div dir="ltr" className="flex items-center">
                      <Switch
                        id="ocr-toggle"
                        checked={uploadOptions.enableOcr}
                        onCheckedChange={(v) => setUploadOptions((prev) => ({ ...prev, enableOcr: v }))}
                        disabled={Boolean(documentId) || isUploadingAndProcessing || isSaving}
                      />
                    </div>
                  </div>

                  {isManager && (
                    <div className="mt-3 space-y-2">
                      <Label htmlFor="target-user-id">{t("رفع نيابةً عن (UserId)", "Upload for (UserId)")}</Label>
                      <Input
                        id="target-user-id"
                        value={uploadOptions.targetUserId}
                        onChange={(e) => setUploadOptions((prev) => ({ ...prev, targetUserId: e.target.value }))}
                        placeholder={t("اختياري", "Optional")}
                        disabled={Boolean(documentId) || isUploadingAndProcessing || isSaving}
                        dir="ltr"
                      />
                    </div>
                  )}
                </div>
              )}

              <Button
                type="button"
                className="w-full gradient-hero"
                onClick={handleUploadAndProcess}
                disabled={!file || isUploadingAndProcessing || isSaving || (Boolean(documentId) && !ocrEnabledForDocument)}
              >
                {isUploadingAndProcessing || isOcrProcessing ? (
                  <Loader2 className={`w-4 h-4 animate-spin ${iconGapClass}`} />
                ) : (
                  <Upload className={`w-4 h-4 ${iconGapClass}`} />
                )}
                {documentId
                  ? ocrEnabledForDocument
                    ? isOcrProcessing
                      ? t("OCR قيد المعالجة...", "OCR processing...")
                      : t("إعادة جلب نتائج OCR", "Re-fetch OCR results")
                    : t("تم رفع الوثيقة", "Document uploaded")
                  : uploadOptions.enableOcr
                    ? t("رفع الوثيقة ومعالجتها", "Upload & Process")
                    : t("رفع الوثيقة", "Upload document")}
              </Button>

              {documentId && (
                <div className="text-sm text-muted-foreground">
                  {ocrEnabledForDocument
                    ? isOcrReady
                      ? t("✅ تم استخراج OCR وتعبئة الفورم.", "✅ OCR extracted and form filled.")
                      : t("⏳ جاري معالجة OCR... سيتم تعبئة الفورم تلقائياً.", "⏳ OCR processing... the form will be filled automatically.")
                    : t("✅ تم رفع الوثيقة.", "✅ Document uploaded.")}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="hover-lift">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-secondary" />
              {t("البيانات الوصفية", "Metadata")}
              {(isExtracting || isOcrProcessing) && (
                <span className="text-sm text-muted-foreground">
                  ({isOcrProcessing ? t("OCR...", "OCR...") : t("...", "...")})
                </span>
              )}
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-4">
              <div>
                <Label htmlFor="title">{t("عنوان الوثيقة *", "Document title *")}</Label>
                <Input id="title" value={formData.title} onChange={(e) => setFormData({ ...formData, title: e.target.value })} />
              </div>

              <div>
                <Label htmlFor="issuingEntity">{t("الجهة المُصدرة", "Issuing entity")}</Label>
                <Input
                  id="issuingEntity"
                  value={formData.issuingEntity}
                  onChange={(e) => setFormData({ ...formData, issuingEntity: e.target.value })}
                />
              </div>

              <div>
                <Label htmlFor="referenceNumber">{t("الرقم المرجعي", "Reference number")}</Label>
                <Input
                  id="referenceNumber"
                  value={formData.referenceNumber}
                  onChange={(e) => setFormData({ ...formData, referenceNumber: e.target.value })}
                  placeholder={t("مثال: WA-2026-0142", "Example: WA-2026-0142")}
                  dir="ltr"
                />
              </div>

              <div>
                <Label htmlFor="documentDate">{t("تاريخ الوثيقة", "Document date")}</Label>
                <Input
                  id="documentDate"
                  type="date"
                  value={formData.documentDate}
                  onChange={(e) => setFormData({ ...formData, documentDate: e.target.value })}
                />
              </div>

              <GenreSelectors institutionId={user?.institutionId ?? undefined} broadGenre={formData.broadGenre} specificGenre={formData.specificGenre} language={language} onChange={(genres) => setFormData({ ...formData, ...genres })} />

              <div>
                <Label htmlFor="keywords">{t("الكلمات المفتاحية", "Keywords")}</Label>
                <Input id="keywords" value={formData.keywords} onChange={(e) => setFormData({ ...formData, keywords: e.target.value })} />
              </div>

              <div>
                <Label htmlFor="description">{t("وصف الوثيقة", "Document description")}</Label>
                <Textarea id="description" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} rows={3} />
              </div>

              <div>
                <Label htmlFor="departmentId">{t("القسم", "Department")}</Label>
                <Select
                  value={formData.departmentId}
                  onValueChange={(value) => setFormData({ ...formData, departmentId: value })}
                  disabled={isDepartmentLocked || departmentsLoading || isSaving || isUploadingAndProcessing}
                >
                  <SelectTrigger id="departmentId">
                    <SelectValue
                      placeholder={
                        departmentsLoading
                          ? t("جاري تحميل الأقسام...", "Loading departments...")
                          : t("اختر القسم", "Select department")
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {(isDepartmentLocked
                      ? departments.filter((dept) => dept.id === userDepartmentId)
                      : departments
                    ).map((dept) => (
                      <SelectItem key={dept.id} value={dept.id}>
                        {dept.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="documentType">{t("نوع الوثيقة", "Document type")}</Label>
                <Input
                  id="documentType"
                  value={formData.documentType}
                  onChange={(e) => setFormData({ ...formData, documentType: e.target.value })}
                  placeholder={t("مثال: PDF أو Invoice أو Contract", "Example: PDF / Invoice / Contract")}
                />
              </div>

              <div>
                <Label htmlFor="expirationDate">{t("تاريخ الانتهاء", "Expiration date")}</Label>
                <Input
                  id="expirationDate"
                  type="date"
                  value={formData.expirationDate}
                  onChange={(e) => setFormData({ ...formData, expirationDate: e.target.value })}
                />
              </div>

              <div className="flex gap-3 pt-4">
                <Button
                  type="button"
                  className="flex-1 gradient-hero"
                  onClick={handleSaveMetadata}
                  disabled={!documentId || isSaving || isUploadingAndProcessing}
                >
                  {isSaving ? (
                    <Loader2 className={`w-4 h-4 animate-spin ${iconGapClass}`} />
                  ) : (
                    <Upload className={`w-4 h-4 ${iconGapClass}`} />
                  )}
                  {isSaving ? t("جاري الحفظ...", "Saving...") : t("حفظ البيانات", "Save metadata")}
                </Button>

                <Button type="button" variant="outline" onClick={() => navigate(-1)} disabled={isSaving || isUploadingAndProcessing}>
                  {t("إلغاء", "Cancel")}
                </Button>
              </div>

              {!documentId && (
                <div className="text-sm text-muted-foreground pt-2">
                  {t(
                    uploadOptions.enableOcr
                      ? "ارفع الملف ثم اضغط (رفع الوثيقة ومعالجتها) ليتم استخراج OCR وتعبئة الفورم تلقائياً."
                      : "ارفع الملف ثم اضغط (رفع الوثيقة) ثم احفظ البيانات.",
                    uploadOptions.enableOcr
                      ? "Upload the file then click (Upload & Process) to extract OCR and fill the form automatically."
                      : "Upload the file then click (Upload document), then save metadata."
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
