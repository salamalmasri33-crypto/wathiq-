import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '@/config/api';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import type { Document, DocumentPriority } from '@/types/document';
import { canEditDocument } from '@/lib/document-authorization';
import { getDepartmentsRequest } from '@/services/departments.service';
import { getDocumentAccessRequest } from '@/services/permissions.service';
import type { Department, DocumentAccessReview } from '@/types/platform';
import { GenreSelectors } from '@/components/GenreSelectors';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';

import { ArrowRight, Save, Upload, X } from 'lucide-react';

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
  if (typeof err === 'object' && err !== null && 'response' in err) {
    return (err as AxiosLikeError).response?.status;
  }
  return undefined;
}

/* =======================
   Types
======================= */
type MetadataForm = {
  description: string;
  broadGenre: string;
  specificGenre: string;
  departmentId: string;
  documentType: string;
  issuingEntity: string;
  referenceNumber: string;
  documentDate: string; // yyyy-mm-dd
  expirationDate: string; // yyyy-mm-dd
  tagsCsv: string; // tag1, tag2
};

type MetadataExtras = {
  insights: string[];
  hasSignature: boolean;
  signatures: string[];
  headers: string[];
  footers: string[];
  stamps: string[];
  rawExtractionJson: string;
};

type PriorityLabel = Exclude<DocumentPriority, number>;

const PRIORITY_BY_INDEX: Record<number, PriorityLabel> = {
  0: 'Normal',
  1: 'Important',
  2: 'Urgent',
};

function normalizePriority(priority: DocumentPriority | null | undefined): PriorityLabel {
  if (typeof priority === 'number') {
    return PRIORITY_BY_INDEX[priority] ?? 'Normal';
  }

  if (priority === 'Normal' || priority === 'Important' || priority === 'Urgent') {
    return priority;
  }

  return 'Normal';
}

/* =======================
   Component
======================= */
export const DocumentEdit = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const { language, t } = useLanguage();

  const [loading, setLoading] = useState(true);
  const [docData, setDocData] = useState<Document | null>(null);
  const [accessReview, setAccessReview] = useState<DocumentAccessReview | null>(null);
  const [accessLoading, setAccessLoading] = useState(true);

  const [title, setTitle] = useState('');
  const [newFile, setNewFile] = useState<File | null>(null);
  const [priority, setPriority] = useState<PriorityLabel>('Normal');
  const [isSensitive, setIsSensitive] = useState(false);

  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);

  const [meta, setMeta] = useState<MetadataForm>({
    description: '',
    broadGenre: '',
    specificGenre: '',
    departmentId: '',
    documentType: '',
    issuingEntity: '',
    referenceNumber: '',
    documentDate: '',
    expirationDate: '',
    tagsCsv: '',
  });

  const [metaExtras, setMetaExtras] = useState<MetadataExtras>({
    insights: [],
    hasSignature: false,
    signatures: [],
    headers: [],
    footers: [],
    stamps: [],
    rawExtractionJson: '',
  });

  /* =======================
     Permissions
  ======================= */
  const canEdit = useMemo(() => {
    // /documents/:id/view returns DocumentViewDto which does not contain the owner userId,
    // so client-side ownership checks can be wrong. Prefer the backend permission review.
    if (accessReview) {
      return accessReview.canEdit;
    }

    return canEditDocument(user, docData);
  }, [accessReview, user, docData]);

  /* =======================
     Fetch permissions (server-side truth)
  ======================= */
  useEffect(() => {
    if (!token || !id) return;

    let cancelled = false;

    const fetchAccess = async () => {
      setAccessLoading(true);
      try {
        const review = await getDocumentAccessRequest(id);
        if (!cancelled) setAccessReview(review);
      } catch (err) {
        console.error("Failed to fetch document access review:", err);
        if (!cancelled) setAccessReview(null);
      } finally {
        if (!cancelled) setAccessLoading(false);
      }
    };

    fetchAccess();

    return () => {
      cancelled = true;
    };
  }, [id, token]);

  /* =======================
     Fetch document
  ======================= */
  useEffect(() => {
    const fetchDocument = async () => {
      if (!token || !id) return;

      setLoading(true);
      try {
        const res = await api.get(`/documents/${id}/view`);

        const doc = res.data as Document;
        setDocData(doc);
        setTitle(doc.title ?? '');
        setPriority(normalizePriority(doc.priority));
        setIsSensitive(Boolean(doc.isSensitive));

        const m = doc.metadata;
        setMeta({
          description: m?.description ?? '',
          broadGenre: m?.broadGenre ?? '',
          specificGenre: m?.specificGenre ?? '',
          departmentId: m?.departmentId ?? doc.departmentId ?? '',
          documentType: m?.documentType ?? '',
          issuingEntity: m?.issuingEntity ?? '',
          referenceNumber: m?.referenceNumber ?? '',
          documentDate: m?.documentDate ? toYmd(m.documentDate) : '',
          expirationDate: m?.expirationDate ? toYmd(m.expirationDate) : '',
          tagsCsv: (m?.tags ?? []).join(', '),
        });

        // Preserve backend metadata fields that are not editable in this screen
        // to avoid wiping them when sending PUT /metadata.
        setMetaExtras({
          insights: Array.isArray(m?.insights) ? (m?.insights ?? []) : [],
          hasSignature: Boolean(m?.hasSignature),
          signatures: Array.isArray(m?.signatures) ? (m?.signatures ?? []) : [],
          headers: Array.isArray(m?.headers) ? (m?.headers ?? []) : [],
          footers: Array.isArray(m?.footers) ? (m?.footers ?? []) : [],
          stamps: Array.isArray(m?.stamps) ? (m?.stamps ?? []) : [],
          rawExtractionJson: m?.rawExtractionJson ?? '',
        });
      } catch (err: unknown) {
        console.error('❌ فشل جلب بيانات الوثيقة:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchDocument();
  }, [id, token]);

  /* =======================
     Fetch departments (to send departmentId to backend)
  ======================= */
  useEffect(() => {
    const institutionId = (docData?.institutionId ?? user?.institutionId ?? '').trim();
    if (!token || !institutionId) return;

    let cancelled = false;

    const loadDepartments = async () => {
      setDepartmentsLoading(true);
      try {
        const data = await getDepartmentsRequest(institutionId);
        if (!cancelled) setDepartments(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('Failed to fetch departments:', err);
        if (!cancelled) setDepartments([]);
      } finally {
        if (!cancelled) setDepartmentsLoading(false);
      }
    };

    loadDepartments();

    return () => {
      cancelled = true;
    };
  }, [docData?.institutionId, token, user?.institutionId]);

  /* =======================
     Save changes
  ======================= */
  const handleSave = async () => {
    if (!token || !id || !docData) return;

    if (!canEdit) {
      alert(t('لا تملك صلاحية تعديل هذه الوثيقة.', "You don't have permission to edit this document."));
      return;
    }

    setLoading(true);
    try {
      /* ---- 1) Update document (title / file) ---- */
      const form = new FormData();
      const trimmedTitle = title.trim();

      if (trimmedTitle && trimmedTitle !== docData.title) {
        form.append('Title', trimmedTitle);
      }
      if (newFile) {
        form.append('File', newFile);
      }

      const currentPriority = normalizePriority(docData.priority);
      if (priority !== currentPriority) {
        form.append('Priority', priority);
      }

      const currentSensitive = Boolean(docData.isSensitive);
      if (isSensitive !== currentSensitive) {
        form.append('IsSensitive', String(isSensitive));
      }

      if (form.has('Title') || form.has('File') || form.has('Priority') || form.has('IsSensitive')) {
        await api.put(`/documents/${id}`, form);
      }

      /* ---- 2) Update metadata ---- */
      const tags = meta.tagsCsv
        .split(',')
        .map((tt) => tt.trim())
        .filter(Boolean);

      const departmentIdTrimmed = meta.departmentId.trim();
      const metadataPayload = {
        description: meta.description || null,
        broadGenre: meta.broadGenre || null,
        specificGenre: meta.specificGenre || null,
        tags,
        departmentId: departmentIdTrimmed ? departmentIdTrimmed : null,
        documentType: meta.documentType || null,
        issuingEntity: meta.issuingEntity || null,
        referenceNumber: meta.referenceNumber || null,
        documentDate: meta.documentDate ? new Date(meta.documentDate).toISOString() : null,
        expirationDate: meta.expirationDate ? new Date(meta.expirationDate).toISOString() : null,
        insights: metaExtras.insights,
        hasSignature: Boolean(metaExtras.hasSignature),
        signatures: metaExtras.signatures,
        headers: metaExtras.headers,
        footers: metaExtras.footers,
        stamps: metaExtras.stamps,
        rawExtractionJson: metaExtras.rawExtractionJson || null,
      };

      await api.put(`/documents/${id}/metadata`, metadataPayload);

      navigate(`/documents/${id}`);
    } catch (err: unknown) {
      console.error('❌ فشل حفظ التعديلات:', err);
      const status = getHttpStatus(err);

      if (status === 403) alert(t('لا تملك صلاحية تعديل هذه الوثيقة.', "You don't have permission to edit this document."));
      else if (status === 409) alert(t('يوجد تعارض أو وثيقة مكررة.', 'There is a conflict or a duplicate document.'));
      else alert(t('فشل حفظ التعديلات.', 'Failed to save changes.'));
    } finally {
      setLoading(false);
    }
  };

  /* =======================
     Render guards
  ======================= */
  if (!token) return <p className="p-6">{t('يجب تسجيل الدخول.', 'You must be logged in.')}</p>;
  if (loading && !docData) return <p className="p-6">{t('جاري التحميل...', 'Loading...')}</p>;
  if (!docData) return <p className="p-6">{t('لم يتم العثور على الوثيقة', 'Document not found')}</p>;

  if (accessLoading) {
    return <p className="p-6">{t("جاري التحقق من الصلاحيات...", "Checking permissions...")}</p>;
  }

  if (!accessReview) {
    return <p className="p-6">{t("تعذر التحقق من الصلاحيات حالياً.", "Unable to verify permissions right now.")}</p>;
  }

  const iconGap = language === 'ar' ? 'ml-2' : 'mr-2';

  if (!canEdit) {
    return (
      <div className="p-6" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
        <Button variant="ghost" onClick={() => navigate(-1)} className="mb-4">
          <ArrowRight className={`w-4 h-4 ${iconGap}`} />
          {t('العودة', 'Back')}
        </Button>
        <Card>
          <CardHeader>
            <CardTitle>{t('غير مصرح', 'Unauthorized')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{t('لا تملك صلاحية تعديل هذه الوثيقة.', "You don't have permission to edit this document.")}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  /* =======================
     UI
  ======================= */
  return (
    <div className="p-6" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
      <div className="mb-6 flex justify-between gap-3 flex-wrap">
        <Button variant="ghost" onClick={() => navigate(-1)}>
          <ArrowRight className={`w-4 h-4 ${iconGap}`} />
          {t('العودة', 'Back')}
        </Button>

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(`/documents/${id}`)}>
            {t('إلغاء', 'Cancel')}
          </Button>
          <Button onClick={handleSave} disabled={loading}>
            <Save className={`w-4 h-4 ${iconGap}`} />
            {loading ? t('جاري الحفظ...', 'Saving...') : t('حفظ التعديلات', 'Save changes')}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Document */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('تعديل الوثيقة', 'Edit document')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>{t('العنوان', 'Title')}</Label>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('عنوان الوثيقة', 'Document title')} />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <Label>{t('الأولوية', 'Priority')}</Label>
                  <Select value={priority} onValueChange={(value) => setPriority(value as PriorityLabel)}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('اختر الأولوية', 'Choose priority')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Normal">{t('عادية', 'Normal')}</SelectItem>
                      <SelectItem value="Important">{t('مهمة', 'Important')}</SelectItem>
                      <SelectItem value="Urgent">{t('عاجلة', 'Urgent')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="is-sensitive">{t('حساسة', 'Sensitive')}</Label>
                  <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                    <span className="text-sm text-muted-foreground">
                      {isSensitive ? t('وثيقة حساسة', 'Sensitive document') : t('غير حساسة', 'Not sensitive')}
                    </span>
                    <Switch id="is-sensitive" checked={isSensitive} onCheckedChange={setIsSensitive} />
                  </div>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <Label>{t('استبدال الملف (اختياري)', 'Replace file (optional)')}</Label>
                <div className="flex items-center gap-2 flex-wrap">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => window.document.getElementById('fileInput')?.click()}
                  >
                    <Upload className={`w-4 h-4 ${iconGap}`} />
                    {t('اختيار ملف', 'Choose file')}
                  </Button>

                  {newFile ? (
                    <div className="flex items-center gap-2 text-sm">
                      <span className="break-all">{newFile.name}</span>
                      <Button type="button" variant="outline" onClick={() => setNewFile(null)}>
                        <X className={`w-4 h-4 ${iconGap}`} />
                        {t('إزالة', 'Remove')}
                      </Button>
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground break-all">
                      {t('الملف الحالي:', 'Current file:')} {docData.fileName ?? '—'}
                    </span>
                  )}
                </div>

                <input
                  id="fileInput"
                  type="file"
                  className="hidden"
                  onChange={(e) => setNewFile(e.target.files?.[0] ?? null)}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('تعديل البيانات الوصفية', 'Edit metadata')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>{t('الوصف', 'Description')}</Label>
                <Textarea
                  value={meta.description}
                  onChange={(e) => setMeta((prev) => ({ ...prev, description: e.target.value }))}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <GenreSelectors institutionId={docData?.institutionId ?? user?.institutionId ?? undefined} broadGenre={meta.broadGenre} specificGenre={meta.specificGenre} language={language} onChange={(genres) => setMeta((prev) => ({ ...prev, ...genres }))} />

                <div>
                  <Label>{t('القسم', 'Department')}</Label>
                  {departments.length ? (
                    <Select
                      value={meta.departmentId || undefined}
                      onValueChange={(value) => setMeta((prev) => ({ ...prev, departmentId: value }))}
                      disabled={departmentsLoading}
                    >
                      <SelectTrigger>
                        <SelectValue
                          placeholder={
                            departmentsLoading
                              ? t('جارٍ تحميل الأقسام...', 'Loading departments...')
                              : t('اختر القسم', 'Choose department')
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {departments.map((department) => (
                          <SelectItem key={department.id} value={department.id}>
                            {department.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      value={docData.department ?? ''}
                      disabled
                      placeholder={t('الأقسام غير متاحة', 'Departments unavailable')}
                    />
                  )}
                </div>

                <div>
                  <Label>{t('نوع الوثيقة', 'Document type')}</Label>
                  <Input
                    value={meta.documentType}
                    onChange={(e) => setMeta((prev) => ({ ...prev, documentType: e.target.value }))}
                  />
                </div>

                <div>
                  <Label>{t('الجهة المُصدرة', 'Issuing entity')}</Label>
                  <Input
                    value={meta.issuingEntity}
                    onChange={(e) => setMeta((prev) => ({ ...prev, issuingEntity: e.target.value }))}
                  />
                </div>

                <div>
                  <Label>{t('الرقم المرجعي', 'Reference number')}</Label>
                  <Input
                    value={meta.referenceNumber}
                    onChange={(e) => setMeta((prev) => ({ ...prev, referenceNumber: e.target.value }))}
                  />
                </div>

                <div>
                  <Label>{t('تاريخ الوثيقة', 'Document date')}</Label>
                  <Input
                    type="date"
                    value={meta.documentDate}
                    onChange={(e) => setMeta((prev) => ({ ...prev, documentDate: e.target.value }))}
                  />
                </div>

                <div>
                  <Label>{t('تاريخ الانتهاء', 'Expiration date')}</Label>
                  <Input
                    type="date"
                    value={meta.expirationDate}
                    onChange={(e) => setMeta((prev) => ({ ...prev, expirationDate: e.target.value }))}
                  />
                </div>
              </div>

              <div>
                <Label>{t('الوسوم (مفصولة بفواصل)', 'Tags (comma-separated)')}</Label>
                <Input
                  value={meta.tagsCsv}
                  onChange={(e) => setMeta((prev) => ({ ...prev, tagsCsv: e.target.value }))}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Info */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle>{t('معلومات', 'Info')}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-2">
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">ID:</span>
                <span className="font-medium break-all">{docData.id}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">{t('المالك:', 'Owner:')}</span>
                <span className="font-medium break-all">{docData.userId ?? '—'}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">{t('النوع:', 'Type:')}</span>
                <span className="font-medium break-all">{docData.contentType ?? '—'}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

/* =======================
   Helpers
======================= */
function toYmd(dateLike: string): string {
  const d = new Date(dateLike);
  if (Number.isNaN(d.getTime())) return '';
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}
