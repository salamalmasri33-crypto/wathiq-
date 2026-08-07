import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import {
  FileText,
  Users,
  FolderOpen,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
  Eye,
  Search,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/config/api';
import { DASHBOARD_ALLOWED_ROLES, getPrimaryBackendRole, hasAnyRole } from '@/lib/roles';

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
  timestamp: string; // ISO
  userId?: string | null;
  userName?: string | null; // إذا الباك رجعه
  userEmail?: string | null; // إذا الباك رجعه
  userRole?: string | null;
  action?: string | null;
  documentId?: string | null;
  description?: string | null;
};

// بديل آمن عن /api/audit لما الباك يطلع 500 بسبب سجلات فيها userId غير صالح
type TimeReportRow = {
  date: string; // DateTime from backend
  added: number;
  updated: number;
  searches: number;
};

type QuickAction = {
  title: string;
  description: string;
  path: string;
  icon: typeof Users;
  primary?: boolean;
};

/* =======================
   Helpers
======================= */
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null;
}

const enNumber = new Intl.NumberFormat('en-US');

function formatNumber(n: number): string {
  return enNumber.format(n);
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
    .map((x) => {
      const timestamp = typeof x.timestamp === 'string' ? x.timestamp : new Date().toISOString();
      const userId = typeof x.userId === 'string' ? x.userId : null;
      const userName = typeof x.userName === 'string' ? x.userName : null;
      const userEmail = typeof x.userEmail === 'string' ? x.userEmail : null;
      const userRole = typeof x.userRole === 'string' ? x.userRole : null;
      const action = typeof x.action === 'string' ? x.action : null;
      const documentId = typeof x.documentId === 'string' ? x.documentId : null;
      const description = typeof x.description === 'string' ? x.description : null;

      return { timestamp, userId, userName, userEmail, userRole, action, documentId, description };
    });
}

function parseTimeReportList(data: unknown): TimeReportRow[] {
  if (!Array.isArray(data)) return [];
  return data
    .filter(isRecord)
    .map((x) => {
      // ReportsController يرجع: { date, added, updated, searches }
      const date = typeof x.date === 'string' ? x.date : new Date().toISOString();
      const added = typeof x.added === 'number' ? x.added : 0;
      const updated = typeof x.updated === 'number' ? x.updated : 0;
      const searches = typeof x.searches === 'number' ? x.searches : 0;
      return { date, added, updated, searches };
    });
}

function synthesizeActivityFromTimeReport(rows: TimeReportRow[]): AuditLog[] {
  if (!rows.length) return [];

  // خذ أحدث يوم (آخر صف حسب التاريخ)
  const sorted = [...rows].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  const latest = sorted[0];
  const ts = latest.date;

  const make = (action: string, count: number): AuditLog | null => {
    if (count <= 0) return null;
    return {
      timestamp: ts,
      userId: 'SYSTEM',
      userName: 'System',
      userRole: 'Admin',
      action,
      description: `${action} (${formatNumber(count)})`,
      documentId: null,
    };
  };

  return [
    make('AddDocument', latest.added),
    make('UpdateDocument', latest.updated),
    make('SearchDocuments', latest.searches),
  ].filter((x): x is AuditLog => x !== null);
}

function statusFromAction(text: string | null | undefined): 'success' | 'warning' | 'error' {
  const a = (text ?? '').toLowerCase();
  if (a.includes('delete') || a.includes('remove') || a.includes('حذف')) return 'error';
  if (a.includes('update') || a.includes('edit') || a.includes('metadata') || a.includes('تعديل') || a.includes('تحديث'))
    return 'warning';
  return 'success';
}

function formatRelativeTime(iso: string, lang: 'ar' | 'en'): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return lang === 'ar' ? 'منذ وقت' : 'a while ago';

  const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (diffSec < 60) return lang === 'ar' ? `منذ ${enNumber.format(diffSec)} ثانية` : `${enNumber.format(diffSec)} seconds ago`;

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return lang === 'ar' ? `منذ ${enNumber.format(diffMin)} دقيقة` : `${enNumber.format(diffMin)} minutes ago`;

  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return lang === 'ar' ? `منذ ${enNumber.format(diffH)} ساعة` : `${enNumber.format(diffH)} hours ago`;

  const diffD = Math.floor(diffH / 24);
  return lang === 'ar' ? `منذ ${enNumber.format(diffD)} يوم` : `${enNumber.format(diffD)} days ago`;
}

function pickUserDisplayName(a: AuditLog, fallback: string): string {
  return a.userName || a.userEmail || a.userId || fallback;
}

export default function Dashboard() {
  const { user, token } = useAuth();
  const { language, t } = useLanguage();
  const navigate = useNavigate();

  const isRTL = language === 'ar';
  const iconGap = isRTL ? 'ml-2' : 'mr-2';
  const primaryRole = getPrimaryBackendRole(user);

  const [totals, setTotals] = useState<DashboardTotals | null>(null);
  const [activity, setActivity] = useState<AuditLog[]>([]);
  const [loadingTotals, setLoadingTotals] = useState(false);
  const [loadingActivity, setLoadingActivity] = useState(false);

  const canSeeDashboardTotals = hasAnyRole(user, DASHBOARD_ALLOWED_ROLES);
  const canSeeRecentActivity = hasAnyRole(user, DASHBOARD_ALLOWED_ROLES);

  useEffect(() => {
    const loadTotals = async () => {
      if (!token || !canSeeDashboardTotals) return;

      setLoadingTotals(true);
      try {
        const res = await api.get('/dashboard/totals', {
          headers: { Authorization: `Bearer ${token}` },
        });

        const parsed = parseTotals(res.data);
        if (parsed) setTotals(parsed);
      } catch (e) {
        console.error('❌ Dashboard totals failed', e);
      } finally {
        setLoadingTotals(false);
      }
    };

    loadTotals();
  }, [token, canSeeDashboardTotals]);

  useEffect(() => {
    const loadActivity = async () => {
      if (!token || !canSeeRecentActivity) return;

      setLoadingActivity(true);
      try {
        // 1) جرّب /audit (بيعطي أسماء المستخدمين)
        const res = await api.get('/audit', {
          headers: { Authorization: `Bearer ${token}` },
        });

        const list = parseAuditList(res.data)
          .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
          .slice(0, 10);

        setActivity(list);
      } catch (e) {
        // إذا الباك رجّع 500 بسبب FormatException (userId غير صالح)
        console.error('❌ Audit load failed, falling back to time-report', e);

        try {
          const tr = await api.get('/reports/time-report', {
            headers: { Authorization: `Bearer ${token}` },
          });
          const rows = parseTimeReportList(tr.data);
          setActivity(synthesizeActivityFromTimeReport(rows));
        } catch (e2) {
          console.error('❌ Time-report fallback failed', e2);
          setActivity([]);
        }
      } finally {
        setLoadingActivity(false);
      }
    };

    loadActivity();
  }, [token, canSeeRecentActivity]);

  const adminStats = useMemo(() => {
    const totalDocs = totals?.totalDocuments ?? 0;
    const totalUsers = totals?.totalUsers ?? 0;
    const todayUploads = totals?.todayUploads ?? 0;
    const monthlyUpdates = totals?.monthlyUpdates ?? 0;

    return [
      {
        title: t('إجمالي الوثائق', 'Total documents'),
        value: loadingTotals ? '...' : formatNumber(totalDocs),
        icon: FileText,
        change: '',
        color: 'text-primary',
      },
      {
        title: t('المستخدمين', 'Users'),
        value: loadingTotals ? '...' : formatNumber(totalUsers),
        icon: Users,
        change: '',
        color: 'text-success',
      },
      {
        title: t('رفع اليوم', "Today's uploads"),
        value: loadingTotals ? '...' : formatNumber(todayUploads),
        icon: FolderOpen,
        change: '',
        color: 'text-warning',
      },
      {
        title: t('تحديثات هذا الشهر', 'Monthly updates'),
        value: loadingTotals ? '...' : formatNumber(monthlyUpdates),
        icon: TrendingUp,
        change: '',
        color: 'text-accent',
      },
    ];
  }, [totals, loadingTotals, t]);

  const recentActivity = useMemo(() => {
    const fallbackUser = t('مستخدم', 'User');
    return activity.map((a) => {
      const who = pickUserDisplayName(a, fallbackUser);
      const actionText = a.description || a.action || t('حدث', 'Event');
      return {
        user: who,
        action: actionText,
        time: formatRelativeTime(a.timestamp, language),
        status: statusFromAction(a.action || a.description),
        documentId: a.documentId ?? null,
      };
    });
  }, [activity, language, t]);

  const quickActions = useMemo<QuickAction[]>(() => {
    switch (primaryRole) {
      case 'SystemAdmin':
        return [
          {
            title: t('إدارة حسابات وصلاحيات المستخدمين', 'Manage user accounts and permissions'),
            description: t('إضافة المستخدمين وتعديل أدوارهم وصلاحياتهم', 'Add users and update their roles and permissions'),
            path: '/users',
            icon: Users,
            primary: true,
          },
          {
            title: t('البحث عن وثيقة محددة', 'Search for a specific document'),
            description: t('الوصول السريع إلى الوثائق عبر البحث المتقدم', 'Quickly find documents using advanced search'),
            path: '/search',
            icon: Search,
          },
          {
            title: t('متابعة وثائق النظام بالكامل', 'Review all system documents'),
            description: t('استعراض وإدارة جميع الوثائق ضمن نطاق النظام', 'Browse and manage all documents in system scope'),
            path: '/documents',
            icon: FileText,
          },
        ];
      case 'InstitutionAdmin':
        return [
          {
            title: t('إدارة مستخدمي المؤسسة', 'Manage institution users'),
            description: t('إضافة المستخدمين وتعديل أدوارهم داخل المؤسسة', 'Add users and update their roles inside the institution'),
            path: '/users',
            icon: Users,
            primary: true,
          },
          {
            title: t('البحث عن وثيقة محددة', 'Search for a specific document'),
            description: t('الوصول السريع إلى وثائق المؤسسة عبر البحث', 'Quickly find institution documents using search'),
            path: '/search',
            icon: Search,
          },
          {
            title: t('متابعة وثائق المؤسسة', 'Review institution documents'),
            description: t('استعراض وثائق المؤسسة وإدارة حالتها', 'Browse institution documents and manage their status'),
            path: '/documents',
            icon: FileText,
          },
        ];
      case 'Manager':
        return [
          {
            title: t('إضافة وثيقة جديدة', 'Add new document'),
            description: t('رفع ملف جديد للنظام', 'Upload a new file to the system'),
            path: '/add-document',
            icon: FolderOpen,
            primary: true,
          },
          {
            title: t('البحث عن وثيقة محددة', 'Search for a specific document'),
            description: t('الوصول السريع إلى وثائق القسم عبر البحث', 'Quickly find department documents using search'),
            path: '/search',
            icon: Search,
          },
          {
            title: t('مراجعة وثائق القسم', 'Review department documents'),
            description: t('استعراض الوثائق التي تحتاج متابعة داخل القسم', 'Review documents that need follow-up in your department'),
            path: '/documents',
            icon: FileText,
          },
        ];
      default:
        return [];
    }
  }, [primaryRole, t]);

  return (
    <div className="p-8 space-y-8" style={{ direction: isRTL ? 'rtl' : 'ltr' }}>
      {/* Header */}
      <div className="animate-slide-up">
        <h1 className="text-4xl font-cairo font-bold text-foreground mb-2">
          {t('مرحباً،', 'Hello,')} {user?.name} 👋
        </h1>
        <p className="text-muted-foreground text-lg">
          {hasAnyRole(user, ['SystemAdmin', 'InstitutionAdmin'])
            ? t('نظرة عامة على النظام', 'System overview')
            : hasAnyRole(user, ['Manager'])
              ? t('نظرة عامة على القسم', 'Your department overview')
              : t('نظرة عامة على وثائقك', 'Your documents overview')}
        </p>
      </div>

      {/* Stats Grid للأدمن فقط */}
      {canSeeDashboardTotals && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {adminStats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <Card
                key={stat.title}
                className="hover-lift animate-bounce-in border-border/50"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">{stat.title}</CardTitle>
                  <Icon className={`w-5 h-5 ${stat.color}`} />
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold font-cairo">{stat.value}</div>
                  <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                    <TrendingUp className="w-3 h-3" />
                    {t('بيانات مباشرة من النظام', 'Live data from the system')}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Quick Actions */}
      <Card className="animate-fade-in border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" />
            {t('إجراءات سريعة', 'Quick actions')}
          </CardTitle>
          <CardDescription>{t('الوصول السريع للمهام الشائعة', 'Quick access to common tasks')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {quickActions.map((action) => {
              const ActionIcon = action.icon;
              return (
                <Button
                  key={action.path}
                  variant={action.primary ? 'default' : 'outline'}
                  className={`h-auto py-4 justify-start hover-lift ${action.primary ? 'gradient-primary hover-glow' : ''}`}
                  onClick={() => navigate(action.path)}
                >
                  <ActionIcon className={`w-5 h-5 shrink-0 ${iconGap}`} />
                  <div className={isRTL ? 'text-right' : 'text-left'}>
                    <div className="font-semibold mb-1">{action.title}</div>
                    <div className={`text-xs ${action.primary ? 'opacity-80' : 'text-muted-foreground'}`}>
                      {action.description}
                    </div>
                  </div>
                </Button>
              );
            })}

            {quickActions.length === 0 && (
              <div className="text-sm text-muted-foreground">
                {t('لا توجد إجراءات سريعة متاحة لهذا الدور حالياً.', 'No quick actions are available for this role right now.')}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity للأدمن فقط */}
      {canSeeRecentActivity && (
        <Card className="animate-fade-in border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              {t('النشاط الأخير', 'Recent activity')}
            </CardTitle>
            <CardDescription>{t('آخر الأحداث في النظام', 'Latest events in the system')}</CardDescription>
          </CardHeader>

          <CardContent>
            {loadingActivity ? (
              <div className="text-sm text-muted-foreground">{t('جاري تحميل النشاط...', 'Loading activity...')}</div>
            ) : (
              <div className="space-y-4">
                {recentActivity.map((a, index) => (
                  <div
                    key={`${a.user}-${a.time}-${index}`}
                    className="flex items-start gap-4 p-3 rounded-lg hover:bg-muted/50 transition-colors animate-stagger"
                    style={{ animationDelay: `${index * 0.1}s` }}
                  >
                    <div
                      className={`mt-1 ${
                        a.status === 'success' ? 'text-success' : a.status === 'warning' ? 'text-warning' : 'text-destructive'
                      }`}
                    >
                      {a.status === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                    </div>

                    <div className="flex-1">
                      <p className="font-medium">{a.user}</p>
                      <p className="text-sm text-muted-foreground">{a.action}</p>

                      {/* ✅ إذا في documentId نعرض زر "عرض الوثيقة" */}
                      {a.documentId && (
                        <div className="mt-2">
                          <Button variant="outline" size="sm" className="justify-start" onClick={() => navigate(`/documents/${a.documentId}`)}>
                            <Eye className={`w-4 h-4 ${iconGap}`} />
                            {t('عرض الوثيقة', 'View document')}
                          </Button>
                        </div>
                      )}
                    </div>

                    <div className="text-xs text-muted-foreground whitespace-nowrap">{a.time}</div>
                  </div>
                ))}

                {recentActivity.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('لا يوجد نشاط حالياً.', 'No activity right now.')}</div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
