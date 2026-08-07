import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  Loader2,
  RotateCcw,
  ScissorsLineDashed,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import {
  getDocumentSegmentationRequest,
  retryDocumentSegmentationRequest,
  startDocumentSegmentationRequest,
} from "@/services/documents.service";
import type { DocumentSegmentation, SegmentationStatus } from "@/types/document";

type StatusLabel = "Pending" | "Processing" | "Completed" | "Failed";

const STATUS_BY_INDEX: Record<number, StatusLabel> = {
  0: "Pending",
  1: "Processing",
  2: "Completed",
  3: "Failed",
};

const POLL_INTERVAL_MS = 3000;

function normalizeSegmentationStatus(status: SegmentationStatus | null | undefined): StatusLabel | null {
  if (typeof status === "number") {
    return STATUS_BY_INDEX[status] ?? null;
  }

  return status ?? null;
}

function getAxiosMessage(error: unknown): string | null {
  if (!axios.isAxiosError(error)) {
    return null;
  }

  const data = error.response?.data;
  if (typeof data === "string") {
    return data;
  }

  if (typeof data === "object" && data !== null && "message" in data) {
    const message = (data as { message?: unknown }).message;
    return typeof message === "string" ? message : null;
  }

  return null;
}

function buildSegmentedText(segmentation: DocumentSegmentation): string {
  // Preserve exact sentence text and order; no trimming, no inserted
  // punctuation. Each sentence is written on its own line.
  return segmentation.sentences.map((sentence) => sentence.text).join("\n");
}

function buildDownloadFileName(
  segmentedFileName: string | null | undefined,
  documentTitle: string | null | undefined,
  documentId: string,
): string {
  const base = (segmentedFileName ?? documentTitle ?? documentId).trim();
  const withoutExtension = base.replace(/\.[^./\\]+$/, "").trim() || documentId;
  return `${withoutExtension}-segmented.txt`;
}

type LoadState = "idle" | "loading" | "ready" | "error";
type ActionState = "idle" | "starting" | "retrying";

type DocumentSegmentationSectionProps = {
  documentId: string | null | undefined;
  isMockMode: boolean;
  hasToken: boolean;
  canEdit: boolean;
  documentFileName?: string | null;
  documentTitle?: string | null;
};

export const DocumentSegmentationSection = ({
  documentId,
  isMockMode,
  hasToken,
  canEdit,
  documentFileName,
  documentTitle,
}: DocumentSegmentationSectionProps) => {
  const { t, language } = useLanguage();
  const { toast } = useToast();
  const isRTL = language === "ar";

  const [segmentation, setSegmentation] = useState<DocumentSegmentation | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<ActionState>("idle");

  const isActive = Boolean(documentId) && !isMockMode && hasToken;
  const activeDocumentId = isActive ? (documentId as string) : null;

  const describeError = useCallback(
    (error: unknown): string => {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;

        if (status === 401) {
          return t(
            "انتهت الجلسة أو التوكن غير صالح. يرجى تسجيل الدخول مجدداً.",
            "Your session has expired or is invalid. Please sign in again.",
          );
        }

        if (status === 403) {
          return t(
            "ليست لديك صلاحية للوصول إلى تقسيم النص لهذه الوثيقة.",
            "You don't have permission to access this document's segmentation.",
          );
        }

        if (!error.response) {
          return t(
            "تعذر الاتصال بالخادم. تحقق من الاتصال بالشبكة.",
            "Could not reach the server. Check your network connection.",
          );
        }

        return (
          getAxiosMessage(error) ??
          t("تعذر جلب حالة تقسيم النص حالياً.", "Unable to fetch the segmentation status right now.")
        );
      }

      return t("حدث خطأ غير متوقع.", "An unexpected error occurred.");
    },
    [t],
  );

  const fetchSegmentation = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!activeDocumentId) {
        setLoadState("idle");
        setSegmentation(null);
        return;
      }

      if (!options?.silent) {
        setLoadState("loading");
        setLoadError(null);
      }

      try {
        const result = await getDocumentSegmentationRequest(activeDocumentId);
        setSegmentation(result);
        setLoadState("ready");
        setLoadError(null);
      } catch (error) {
        setSegmentation(null);
        setLoadState("error");
        setLoadError(describeError(error));
      }
    },
    [activeDocumentId, describeError],
  );

  useEffect(() => {
    void fetchSegmentation();
  }, [fetchSegmentation]);

  const status = normalizeSegmentationStatus(segmentation?.status);

  // Poll while Processing only. Each tick schedules at most one further
  // fetch; polling stops as soon as the status leaves Processing, on error,
  // or when the component unmounts.
  useEffect(() => {
    if (!activeDocumentId || loadState !== "ready" || status !== "Processing") {
      return;
    }

    let cancelled = false;
    const timeoutId = window.setTimeout(async () => {
      if (cancelled) return;

      try {
        const result = await getDocumentSegmentationRequest(activeDocumentId);
        if (!cancelled) {
          setSegmentation(result);
        }
      } catch {
        // Keep the last known state; the next render's effect (or a manual
        // retry) will attempt again instead of surfacing a transient poll
        // failure as a hard error.
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [activeDocumentId, loadState, status]);

  const handleStart = useCallback(async () => {
    if (!activeDocumentId || actionState !== "idle") {
      return;
    }

    setActionState("starting");

    try {
      const result = await startDocumentSegmentationRequest(activeDocumentId);
      setSegmentation(result);
      setLoadState("ready");
      setLoadError(null);
      toast({
        title: t("بدأ تقسيم النص", "Segmentation started"),
        description: t("جارٍ تقسيم نص الوثيقة إلى جمل.", "The document text is being segmented into sentences."),
      });
    } catch (error) {
      toast({
        variant: "destructive",
        title: t("فشل بدء تقسيم النص", "Failed to start segmentation"),
        description: describeError(error),
      });
    } finally {
      setActionState("idle");
    }
  }, [activeDocumentId, actionState, describeError, t, toast]);

  const handleRetry = useCallback(async () => {
    if (!activeDocumentId || actionState !== "idle") {
      return;
    }

    setActionState("retrying");

    try {
      const result = await retryDocumentSegmentationRequest(activeDocumentId);
      setSegmentation(result);
      setLoadState("ready");
      setLoadError(null);
      toast({
        title: t("تمت إعادة المحاولة", "Retry submitted"),
        description: t("جارٍ إعادة تقسيم نص الوثيقة.", "The document is being re-segmented."),
      });
    } catch (error) {
      // Preserve the prior Failed UI; only notify the user.
      toast({
        variant: "destructive",
        title: t("فشلت إعادة المحاولة", "Retry failed"),
        description: describeError(error),
      });
    } finally {
      setActionState("idle");
    }
  }, [activeDocumentId, actionState, describeError, t, toast]);

  const handleCopy = useCallback(async () => {
    if (!segmentation || segmentation.sentences.length === 0) {
      return;
    }

    try {
      await navigator.clipboard.writeText(buildSegmentedText(segmentation));
      toast({
        title: t("تم النسخ", "Copied"),
        description: t("تم نسخ النص المقسّم إلى الحافظة.", "The segmented text was copied to the clipboard."),
      });
    } catch {
      toast({
        variant: "destructive",
        title: t("فشل النسخ", "Copy failed"),
        description: t("تعذر نسخ النص إلى الحافظة.", "Unable to copy the text to the clipboard."),
      });
    }
  }, [segmentation, t, toast]);

  const handleDownload = useCallback(() => {
    if (!segmentation || segmentation.sentences.length === 0 || !activeDocumentId) {
      return;
    }

    const blob = new Blob([buildSegmentedText(segmentation)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = buildDownloadFileName(documentFileName, documentTitle, activeDocumentId);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }, [activeDocumentId, documentFileName, documentTitle, segmentation]);

  const statusPresentation = (label: StatusLabel | null) => {
    switch (label) {
      case "Pending":
        return {
          text: t("بانتظار المعالجة", "Pending"),
          className: "border-slate-200 bg-slate-50 text-slate-700",
          icon: <Clock className="h-3.5 w-3.5" />,
        };
      case "Processing":
        return {
          text: t("جارٍ تقسيم النص", "Processing"),
          className: "border-amber-200 bg-amber-50 text-amber-700",
          icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
        };
      case "Completed":
        return {
          text: t("اكتمل تقسيم النص", "Completed"),
          className: "border-emerald-200 bg-emerald-50 text-emerald-700",
          icon: <CheckCircle2 className="h-3.5 w-3.5" />,
        };
      case "Failed":
        return {
          text: t("فشل تقسيم النص", "Failed"),
          className: "border-destructive/20 bg-destructive/10 text-destructive",
          icon: <AlertTriangle className="h-3.5 w-3.5" />,
        };
      default:
        return null;
    }
  };

  const presentation = statusPresentation(status);
  const marginIcon = isRTL ? "ml-2" : "mr-2";
  const marginIconSm = isRTL ? "ml-1" : "mr-1";

  const renderBody = () => {
    if (!documentId) {
      return null;
    }

    if (isMockMode || !hasToken) {
      return (
        <p className="text-sm text-muted-foreground">
          {t(
            "النص المقسّم غير متاح في وضع المعاينة المؤقتة.",
            "Segmented text isn't available in temporary preview mode.",
          )}
        </p>
      );
    }

    if (loadState === "loading" && !segmentation) {
      return (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("جارٍ التحقق من حالة تقسيم النص...", "Checking segmentation status...")}
        </div>
      );
    }

    if (loadState === "error") {
      return (
        <div className="space-y-3">
          <div className="flex items-start gap-3 rounded-2xl border border-destructive/15 bg-destructive/5 p-4">
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-destructive" />
            <p className="text-sm text-destructive">
              {loadError ?? t("تعذر جلب حالة تقسيم النص.", "Unable to fetch segmentation status.")}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void fetchSegmentation()}>
            <RotateCcw className={cn("h-4 w-4", marginIcon)} />
            {t("إعادة المحاولة", "Try again")}
          </Button>
        </div>
      );
    }

    // No segmentation record exists yet, or it's still Pending -- both allow
    // starting segmentation manually.
    if (!segmentation || status === "Pending") {
      return (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {t(
              "لا يوجد تقسيم نص لهذه الوثيقة بعد.",
              "No segmentation has been generated for this document yet.",
            )}
          </p>
          {canEdit ? (
            <Button
              size="sm"
              onClick={() => void handleStart()}
              disabled={actionState === "starting"}
              className="gradient-primary text-primary-foreground"
            >
              <ScissorsLineDashed className={cn("h-4 w-4", marginIcon)} />
              {actionState === "starting" ? t("جارٍ البدء...", "Starting...") : t("تقسيم النص", "Segment text")}
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">
              {t(
                "لا تملك صلاحية بدء تقسيم النص لهذه الوثيقة.",
                "You don't have permission to start segmentation for this document.",
              )}
            </p>
          )}
        </div>
      );
    }

    if (status === "Processing") {
      return (
        <div className="flex items-center gap-3 rounded-2xl border border-amber-200/60 bg-amber-50/60 p-4">
          <Loader2 className="h-5 w-5 flex-shrink-0 animate-spin text-amber-700" />
          <p className="text-sm text-amber-800">
            {t(
              "جارٍ تقسيم نص الوثيقة إلى جمل. سيتحدّث هذا القسم تلقائياً.",
              "The document text is being segmented into sentences. This section will update automatically.",
            )}
          </p>
        </div>
      );
    }

    if (status === "Failed") {
      return (
        <div className="space-y-3">
          <div className="rounded-2xl border border-destructive/15 bg-destructive/5 p-4">
            <p className="text-sm font-medium text-destructive">
              {segmentation.errorMessage ?? t("فشلت عملية تقسيم النص.", "Segmentation failed.")}
            </p>
            {segmentation.errorCode && (
              <p className="mt-1 font-mono text-xs text-destructive/70">{segmentation.errorCode}</p>
            )}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void handleRetry()}
            disabled={actionState === "retrying"}
            className="border-destructive/20 bg-destructive/5 text-destructive hover:bg-destructive/10"
          >
            <RotateCcw className={cn("h-4 w-4", marginIcon)} />
            {actionState === "retrying" ? t("جارٍ إعادة المحاولة...", "Retrying...") : t("إعادة المحاولة", "Retry")}
          </Button>
        </div>
      );
    }

    // Completed.
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-border/60 bg-muted/40 text-muted-foreground">
            {t("المسار:", "Track:")} {segmentation.track || "PA"}
          </Badge>
          {segmentation.pipelineId && (
            <Badge variant="outline" className="border-border/60 bg-muted/40 text-muted-foreground">
              PipelineId: {segmentation.pipelineId}
            </Badge>
          )}
          <Badge variant="outline" className="border-border/60 bg-muted/40 text-muted-foreground">
            {t("عدد الجمل:", "Sentences:")} {segmentation.sentences.length}
          </Badge>

          <div className={cn("flex items-center gap-2", isRTL ? "mr-auto" : "ml-auto")}>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => void handleCopy()}
              disabled={segmentation.sentences.length === 0}
            >
              <Copy className={cn("h-4 w-4", marginIconSm)} />
              {t("نسخ", "Copy")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleDownload}
              disabled={segmentation.sentences.length === 0}
            >
              <Download className={cn("h-4 w-4", marginIconSm)} />
              {t("تنزيل", "Download")}
            </Button>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-border/60 bg-muted/20 shadow-[var(--shadow-card)]">
          <div className="max-h-[420px] overflow-y-auto p-4">
            {segmentation.sentences.length > 0 ? (
              <ol className="space-y-2">
                {segmentation.sentences.map((sentence) => (
                  <li key={sentence.index} className="flex gap-3 rounded-xl bg-card/60 p-3">
                    <span className="mt-0.5 flex h-6 min-w-6 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                      {sentence.index + 1}
                    </span>
                    <p className="min-w-0 flex-1 whitespace-pre-wrap font-tajawal text-sm leading-7 text-foreground">
                      {sentence.text}
                    </p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t("لا توجد جمل ضمن هذا التقسيم.", "No sentences were produced by this segmentation.")}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (!documentId) {
    return null;
  }

  return (
    <Card className="animate-slide-up overflow-hidden border-border/60 bg-card shadow-[var(--shadow-card)]">
      <CardHeader className="pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <ScissorsLineDashed className="h-4 w-4 text-muted-foreground" />
            <CardTitle>{t("النص المقسّم", "Segmented text")}</CardTitle>
          </div>
          {presentation && (
            <Badge variant="outline" className={cn("flex items-center gap-1.5 font-medium", presentation.className)}>
              {presentation.icon}
              {presentation.text}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>{renderBody()}</CardContent>
    </Card>
  );
};

export default DocumentSegmentationSection;
