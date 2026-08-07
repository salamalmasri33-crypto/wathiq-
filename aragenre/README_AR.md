# خدمة Wathiq Classifier Service متعددة المؤسسات

الخدمة مبنية باستخدام FastAPI وتدعم Taxonomy وExamples وEmbeddings وفهرساً مستقلاً
في الذاكرة لكل مؤسسة. بقيت Pipeline التصنيف كما هي: Broad V10 وSpecific V18
Weighted RRF بقيمة K=20.

التحقق من المستخدم والـRole والـJWT واستخراج `institution_id` مسؤولية Backend وثق.
تعتبر خدمة التصنيف معرف المؤسسة القادم من Backend قيمة موثوقة، ولا تنفذ Authentication
أو Authorization. تستخدم SQLite حالياً لحفظ إعدادات المصنف أثناء التطوير. المقصود
بالـIndex هنا فهرس المصنف في الذاكرة وليس Elasticsearch.

## التشغيل

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Swagger: `http://127.0.0.1:8001/docs`

## مسارات المؤسسة

```text
POST /institutions/{institution_id}/config/import-definitions
POST /institutions/{institution_id}/config/import-examples
POST /institutions/{institution_id}/classify
POST /institutions/{institution_id}/classify/debug
```

طلب التصنيف:

```json
{"id":"document_123","text":"قرار إداري بتشكيل لجنة لمراجعة ملفات العقود"}
```

الاستجابة:

```json
{"id":"document_123","broad_genre":"AdministrativeAndOrganizational","specific_genre":"AdministrativeDecision"}
```

يعاد `id` كما وصل ولا يدخل في التصنيف أو Embedding. مسار debug مخصص للتطوير فقط.
المسارات القديمة باقية كـDeprecated aliases للمؤسسة المحددة في
`DEFAULT_INSTITUTION_ID` ولا تستخدم في أي تكامل جديد.

## Migration

عند اكتشاف مخطط قاعدة البيانات القديم تنشئ الخدمة تلقائياً نسخة
`wathiq_classifier.db.pre_multitenant.bak`، ثم تنقل التعريفات والأمثلة والـEmbeddings
والـMetadata إلى `DEFAULT_INSTITUTION_ID` وقيمتها الافتراضية `default-institution`.
العملية Idempotent ولا تتكرر بعد نجاح التحويل، ولا تحذف قاعدة البيانات الأصلية.

توجد ملفات اختبار مؤسستين داخل `data/multi_tenant_test`.

## Workflow إدارة التصنيفات والحذف

يمكن عرض وتعديل وحذف Broad وSpecific والأمثلة تحت
`/institutions/{institution_id}/config`. يرسل PATCH الحقول المعدلة فقط. يمكن معاينة
الاستبدال الكامل للـTaxonomy أو الأمثلة باستخدام `dry_run=true`، ثم تنفيذه باستخدام
`confirm=true` عند وجود بيانات ستحذف.

تسلسل الحذف المستخدم من الواجهة:

1. تستدعي الواجهة مسار `deletion-impact` للعنصر.
2. إذا كانت `requires_confirmation=true` تعرض رسالة التأكيد المعادة من الخدمة.
3. زر الإلغاء لا يرسل طلب حذف.
4. زر التأكيد يرسل DELETE مع `cascade=true`. وعند حذف آخر Specific فعال يستخدم أيضاً `allow_empty_broad=true`.
5. كل تعديل فعلي يعيد `index_ready=false` و`requires_rebuild=true`.
6. بعد انتهاء التعديلات يرسل الأدمن `POST .../config/rebuild-index` مرة واحدة.

تنفذ عمليات Cascade والاستبدال الكامل داخل SQLite Transactions. عند حدوث خطأ يتم
Rollback قبل تغيير حالة الفهرس المحمل. تحتوي جميع استعلامات البيانات والعدادات وحذف
Embeddings على `institution_id` لمنع أي تسرب بين المؤسسات.
