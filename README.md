# مرتّب الملفات (Smart Organizer)

برنامج ويندوز بيقرا **محتوى** ملفاتك ويقترح ترتيبها وتسميتها، بدل ما يرتب بالامتداد بس.
كل حاجة بتتم على جهازك، ومفيش ملف بيتحذف أو يتكتب فوقه، وأي عملية تقدر ترجع عنها.

[![Release](https://img.shields.io/github/v/release/YOUR_USERNAME/smart-organizer)](https://github.com/YOUR_USERNAME/smart-organizer/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/YOUR_USERNAME/smart-organizer/total)](https://github.com/YOUR_USERNAME/smart-organizer/releases)

## التحميل

من صفحة [Releases](https://github.com/YOUR_USERNAME/smart-organizer/releases/latest):

| الملف | الوصف |
|---|---|
| `SmartOrganizer_Setup.exe` | مثبّت عادي، بيضيف اختصار وأمر إزالة |
| `SmartOrganizer_Portable.zip` | نسخة محمولة، فك الضغط وشغّل `SmartOrganizer.exe` من أي مكان (حتى فلاشة) |

> ويندوز ممكن يعرض تحذير SmartScreen لأن البرنامج مش موقّع رقميًا. اضغط **More info** ثم **Run anyway**.

## المميزات

- قراءة محتوى PDF وWord والنصوص، وتصنيفها (فواتير، عقود، سير ذاتية، شهادات، دراسة، تقارير...) بالعربي والإنجليزي.
- اقتراح اسم واضح ومكان مناسب لكل ملف، مع **معاينة قبل التنفيذ**.
- ترتيب الصور والفيديو والصوت والمضغوطات والبرامج والكود في فولدرات.
- **تراجع (Undo)** عن آخر عملية، وسجل بكل العمليات.
- مبيحذفش ولا يكتب فوق أي ملف.
- نسخة محمولة بتحفظ إعداداتها جنب البرنامج.

## التشغيل من الكود

```bash
pip install -r requirements.txt
python organizer_gui.py
```

## البناء

**محليًا على ويندوز:** ثبّت Python وInno Setup 6، وشغّل `build_windows.bat`. الناتج في فولدر `installer_output`.

**تلقائيًا على GitHub:** ارفع tag بالشكل ده، والـ Actions هتبني وتنشر الـ Release لوحدها:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## أيقونة البرنامج

حط صورة PNG مربعة باسم `app.png` في جذر المشروع، وسكربت `make_icon.py` هيحولها لـ `app.ico` أثناء البناء.

## هيكل المشروع

```
smart_organizer.py   محرك التصنيف والترتيب
organizer_gui.py     الواجهة (PySide6)
make_icon.py         تحويل PNG إلى ICO
installer.iss        سكربت المثبّت (Inno Setup)
build_windows.bat    بناء محلي
docs/                موقع التحميل (GitHub Pages)
.github/workflows/   البناء والنشر التلقائي
```

## الترخيص

البرنامج بيستخدم مكتبة [PyMuPDF](https://github.com/pymupdf/PyMuPDF) المرخصة بـ AGPL-3.0، و[PySide6](https://doc.qt.io/qtforpython/) المرخصة بـ LGPL. تأكد إن ترخيص مشروعك متوافق معاهم قبل النشر. أبسط حل هو ترخيص المشروع بـ AGPL-3.0.
