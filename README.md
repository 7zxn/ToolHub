# ToolHub — Sherlock, Photon & Maigret

واجهة ويب بسيطة وحديثة (صفحة واحدة) تجمع ثلاث أدوات مفتوحة المصدر لأغراض OSINT:

- **[Sherlock](https://github.com/sherlock-project/sherlock)** — يبحث عن اسم مستخدم عبر مئات المواقع .
- **[Photon](https://github.com/s0md3v/Photon)** — يفحص رابط موقع ويستخرج منه الروابط الداخلية/الخارجية،
  نقاط النهاية، ملفات JavaScript، البيانات المهمة (Intel)، وغيرها.
- **[Maigret](https://github.com/soxoj/maigret)** — بحث موسّع عن اسم مستخدم عبر مئات المواقع، مع دعم
  استخراج بيانات إضافية من الحسابات الموجودة.

يختار المستخدم الأداة المطلوبة عبر قائمة منسدلة أعلى خانة البحث (تظهر عند الضغط على الزر)، وتُعرض
النتائج مباشرة في نفس الصفحة بدون إعادة تحميل.

## المكونات

```
  main.py             # تطبيق FastAPI (الخادم الخلفي + نقاط الـ API الثلاث)
  sherlock_runner.py  # سكربت يشغّل محرك Sherlock ويطبع النتائج بصيغة JSON
  photon_runner.py    # سكربت يشغّل أداة Photon ويطبع النتائج بصيغة JSON
  maigret_runner.py   # سكربت يشغّل أداة Maigret ويطبع النتائج بصيغة JSON
  static/
    index.html        # الصفحة الرئيسية (تحتوي القائمة المنسدلة لاختيار الأداة)
    style.css          # التنسيقات (تصميم Minimal، خط Inter)
    script.js          # منطق الواجهة الأمامية (Fetch API + التبديل بين الأدوات)
sherlock_project/     # حزمة Sherlock الأصلية (تُستخدم داخليًا كمحرك بحث)
photon_project/       # حزمة Photon الأصلية (تُستخدم داخليًا كمحرك فحص)
requirements.txt      # متطلبات تشغيل واجهة الويب (تتضمن حزمة maigret)
```

## طريقة العمل

1. يفتح المستخدم القائمة المنسدلة ويختار الأداة (Sherlock أو Photon أو Maigret)، ثم يدخل القيمة
   المطلوبة (اسم مستخدم لـ Sherlock/Maigret، أو رابط موقع لـ Photon) ويضغط "بحث".
2. يرسل المتصفح الطلب عبر `fetch()` إلى:
   - `POST /api/search` لأداة Sherlock.
   - `POST /api/photon` لأداة Photon.
   - `POST /api/maigret` لأداة Maigret.
3. يقوم الخادم (`webapp/main.py`) بتشغيل السكربت المناسب كعملية فرعية (subprocess).
4. يستدعي كل سكربت الأداة الأصلية مباشرة (بدون تحليل نصوص)، ويطبع النتائج بصيغة JSON منظمة
   إلى المخرج القياسي (stdout).
5. يقرأ الخادم مخرجات JSON، ويعيد النتائج المفيدة فقط إلى المتصفح (الحسابات الموجودة فعليًا لـ
   Sherlock/Maigret، أو البيانات المستخرجة لـ Photon).
6. تعرض الواجهة الأمامية النتائج كبطاقات (Card)، مع التفاف النص تلقائيًا لمنع اتساع الصفحة عند
   ظهور روابط أو قيم طويلة.

## التشغيل على Replit

المشروع مُعد للعمل مباشرة على Replit:

1. تأكد من تثبيت المتطلبات (تتم تلقائيًا عبر أداة إدارة الحزم في Replit، أو يدويًا):
   ```bash
   pip install -r requirements.txt
   ```
2. شغّل التطبيق (هذا هو أمر الـ Workflow الافتراضي على Replit، ويستمع على المنفذ 5000):
   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port 5000
   ```
3. افتح معاينة الموقع (Preview) داخل Replit — ستظهر الصفحة الرئيسية مباشرة.

## التشغيل محليًا (خارج Replit)

```bash
python -m venv .venv
source .venv/bin/activate        # على ويندوز: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 5000
```

ثم افتح المتصفح على: `http://localhost:5000`

## API

### `POST /api/search` (Sherlock)

**Request body:**
```json
{ "username": "github" }
```

**Response (نجاح):**
```json
{
  "success": true,
  "username": "github",
  "total_found": 3,
  "results": [
    { "site": "GitHub", "url": "https://github.com/github", "status": "Claimed" }
  ]
}
```

### `POST /api/photon` (Photon)

**Request body:**
```json
{ "url": "example.com" }
```

**Response (نجاح):**
```json
{
  "success": true,
  "url": "https://example.com",
  "total_found": 2,
  "results": [
    { "category": "روابط داخلية", "value": "https://example.com" },
    { "category": "روابط خارجية", "value": "https://iana.org/domains/example" }
  ]
}
```

### `POST /api/maigret` (Maigret)

**Request body:**
```json
{ "username": "github" }
```

**Response (نجاح):**
```json
{
  "success": true,
  "username": "github",
  "total_found": 24,
  "results": [
    { "site": "GitHub", "url": "https://github.com/github", "status": "Claimed" }
  ]
}
```

**Response (خطأ):** يعاد كود حالة HTTP مناسب (400/500/504) مع رسالة خطأ بالعربية في الحقل `detail`.

## معالجة الأخطاء

- إدخال فارغ أو غير صالح → خطأ 400 برسالة واضحة.
- تعذّر تشغيل الأداة (غير مثبتة، أو فشل الاستيراد) → خطأ 500 مع تفاصيل السبب.
- تجاوز المهلة الزمنية للفحص → خطأ 504.
- أي استجابة غير متوقعة من الـ Backend تُعرض للمستخدم داخل صندوق خطأ أحمر في الصفحة نفسها.

## ملاحظات تقنية

- لا تُستخدم أي مكتبة Frontend (React/Vue/إلخ) — HTML + CSS + JavaScript خام فقط.
- التواصل بين الواجهة والخادم يتم عبر `fetch()` بدون إعادة تحميل الصفحة (AJAX).
- تُقرأ نتائج كل أداة كـ JSON منظم مباشرة من الكود المصدري للأداة، وليس بتحليل نص الطرفية.
- التصميم متجاوب بالكامل (Mobile/Desktop) ويستخدم خط Inter من Google Fonts.
- بطاقات النتائج تسمح بالتفاف النص للقيم الطويلة (روابط، مفاتيح، نصوص) لمنع اتساع الصفحة بشكل غير
  متوقع، مع الحفاظ على شبكة عرض متجاوبة.
