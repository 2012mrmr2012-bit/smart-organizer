#!/usr/bin/env python3
"""
مرتّب الملفات الذكي - النسخة الأولى
- يقرأ محتوى الملفات (PDF / DOCX / TXT / CSV...) ويصنفها بالكلمات المفتاحية (عربي + إنجليزي)
- يعرض الاقتراحات قبل التنفيذ
- لا يحذف ولا يكتب فوق أي ملف أبدًا (نقل + إعادة تسمية فقط)
- كل عملية تتسجل ويمكن التراجع عنها (Undo)

التشغيل:
    python smart_organizer.py            # واجهة رسومية
    python smart_organizer.py FOLDER     # معاينة في الطرفية (من غير تنفيذ)

مكتبات اختيارية (للقراءة الأعمق):
    pip install pymupdf python-docx
"""
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# مكتبات اختيارية: لو فشل تحميلها لأي سبب البرنامج يكمل من غيرها
try:
    import pymupdf as fitz  # PyMuPDF (الاسم الجديد)
except Exception:
    try:
        import fitz  # PyMuPDF (الاسم القديم)
    except Exception:
        fitz = None
try:
    import docx  # python-docx
except Exception:
    docx = None

LOG_NAME = ".organizer_log.json"
MAX_CHARS = 6000  # أقصى كمية نص نقراها من كل ملف

# ---------------------------------------------------------------- الفئات حسب الامتداد
EXT_CATEGORIES = {
    "مستندات": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md"},
    "جداول": {".xls", ".xlsx", ".csv", ".ods"},
    "عروض تقديمية": {".ppt", ".pptx", ".odp"},
    "صور": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".svg"},
    "فيديو": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "صوت": {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"},
    "مضغوطات": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "برامج": {".exe", ".msi", ".dmg", ".apk", ".pkg", ".deb"},
    "كود": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".cs",
            ".json", ".xml", ".sql", ".sh", ".ipynb"},
}
READABLE = {".pdf", ".docx", ".txt", ".md", ".csv", ".rtf"}

# ---------------------------------------------------------------- قواعد المحتوى
# (التصنيف، المجلد الفرعي، التسمية، الكلمات المفتاحية)
CONTENT_RULES = [
    ("مستندات/فواتير", "فاتورة كهرباء", ["فاتورة كهرباء", "شركة الكهرباء", "كيلووات", "electricity bill"]),
    ("مستندات/فواتير", "فاتورة مياه", ["فاتورة مياه", "شركة المياه", "water bill"]),
    ("مستندات/فواتير", "فاتورة غاز", ["فاتورة غاز", "gas bill"]),
    ("مستندات/فواتير", "فاتورة إنترنت وموبايل", ["فاتورة الإنترنت", "فاتورة انترنت", "vodafone", "فودافون", "orange", "اتصالات", "we ", "internet bill"]),
    ("مستندات/فواتير", "فاتورة", ["فاتورة", "invoice", "إجمالي المبلغ", "الضريبة", "vat", "total due", "receipt", "إيصال"]),
    ("مستندات/عقود", "عقد", ["عقد", "الطرف الأول", "الطرف الثاني", "contract", "agreement", "hereinafter"]),
    ("مستندات/سيرة ذاتية", "سيرة ذاتية", ["سيرة ذاتية", "curriculum vitae", "resume", "work experience", "الخبرات العملية"]),
    ("مستندات/شهادات", "شهادة", ["شهادة", "certificate", "certify", "تشهد بأن", "تخرج"]),
    ("مستندات/بنك وفلوس", "كشف حساب", ["كشف حساب", "bank statement", "الرصيد", "iban", "account statement"]),
    ("مستندات/دراسة", "ورقة دراسية", ["محاضرة", "الفصل الدراسي", "امتحان", "lecture", "chapter", "assignment", "syllabus", "الجامعة", "university", "abstract", "references"]),
    ("مستندات/شغل", "تقرير", ["تقرير", "report", "executive summary", "ملخص تنفيذي"]),
    ("مستندات/شغل", "اجتماع", ["محضر اجتماع", "meeting minutes", "agenda", "جدول الأعمال"]),
    ("مستندات/هوية ووثائق رسمية", "وثيقة رسمية", ["بطاقة الرقم القومي", "جواز سفر", "passport", "الرقم القومي", "شهادة ميلاد", "رخصة"]),
]

DATE_PATTERNS = [
    (re.compile(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b"), "ymd"),
    (re.compile(r"\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])[-/.](20\d{2})\b"), "dmy"),
]
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


# ---------------------------------------------------------------- قراءة المحتوى
def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in {".txt", ".md", ".csv", ".rtf"}:
            for enc in ("utf-8", "utf-16", "cp1256", "latin-1"):
                try:
                    return path.read_text(encoding=enc)[:MAX_CHARS]
                except (UnicodeError, OSError):
                    continue
        elif ext == ".pdf" and fitz:
            text = ""
            with fitz.open(path) as pdf:
                for page in pdf:
                    text += page.get_text()
                    if len(text) >= MAX_CHARS:
                        break
            return text[:MAX_CHARS]
        elif ext == ".docx" and docx:
            d = docx.Document(str(path))
            return "\n".join(p.text for p in d.paragraphs)[:MAX_CHARS]
    except Exception:
        pass
    return ""


def find_date(text: str, fallback: float) -> str:
    text = text.translate(ARABIC_DIGITS)
    for rx, kind in DATE_PATTERNS:
        m = rx.search(text)
        if m:
            if kind == "ymd":
                y, mo = m.group(1), m.group(2)
            else:
                y, mo = m.group(3), m.group(2)
            return f"{y}-{int(mo):02d}"
    return datetime.fromtimestamp(fallback).strftime("%Y-%m")


def classify_by_extension(ext: str) -> str:
    for cat, exts in EXT_CATEGORIES.items():
        if ext in exts:
            return cat
    return "مراجعة"


def classify_by_content(text: str):
    """يرجع (folder, label) لأعلى قاعدة بنقاط، أو None."""
    if not text.strip():
        return None
    low = text.translate(ARABIC_DIGITS).lower()
    best, best_score = None, 0
    for folder, label, kws in CONTENT_RULES:
        score = sum(low.count(k.lower()) for k in kws)
        if score > best_score:
            best, best_score = (folder, label), score
    return best


SAFE_RX = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def clean_name(name: str) -> str:
    return SAFE_RX.sub("_", name).strip(" .")


# ---------------------------------------------------------------- الاقتراحات
@dataclass
class Proposal:
    src: Path
    dest: Path
    reason: str
    enabled: bool = True


def unique_path(p: Path, taken: set) -> Path:
    if not p.exists() and p not in taken:
        return p
    i = 2
    while True:
        cand = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not cand.exists() and cand not in taken:
            return cand
        i += 1


def build_proposals(root: Path, rename: bool = True, progress=None) -> list:
    proposals, taken = [], set()
    files = [f for f in sorted(root.iterdir())
             if f.is_file() and not f.name.startswith(".") and f.name != LOG_NAME]
    for i, f in enumerate(files, 1):
        if progress:
            progress(i, len(files), f.name)
        ext = f.suffix.lower()
        category = classify_by_extension(ext)
        new_name, reason = f.name, f"حسب النوع ({ext or 'بدون امتداد'})"

        if category in ("مستندات", "جداول") and ext in READABLE:
            text = extract_text(f)
            hit = classify_by_content(text)
            if hit:
                folder, label = hit
                category = folder
                reason = f"المحتوى يشبه: {label}"
                if rename:
                    date = find_date(text, f.stat().st_mtime)
                    new_name = clean_name(f"{date} {label}{f.suffix}")
            elif ext in {".pdf", ".docx"} and not text.strip():
                reason = "ملف بدون نص قابل للقراءة (محتاج OCR) - حسب النوع"
        elif category == "صور":
            low = f.name.lower()
            if any(k in low for k in ("screenshot", "screen shot", "لقطة")):
                category = "صور/سكرين شوت"
                reason = "الاسم يدل على سكرين شوت"
            else:
                category = "صور/أخرى"

        dest = unique_path(root / category / new_name, taken)
        if dest == f:
            continue
        taken.add(dest)
        proposals.append(Proposal(f, dest, reason))
    return proposals


# ---------------------------------------------------------------- التنفيذ والتراجع
def load_log(root: Path) -> list:
    p = root / LOG_NAME
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_log(root: Path, log: list):
    (root / LOG_NAME).write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def apply_proposals(root: Path, proposals: list) -> int:
    moves, done = [], 0
    for pr in proposals:
        if not pr.enabled or not pr.src.exists():
            continue
        dest = unique_path(pr.dest, set())  # حماية إضافية من الكتابة فوق ملف
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pr.src), str(dest))
        moves.append({"from": str(pr.src), "to": str(dest)})
        done += 1
    if moves:
        log = load_log(root)
        log.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "moves": moves})
        save_log(root, log)
    return done


def undo_last(root: Path) -> int:
    log = load_log(root)
    if not log:
        return 0
    batch, restored = log.pop(), 0
    for m in reversed(batch["moves"]):
        src, dst = Path(m["to"]), Path(m["from"])
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            back = unique_path(dst, set())
            shutil.move(str(src), str(back))
            restored += 1
    # تنظيف المجلدات الفاضية اللي إحنا عملناها
    for m in batch["moves"]:
        d = Path(m["to"]).parent
        while d != root and d.exists() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    save_log(root, log)
    return restored


# ---------------------------------------------------------------- الواجهة
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    app = tk.Tk()
    app.title("مرتّب الملفات الذكي")
    app.geometry("980x560")

    state = {"root": None, "props": []}

    top = ttk.Frame(app, padding=8)
    top.pack(fill="x")
    path_var = tk.StringVar()
    ttk.Entry(top, textvariable=path_var).pack(side="left", fill="x", expand=True, padx=(0, 6))
    rename_var = tk.BooleanVar(value=True)

    cols = ("ok", "src", "dest", "reason")
    tree = ttk.Treeview(app, columns=cols, show="headings", selectmode="browse")
    for c, t, w in (("ok", "✓", 40), ("src", "الملف الحالي", 260), ("dest", "المكان الجديد", 380), ("reason", "السبب", 240)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w" if c != "ok" else "center")
    tree.pack(fill="both", expand=True, padx=8)

    status = tk.StringVar(value="اختار فولدر وبعدين اضغط «فحص».")
    ttk.Label(app, textvariable=status, padding=8).pack(fill="x")

    def refresh():
        tree.delete(*tree.get_children())
        for i, p in enumerate(state["props"]):
            rel = p.dest.relative_to(state["root"])
            tree.insert("", "end", iid=str(i),
                        values=("☑" if p.enabled else "☐", p.src.name, str(rel), p.reason))

    def browse():
        d = filedialog.askdirectory()
        if d:
            path_var.set(d)

    def scan():
        root = Path(path_var.get().strip())
        if not root.is_dir():
            messagebox.showerror("خطأ", "اختار فولدر صحيح.")
            return
        status.set("جاري قراءة الملفات...")
        app.update_idletasks()
        state["root"] = root
        state["props"] = build_proposals(root, rename_var.get())
        refresh()
        status.set(f"لقيت {len(state['props'])} ملف محتاج ترتيب. دوس مرتين على أي سطر عشان تلغيه أو تفعّله.")

    def toggle(_e):
        sel = tree.focus()
        if sel:
            p = state["props"][int(sel)]
            p.enabled = not p.enabled
            refresh()

    def apply():
        if not state["props"]:
            return
        n = sum(p.enabled for p in state["props"])
        if not messagebox.askyesno("تأكيد", f"هنقل {n} ملف. تكمل؟ (تقدر ترجّع بعدها)"):
            return
        done = apply_proposals(state["root"], state["props"])
        state["props"] = []
        refresh()
        status.set(f"تم نقل {done} ملف. لو مش عاجبك اضغط «تراجع».")

    def undo():
        if not state["root"]:
            if not path_var.get().strip():
                return
            state["root"] = Path(path_var.get().strip())
        n = undo_last(state["root"])
        status.set(f"تم إرجاع {n} ملف." if n else "مفيش حاجة للتراجع عنها.")

    ttk.Button(top, text="اختيار فولدر", command=browse).pack(side="left", padx=2)
    ttk.Checkbutton(top, text="إعادة تسمية", variable=rename_var).pack(side="left", padx=6)
    ttk.Button(top, text="فحص", command=scan).pack(side="left", padx=2)
    ttk.Button(top, text="تنفيذ", command=apply).pack(side="left", padx=2)
    ttk.Button(top, text="تراجع", command=undo).pack(side="left", padx=2)
    tree.bind("<Double-1>", toggle)
    app.mainloop()


def run_cli(folder: str):
    root = Path(folder)
    for p in build_proposals(root):
        print(f"{p.src.name}  ->  {p.dest.relative_to(root)}   [{p.reason}]")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli(sys.argv[1])
    else:
        run_gui()
