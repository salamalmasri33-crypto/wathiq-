import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { BarChart3, Download, FileText, TrendingUp } from 'lucide-react';
import api from '@/config/api';
import { hasAnyRole, REPORTS_ALLOWED_ROLES } from '@/lib/roles';
import {
  exportDepartmentExcelRequest,
  exportTypeExcelRequest,
  exportUserActivityExcelRequest,
  getDocumentsByDepartmentReportRequest,
  getDocumentsByTypeReportRequest,
  getTimeReportRequest,
  getUserActivityReportRequest,
} from '@/services/reports.service';

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  LineChart,
  Line,
  PieChart,
  Pie,
  Legend,
} from 'recharts';

/* =======================
   Types (no any)
======================= */
type DashboardTotals = {
  totalDocuments: number;
  totalUsers: number;
  todayUploads: number;
  monthlyUpdates: number;
};

type AuditLog = {
  timestamp: string;
  userId?: string | null;
  userName?: string | null;
  userEmail?: string | null;
  userRole?: string | null;
  action?: string | null;
  documentId?: string | null;
  description?: string | null;
};

type DocumentLite = {
  id: string;
  fileName?: string | null;
  contentType?: string | null;
  // ما رح نعتمد على metadata.documentType هون لأنك قلت نعتمد على endpoint يلي فيه contentType
};

type CountItem = { label: string; count: number };

type ReportType = 'documentsByDepartment' | 'documentsByType' | 'userActivity' | 'timeReport';
type DateRange = 'today' | 'week' | 'month' | 'year' | 'custom';

type ChartDatum = { name: string; value: number };

type UserActivityRow = {
  userId: string;
  uploads: number;
  updates: number;
  deletes: number;
  searches: number;
  downloads: number;
};

type TimeReportRow = {
  date: string;
  added: number;
  updated: number;
  searches: number;
};

/* =======================
   Helpers
======================= */
const enNumber = new Intl.NumberFormat('en-US');

const BAR_COLORS = [
  '#3b82f6', // blue
  '#22c55e', // green
  '#f59e0b', // amber
  '#a855f7', // purple
  '#ef4444', // red
  '#06b6d4', // cyan
  '#f97316', // orange
  '#14b8a6', // teal
  '#64748b', // slate
];

function formatNumber(n: number): string {
  return enNumber.format(n);
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null;
}

function parseTotals(data: unknown): DashboardTotals | null {
  if (!isRecord(data)) return null;

  const td = data.totalDocuments;
  const tu = data.totalUsers;
  const today = data.todayUploads;
  const monthly = data.monthlyUpdates;

  if (
    typeof td !== 'number' ||
    typeof tu !== 'number' ||
    typeof today !== 'number' ||
    typeof monthly !== 'number'
  ) {
    return null;
  }

  return { totalDocuments: td, totalUsers: tu, todayUploads: today, monthlyUpdates: monthly };
}

function parseAuditList(data: unknown): AuditLog[] {
  if (!Array.isArray(data)) return [];
  return data
    .filter(isRecord)
    .map((x) => ({
      timestamp: typeof x.timestamp === 'string' ? x.timestamp : new Date().toISOString(),
      userId: typeof x.userId === 'string' ? x.userId : null,
      userName: typeof x.userName === 'string' ? x.userName : null,
      userEmail: typeof x.userEmail === 'string' ? x.userEmail : null,
      userRole: typeof x.userRole === 'string' ? x.userRole : null,
      action: typeof x.action === 'string' ? x.action : null,
      documentId: typeof x.documentId === 'string' ? x.documentId : null,
      description: typeof x.description === 'string' ? x.description : null,
    }))
    .filter((x) => x.timestamp);
}

function parseUserActivityRows(data: unknown): UserActivityRow[] {
  if (!Array.isArray(data)) return [];
  return data
    .filter(isRecord)
    .map((x) => {
      const userId = typeof x.userId === 'string' ? x.userId : '';
      const uploads = typeof x.uploads === 'number' ? x.uploads : 0;
      const updates = typeof x.updates === 'number' ? x.updates : 0;
      const deletes = typeof x.deletes === 'number' ? x.deletes : 0;
      const searches = typeof x.searches === 'number' ? x.searches : 0;
      const downloads = typeof x.downloads === 'number' ? x.downloads : 0;
      return { userId, uploads, updates, deletes, searches, downloads };
    })
    .filter((x) => x.userId);
}

function parseCountMap(data: unknown): CountItem[] {
  if (!isRecord(data)) return [];

  return Object.entries(data)
    .filter(([, value]) => typeof value === 'number')
    .map(([label, count]) => ({ label, count: count as number }))
    .sort((a, b) => b.count - a.count);
}

function parseTimeReportRows(data: unknown): TimeReportRow[] {
  if (!Array.isArray(data)) return [];

  return data
    .filter(isRecord)
    .map((x) => {
      const dateRaw = x.date ?? x.Date;
      const date = typeof dateRaw === 'string' ? dateRaw : '';
      const addedRaw = x.added ?? x.Added;
      const updatedRaw = x.updated ?? x.Updated;
      const searchesRaw = x.searches ?? x.Searches;

      return {
        date,
        added: typeof addedRaw === 'number' ? addedRaw : 0,
        updated: typeof updatedRaw === 'number' ? updatedRaw : 0,
        searches: typeof searchesRaw === 'number' ? searchesRaw : 0,
      };
    })
    .filter((row) => row.date.length > 0);
}

function normalizeDocumentsResponse(data: unknown): DocumentLite[] {
  if (Array.isArray(data)) return data as DocumentLite[];

  if (isRecord(data)) {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.items)) return obj.items as DocumentLite[];
    if (Array.isArray(obj.documents)) return obj.documents as DocumentLite[];
  }

  return [];
}

function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function startOfWeek(): Date {
  const d = startOfToday();
  const day = d.getDay();
  const diff = (day + 6) % 7; // Monday=0
  d.setDate(d.getDate() - diff);
  return d;
}

function startOfMonth(): Date {
  const d = startOfToday();
  d.setDate(1);
  return d;
}

function startOfYear(): Date {
  const d = startOfToday();
  d.setMonth(0, 1);
  return d;
}

function filterByDateRange(logs: AuditLog[], range: DateRange): AuditLog[] {
  const now = new Date();
  let from: Date | null = null;

  if (range === 'today') from = startOfToday();
  else if (range === 'week') from = startOfWeek();
  else if (range === 'month') from = startOfMonth();
  else if (range === 'year') from = startOfYear();
  else from = null; // custom بدون from/to حالياً

  if (!from) return logs;

  const fromTime = from.getTime();
  const toTime = now.getTime();

  return logs.filter((l) => {
    const t = new Date(l.timestamp).getTime();
    return !Number.isNaN(t) && t >= fromTime && t <= toTime;
  });
}

function filterTimeReportByDateRange(rows: TimeReportRow[], range: DateRange): TimeReportRow[] {
  const now = new Date();
  let from: Date | null = null;

  if (range === 'today') from = startOfToday();
  else if (range === 'week') from = startOfWeek();
  else if (range === 'month') from = startOfMonth();
  else if (range === 'year') from = startOfYear();
  else from = null; // custom بدون from/to حالياً

  if (!from) return rows;

  const fromTime = from.getTime();
  const toTime = now.getTime();

  return rows.filter((row) => {
    const t = new Date(row.date).getTime();
    return !Number.isNaN(t) && t >= fromTime && t <= toTime;
  });
}

function getTopActions(logs: AuditLog[]): CountItem[] {
  const m = new Map<string, number>();

  for (const l of logs) {
    const key = (l.action || l.description || 'Unknown').toString().trim() || 'Unknown';
    m.set(key, (m.get(key) ?? 0) + 1);
  }

  return Array.from(m.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count);
}

function labelFromContentType(contentType: string | null | undefined, fileName?: string | null): string {
  const ct = (contentType ?? '').trim().toLowerCase();
  const fn = (fileName ?? '').trim().toLowerCase();

  // contentType أولاً
  if (ct === 'application/pdf') return 'PDF';
  if (ct.startsWith('image/')) return 'Image';
  if (ct.includes('spreadsheet') || ct.includes('excel')) return 'Excel';
  if (ct.includes('word') || ct.includes('msword')) return 'Word';
  if (ct.includes('powerpoint') || ct.includes('presentation')) return 'PowerPoint';
  if (ct.startsWith('text/')) return 'Text';
  if (ct.includes('zip')) return 'Archive';

  // fallback على الامتداد إذا contentType مش واضح
  const ext = fn.includes('.') ? fn.split('.').pop() ?? '' : '';
  if (ext === 'pdf') return 'PDF';
  if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'svg'].includes(ext)) return 'Image';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return 'Excel';
  if (['doc', 'docx'].includes(ext)) return 'Word';
  if (['ppt', 'pptx'].includes(ext)) return 'PowerPoint';
  if (ext) return ext.toUpperCase();

  return 'Unspecified';
}

function groupDocumentsByContentType(docs: DocumentLite[]): CountItem[] {
  const m = new Map<string, number>();

  for (const d of docs) {
    const key = labelFromContentType(d.contentType, d.fileName);
    m.set(key, (m.get(key) ?? 0) + 1);
  }

  return Array.from(m.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => {
      if (a.label === 'Unspecified') return 1;
      if (b.label === 'Unspecified') return -1;
      return b.count - a.count;
    });
}

function toChartData(items: CountItem[], limit = 8): ChartDatum[] {
  const top = items.slice(0, limit);
  const rest = items.slice(limit);
  const others = rest.reduce((sum, x) => sum + x.count, 0);

  const data: ChartDatum[] = top.map((x) => ({
    name: x.label.length > 18 ? x.label.slice(0, 18) + '…' : x.label,
    value: x.count,
  }));

  if (others > 0) data.push({ name: 'Others', value: others });

  return data;
}

function downloadCsvFile(filename: string, rows: string[][]) {
  const escapeCell = (s: string) => `"${s.split('"').join('""')}"`;
  const csv = rows.map((r) => r.map((c) => escapeCell(c)).join(',')).join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = window.document.createElement('a');
  a.href = url;
  a.download = filename;
  window.document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = window.document.createElement('a');
  a.href = url;
  a.download = filename;
  window.document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/* =======================
   Component
======================= */
export const Reports = () => {
  const { user, token } = useAuth();
  const { language, t } = useLanguage();
  const { toast } = useToast();

  const isRTL = language === 'ar';
  const iconGap = isRTL ? 'ml-2' : 'mr-2';

  const [reportType, setReportType] = useState<ReportType>('documentsByDepartment');
  const [dateRange, setDateRange] = useState<DateRange>('month');

  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const [totals, setTotals] = useState<DashboardTotals | null>(null);
  const [documentsByDepartment, setDocumentsByDepartment] = useState<CountItem[]>([]);
  const [documentsByType, setDocumentsByType] = useState<CountItem[]>([]);
  const [userActivityRows, setUserActivityRows] = useState<UserActivityRow[]>([]);
  const [timeReportRows, setTimeReportRows] = useState<TimeReportRow[]>([]);

  const canUseReportsApis = hasAnyRole(user, REPORTS_ALLOWED_ROLES);

  useEffect(() => {
    const loadAll = async () => {
      if (!token || !canUseReportsApis) return;

      setLoading(true);
      try {
        // totals دائماً
        const totalsRes = await api.get('/dashboard/totals');
        setTotals(parseTotals(totalsRes.data));

        const [deptResult, typeResult, userActivityResult, timeResult] = await Promise.allSettled([
          getDocumentsByDepartmentReportRequest(),
          getDocumentsByTypeReportRequest(),
          getUserActivityReportRequest(),
          getTimeReportRequest(),
        ]);

        setDocumentsByDepartment(deptResult.status === 'fulfilled' ? parseCountMap(deptResult.value) : []);
        setDocumentsByType(typeResult.status === 'fulfilled' ? parseCountMap(typeResult.value) : []);
        setUserActivityRows(
          userActivityResult.status === 'fulfilled' ? parseUserActivityRows(userActivityResult.value) : []
        );
        setTimeReportRows(timeResult.status === 'fulfilled' ? parseTimeReportRows(timeResult.value) : []);
      } catch (e) {
        console.error('❌ Reports load failed', e);
        setDocumentsByDepartment([]);
        setDocumentsByType([]);
        setUserActivityRows([]);
        setTimeReportRows([]);
      } finally {
        setLoading(false);
      }
    };

    loadAll();
  }, [token, canUseReportsApis]);

  const filteredTimeReport = useMemo(
    () => filterTimeReportByDateRange(timeReportRows, dateRange),
    [timeReportRows, dateRange]
  );

  const stats = useMemo(() => {
    const totalDocs = totals?.totalDocuments ?? 0;
    const todayUploads = totals?.todayUploads ?? 0;

    const activeUsers = userActivityRows.filter(
      (row) => row.uploads + row.updates + row.deletes + row.searches + row.downloads > 0
    ).length;

    return [
      {
        title: t('إجمالي الوثائق', 'Total documents'),
        value: loading ? '...' : formatNumber(totalDocs),
        icon: FileText,
        color: 'text-primary',
      },
      {
        title: t('رفع اليوم', "Today's uploads"),
        value: loading ? '...' : formatNumber(todayUploads),
        icon: TrendingUp,
        color: 'text-green-500',
      },
      {
        title: t('نشاط المستخدمين', 'Active users'),
        value: loading ? '...' : formatNumber(activeUsers),
        icon: TrendingUp,
        color: 'text-secondary',
      },
    ];
  }, [totals, userActivityRows, loading, t]);

  const chartTitle = useMemo(() => {
    switch (reportType) {
      case 'documentsByDepartment':
        return t('عدد الوثائق حسب الأقسام', 'Documents by department');
      case 'documentsByType':
        return t('عدد الوثائق حسب النوع', 'Documents by type');
      case 'userActivity':
        return t('نشاط المستخدمين', 'User activity');
      case 'timeReport':
        return t('تقرير زمني', 'Time report');
      default:
        return t('التقارير', 'Reports');
    }
  }, [reportType, t]);

  const sourceHint = useMemo(() => {
    switch (reportType) {
      case 'documentsByDepartment':
        return t('المصدر: /reports/documents-by-department', 'Source: /reports/documents-by-department');
      case 'documentsByType':
        return t('المصدر: /reports/documents-by-type', 'Source: /reports/documents-by-type');
      case 'userActivity':
        return t('المصدر: /reports/user-activity', 'Source: /reports/user-activity');
      case 'timeReport':
        return t('المصدر: /reports/time-report (مع فلترة زمنية بالفرونت)', 'Source: /reports/time-report (date filtered on frontend)');
      default:
        return '';
    }
  }, [reportType, t]);

  const chartItems = useMemo<CountItem[]>(() => {
    switch (reportType) {
      case 'documentsByDepartment':
        return documentsByDepartment;
      case 'documentsByType':
        return documentsByType;
      case 'userActivity':
        return userActivityRows
          .map((row) => ({
            label: row.userId,
            count: row.uploads + row.updates + row.deletes + row.searches + row.downloads,
          }))
          .filter((item) => item.count > 0)
          .sort((a, b) => b.count - a.count);
      case 'timeReport': {
        const sorted = [...filteredTimeReport].sort(
          (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
        );
        return sorted.map((row) => ({
          label: row.date.includes('T') ? row.date.split('T')[0] : row.date,
          count: row.added + row.updated + row.searches,
        }));
      }
      default:
        return [];
    }
  }, [documentsByDepartment, documentsByType, filteredTimeReport, reportType, userActivityRows]);

  const chartData = useMemo(() => {
    if (reportType === 'timeReport') {
      const limit =
        dateRange === 'today' ? 1 : dateRange === 'week' ? 7 : dateRange === 'month' ? 30 : 30;
      const tail = chartItems.slice(Math.max(0, chartItems.length - limit));
      return tail.map((item) => ({ name: item.label, value: item.count }));
    }

    return toChartData(chartItems, 8);
  }, [chartItems, dateRange, reportType]);

  const pieData = useMemo(() => {
    if (reportType === 'timeReport') {
      return chartData.slice(Math.max(0, chartData.length - 6));
    }

    return toChartData(chartItems, 6);
  }, [chartData, chartItems, reportType]);

  const handleExport = async () => {
    if (exporting) return;

    setExporting(true);
    try {
      if (reportType === 'documentsByDepartment') {
        const blob = await exportDepartmentExcelRequest();
        downloadBlob(blob, 'DepartmentReport.xlsx');
      } else if (reportType === 'documentsByType') {
        const blob = await exportTypeExcelRequest();
        downloadBlob(blob, 'DocumentTypeReport.xlsx');
      } else if (reportType === 'userActivity') {
        const blob = await exportUserActivityExcelRequest();
        downloadBlob(blob, 'UserActivityReport.xlsx');
      } else {
        const rows: string[][] = [];
        rows.push(['date', 'added', 'updated', 'searches', 'total']);

        for (const row of filteredTimeReport) {
          const label = row.date.includes('T') ? row.date.split('T')[0] : row.date;
          const total = row.added + row.updated + row.searches;
          rows.push([label, String(row.added), String(row.updated), String(row.searches), String(total)]);
        }

        downloadCsvFile(`TimeReport_${dateRange}.csv`, rows);
      }

      toast({
        title: t('تم التصدير', 'Exported'),
        description: t('تم تنزيل الملف بنجاح.', 'The file has been downloaded.'),
      });
    } catch (err) {
      console.error('Export failed', err);
      toast({
        variant: 'destructive',
        title: t('فشل التصدير', 'Export failed'),
        description: t('تعذر تصدير التقرير حالياً.', 'Unable to export the report right now.'),
      });
    } finally {
      setExporting(false);
    }
  };

  if (!canUseReportsApis) {
    return (
      <div className="p-6" style={{ direction: isRTL ? 'rtl' : 'ltr' }}>
        <Card className="hover-lift">
          <CardHeader>
            <CardTitle>{t('التقارير والإحصائيات', 'Reports & analytics')}</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground">
            {t('ليس لديك صلاحية لعرض هذه الصفحة.', 'You do not have permission to view this page.')}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 animate-fade-in" style={{ direction: isRTL ? 'rtl' : 'ltr' }}>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-cairo font-bold text-foreground mb-2">
            {t('التقارير والإحصائيات', 'Reports & analytics')}
          </h1>
          <p className="text-muted-foreground">{t('عرض وتحليل بيانات النظام', 'View and analyze system data')}</p>
        </div>
        <Button className="gradient-hero" onClick={() => void handleExport()} disabled={loading || exporting}>
          <Download className={`w-4 h-4 ${iconGap}`} />
          {t('تصدير التقرير', 'Export report')}
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        {stats.map((stat, index) => (
          <Card
            key={index}
            className="hover-lift animate-bounce-in"
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">{stat.title}</p>
                  <p className="text-3xl font-bold mb-1">{stat.value}</p>
                  <p className="text-sm text-muted-foreground">{loading ? '...' : t('بيانات مباشرة', 'Live data')}</p>
                </div>
                <div className={`w-12 h-12 rounded-lg gradient-hero flex items-center justify-center ${stat.color}`}>
                  <stat.icon className="w-6 h-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Settings */}
      <Card className="mb-6 hover-lift">
        <CardHeader>
          <CardTitle>{t('إعدادات التقرير', 'Report settings')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select value={reportType} onValueChange={(v) => setReportType(v as ReportType)}>
              <SelectTrigger>
                <SelectValue placeholder={t('نوع التقرير', 'Report type')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="documentsByDepartment">{t('وثائق حسب الأقسام', 'Documents by department')}</SelectItem>
                <SelectItem value="documentsByType">{t('وثائق حسب النوع', 'Documents by type')}</SelectItem>
                <SelectItem value="userActivity">{t('نشاط المستخدمين', 'User activity')}</SelectItem>
                <SelectItem value="timeReport">{t('تقرير زمني', 'Time report')}</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={dateRange}
              onValueChange={(v) => setDateRange(v as DateRange)}
              disabled={reportType !== 'timeReport'}
            >
              <SelectTrigger>
                <SelectValue placeholder={t('الفترة الزمنية', 'Date range')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today">{t('اليوم', 'Today')}</SelectItem>
                <SelectItem value="week">{t('هذا الأسبوع', 'This week')}</SelectItem>
                <SelectItem value="month">{t('هذا الشهر', 'This month')}</SelectItem>
                <SelectItem value="year">{t('هذا العام', 'This year')}</SelectItem>
                <SelectItem value="custom">{t('فترة مخصصة', 'Custom')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {reportType === 'timeReport' && dateRange === 'custom' && (
            <p className="text-xs text-muted-foreground mt-3">
              {t(
                'الفترة المخصصة غير مدعومة حالياً.',
                'Custom range is not supported yet.'
              )}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Chart */}
      <Card className="hover-lift">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-primary" />
            {chartTitle}
          </CardTitle>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="bg-muted rounded-lg p-4 h-[360px]">
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                <BarChart3 className="w-14 h-14 mb-3" />
                {t('جاري تحميل بيانات التقرير...', 'Loading report data...')}
              </div>
            </div>
          ) : chartData.length === 0 ? (
            <div className="bg-muted rounded-lg p-4 h-[360px]">
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                <BarChart3 className="w-14 h-14 mb-3" />
                {t('لا توجد بيانات كافية', 'Not enough data')}
              </div>
            </div>
          ) : (
            <>
              <div className="bg-muted rounded-lg p-4 h-[360px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="name"
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      interval={0}
                      angle={-15}
                      textAnchor="end"
                      height={55}
                    />
                    <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                    <Tooltip
                      contentStyle={{
                        background: 'hsl(var(--popover))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(value: unknown) => {
                        const n = typeof value === 'number' ? value : 0;
                        return [formatNumber(n), t('العدد', 'Count')];
                      }}
                    />
                    <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                      {chartData.map((_, idx) => (
                        <Cell key={`cell-${idx}`} fill={BAR_COLORS[idx % BAR_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <p className="text-xs text-muted-foreground mt-2">{sourceHint}</p>

              {/* Extra views (same data) */}
              <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-muted rounded-lg p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-semibold">
                      {t('تمثيل خطّي', 'Line view')}
                    </p>
                  </div>
                  <div className="h-[240px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis
                          dataKey="name"
                          stroke="hsl(var(--muted-foreground))"
                          fontSize={11}
                          interval={0}
                          angle={-15}
                          textAnchor="end"
                          height={55}
                        />
                        <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                        <Tooltip
                          contentStyle={{
                            background: 'hsl(var(--popover))',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: 8,
                            fontSize: 12,
                          }}
                          formatter={(value: unknown) => {
                            const n = typeof value === 'number' ? value : 0;
                            return [formatNumber(n), t('العدد', 'Count')];
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="value"
                          name={t('العدد', 'Count')}
                          stroke="hsl(var(--primary))"
                          strokeWidth={2.5}
                          dot={{ r: 3 }}
                          activeDot={{ r: 5 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="bg-muted rounded-lg p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-semibold">
                      {t('تمثيل دائري', 'Pie view')}
                    </p>
                  </div>
                  <div className="h-[240px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={52}
                          outerRadius={88}
                          paddingAngle={2}
                        >
                          {pieData.map((_, i) => (
                            <Cell key={`slice-${i}`} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            background: 'hsl(var(--popover))',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: 8,
                            fontSize: 12,
                          }}
                          formatter={(value: unknown) => {
                            const n = typeof value === 'number' ? value : 0;
                            return [formatNumber(n), t('العدد', 'Count')];
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
