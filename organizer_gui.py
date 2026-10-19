#!/usr/bin/env python3
"""
مرتّب الملفات - واجهة سطح مكتب عادية (PySide6)

التثبيت:   pip install PySide6 pymupdf python-docx
التشغيل:   python organizer_gui.py     (لازم smart_organizer.py في نفس الفولدر)
"""
import sys
from pathlib import Path

try:
    from PySide6.QtCore import QFileInfo, QSettings, Qt, QThread, QUrl, Signal
    from PySide6.QtGui import QAction, QBrush, QDesktopServices, QIcon, QKeySequence, QPalette
    from PySide6.QtWidgets import (
        QAbstractItemView, QApplication, QDialog, QFileDialog, QFileIconProvider,
        QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu,
        QMessageBox, QProgressBar, QPushButton, QSplitter, QStackedWidget, QStyle,
        QTableWidget, QTableWidgetItem, QToolBar, QTreeWidget, QTreeWidgetItem,
        QVBoxLayout, QWidget, QSizePolicy,
    )
except ImportError:
    print("محتاج تثبّت المكتبة الأول:  pip install PySide6 pymupdf python-docx")
    sys.exit(1)

import smart_organizer as eng

APP_TITLE = "مرتّب الملفات"


def make_settings() -> QSettings:
    """لو فيه ملف portable.txt جنب البرنامج، الإعدادات تتحفظ في نفس الفولدر (نسخة محمولة)."""
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    if (exe_dir / "portable.txt").exists():
        return QSettings(str(exe_dir / "settings.ini"), QSettings.Format.IniFormat)
    return QSettings("SmartOrganizer", "App")


def resource_path(name: str) -> Path:
    """مسار ملف مرفق، سواء شغّال من الكود أو من نسخة الـ exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name

# تعديلات بسيطة جدًا فوق الشكل الأصلي للنظام
QSS = """
QTableWidget::item { padding: 3px 6px; }
QToolBar { spacing: 4px; padding: 3px; }
QFrame#details { border-top: 1px solid palette(mid); }
"""


def top_category(p, root: Path) -> str:
    return p.dest.relative_to(root).parts[0]


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, root: Path, rename: bool):
        super().__init__()
        self.root, self.rename = root, rename

    def run(self):
        try:
            props = eng.build_proposals(
                self.root, self.rename,
                progress=lambda i, t, n: self.progress.emit(i, t, n))
            self.done.emit(props)
        except Exception as e:  # noqa
            self.failed.emit(str(e))


class HistoryDialog(QDialog):
    def __init__(self, parent, root: Path):
        super().__init__(parent)
        self.root = root
        self.setWindowTitle("سجل عمليات الترتيب")
        self.resize(720, 380)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["الوقت", "عدد الملفات", "أمثلة"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        self.undo_btn = QPushButton("تراجع عن آخر عملية")
        close = QPushButton("إغلاق")
        close.clicked.connect(self.accept)
        self.undo_btn.clicked.connect(self.undo)
        row.addWidget(self.undo_btn)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        log = eng.load_log(self.root)
        self.undo_btn.setEnabled(bool(log))
        for batch in reversed(log):
            r = self.table.rowCount()
            self.table.insertRow(r)
            moves = batch.get("moves", [])
            names = "، ".join(Path(m["to"]).name for m in moves[:3]) + (" ..." if len(moves) > 3 else "")
            for c, t in enumerate((batch.get("time", ""), str(len(moves)), names)):
                self.table.setItem(r, c, QTableWidgetItem(t))

    def undo(self):
        self.parent().do_undo(self.root)
        self.refresh()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1100, 680)
        self.setAcceptDrops(True)
        self.settings = make_settings()
        self.icons = QFileIconProvider()
        self.props = []
        self.root = None
        self.worker = None

        self._make_actions()
        self._make_menus()
        self._make_toolbar()
        self._make_central()
        self._make_statusbar()

        geo = self.settings.value("geometry")
        if geo:
            try:
                self.restoreGeometry(geo)
            except Exception:
                pass
        last = self.settings.value("last_folder", "")
        if last:
            self.path_edit.setText(last)
        self.refresh_ui_state()

    # ------------------------------------------------------------- الإجراءات
    def _make_actions(self):
        st = self.style()
        SP = QStyle.StandardPixmap

        def act(text, icon=None, shortcut=None, slot=None, tip=None):
            a = QAction(st.standardIcon(icon), text, self) if icon else QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if tip:
                a.setStatusTip(tip)
            if slot:
                a.triggered.connect(slot)
            return a

        self.act_open = act("اختيار فولدر...", SP.SP_DirOpenIcon, "Ctrl+O", self.browse, "اختيار الفولدر اللي هيتم ترتيبه")
        self.act_scan = act("فحص", SP.SP_BrowserReload, "F5", self.start_scan, "قراءة الملفات واقتراح الترتيب")
        self.act_apply = act("تنفيذ الترتيب", SP.SP_DialogApplyButton, "Ctrl+Return", self.do_apply, "نقل الملفات المحددة")
        self.act_undo = act("تراجع", SP.SP_ArrowBack, "Ctrl+Z", lambda: self.do_undo(), "الرجوع عن آخر عملية ترتيب")
        self.act_hist = act("السجل...", SP.SP_FileDialogDetailedView, "Ctrl+H", self.show_history)
        self.act_quit = act("خروج", None, "Ctrl+Q", self.close)
        self.act_about = act("عن البرنامج", None, None, self.about)
        self.act_selall = act("تحديد الكل", None, "Ctrl+Shift+A", lambda: self.set_all(True))
        self.act_selnone = act("إلغاء التحديد", None, "Ctrl+Shift+D", lambda: self.set_all(False))
        self.act_rename = QAction("إعادة تسمية الملفات حسب محتواها", self)
        self.act_rename.setCheckable(True)
        self.act_rename.setChecked(True)

    def _make_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("ملف")
        m.addAction(self.act_open)
        m.addAction(self.act_hist)
        m.addSeparator()
        m.addAction(self.act_quit)
        m = mb.addMenu("إجراءات")
        m.addAction(self.act_scan)
        m.addAction(self.act_apply)
        m.addAction(self.act_undo)
        m.addSeparator()
        m.addAction(self.act_selall)
        m.addAction(self.act_selnone)
        m = mb.addMenu("خيارات")
        m.addAction(self.act_rename)
        m = mb.addMenu("مساعدة")
        m.addAction(self.act_about)

    def _make_toolbar(self):
        tb = QToolBar("الأدوات")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        tb.addAction(self.act_open)
        tb.addAction(self.act_scan)
        tb.addSeparator()
        tb.addAction(self.act_apply)
        tb.addAction(self.act_undo)
        tb.addAction(self.act_hist)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.search = QLineEdit()
        self.search.setPlaceholderText("بحث في الأسماء")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(240)
        self.search.textChanged.connect(self.apply_filter)
        tb.addWidget(self.search)
        find = QAction(self)
        find.setShortcut(QKeySequence("Ctrl+F"))
        find.triggered.connect(self.search.setFocus)
        self.addAction(find)

    # ------------------------------------------------------------- الواجهة
    def _make_central(self):
        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 0)
        v.setSpacing(6)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("المسار:"))
        self.path_edit = QLineEdit()
        self.path_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.path_edit.setPlaceholderText(r"C:\Users\...\Downloads")
        self.path_edit.returnPressed.connect(self.start_scan)
        bar.addWidget(self.path_edit, 1)
        v.addLayout(bar)

        split = QSplitter()
        # شجرة الفئات
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("الفئات")
        self.tree.setRootIsDecorated(False)
        self.tree.setMinimumWidth(170)
        self.tree.itemSelectionChanged.connect(self.apply_filter)
        split.addWidget(self.tree)

        # الجدول + الحالة الفاضية + التفاصيل
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.stack = QStackedWidget()
        self.empty = QLabel("مفيش ملفات معروضة.\nاختار فولدر (أو اسحبه هنا) واضغط «فحص».")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setEnabled(False)
        self.stack.addWidget(self.empty)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "الاسم الحالي", "الاسم الجديد", "سيُنقل إلى", "السبب"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 34)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 220)
        self.table.setColumnWidth(4, 200)
        h.setStretchLastSection(False)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.itemSelectionChanged.connect(self.update_details)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.row_menu)
        self.table.doubleClicked.connect(lambda i: self.open_row(i.row()))
        self.stack.addWidget(self.table)
        rl.addWidget(self.stack, 1)

        self.details = QFrame()
        self.details.setObjectName("details")
        dl = QVBoxLayout(self.details)
        dl.setContentsMargins(8, 6, 8, 6)
        self.details_lbl = QLabel("")
        self.details_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.details_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_lbl.setWordWrap(True)
        dl.addWidget(self.details_lbl)
        rl.addWidget(self.details)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([200, 900])
        v.addWidget(split, 1)
        self.setCentralWidget(central)
        self.setStyleSheet(QSS)

    def _make_statusbar(self):
        sb = self.statusBar()
        self.count_lbl = QLabel("")
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(180)
        self.progress.setMaximumHeight(14)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        sb.addPermanentWidget(self.progress)
        sb.addPermanentWidget(self.count_lbl)
        sb.showMessage("جاهز")

    def msg(self, text):
        self.statusBar().showMessage(text)

    # ------------------------------------------------------------- سحب وإفلات
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                self.path_edit.setText(str(p))
                self.start_scan()
                return
        self.msg("اسحب فولدر مش ملف.")

    # ------------------------------------------------------------- الفحص
    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "اختيار الفولدر", self.path_edit.text())
        if d:
            self.path_edit.setText(d)
            self.start_scan()

    def _current_root(self):
        t = self.path_edit.text().strip().strip('"')
        return Path(t) if t and Path(t).is_dir() else None

    def start_scan(self):
        root = self._current_root()
        if not root:
            QMessageBox.warning(self, APP_TITLE, "اختار فولدر موجود الأول.")
            return
        if self.worker and self.worker.isRunning():
            return
        self.root = root
        self.settings.setValue("last_folder", str(root))
        self.act_scan.setEnabled(False)
        self.act_apply.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.msg("جاري قراءة الملفات...")
        self.worker = ScanWorker(root, self.act_rename.isChecked())
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_scan_done)
        self.worker.failed.connect(self.on_scan_failed)
        self.worker.start()

    def on_progress(self, i, total, name):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(i)
        self.msg(f"قراءة ({i} من {total}): {name}")

    def on_scan_failed(self, text):
        self.progress.setVisible(False)
        self.act_scan.setEnabled(True)
        self.msg("حصل خطأ أثناء الفحص")
        QMessageBox.critical(self, APP_TITLE, text)

    def on_scan_done(self, props):
        self.props = props
        self.progress.setVisible(False)
        self.act_scan.setEnabled(True)
        self.populate()
        self.msg(f"تم الفحص: {len(props)} ملف محتاج ترتيب." if props
                 else "الفولدر مترتب بالفعل، مفيش حاجة تتنقل.")

    # ------------------------------------------------------------- الجدول
    def populate(self):
        muted = QBrush(self.palette().color(QPalette.ColorRole.PlaceholderText))
        t = self.table
        t.blockSignals(True)
        t.setSortingEnabled(False)
        t.setRowCount(0)

        counts = {}
        for p in self.props:
            c = top_category(p, self.root)
            counts[c] = counts.get(c, 0) + 1

        self.tree.blockSignals(True)
        self.tree.clear()
        folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        root_item = QTreeWidgetItem([f"كل الملفات ({len(self.props)})"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, "")
        root_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon))
        self.tree.addTopLevelItem(root_item)
        for c in sorted(counts):
            it = QTreeWidgetItem([f"{c} ({counts[c]})"])
            it.setData(0, Qt.ItemDataRole.UserRole, c)
            it.setIcon(0, folder_icon)
            self.tree.addTopLevelItem(it)
        root_item.setSelected(True)
        self.tree.setCurrentItem(root_item)
        self.tree.blockSignals(False)

        for i, p in enumerate(self.props):
            r = t.rowCount()
            t.insertRow(r)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk.setCheckState(Qt.CheckState.Checked if p.enabled else Qt.CheckState.Unchecked)
            chk.setData(Qt.ItemDataRole.UserRole, i)
            src = QTableWidgetItem(self.icons.icon(QFileInfo(str(p.src))), p.src.name)
            new_name = QTableWidgetItem(p.dest.name)
            if p.dest.name == p.src.name:
                new_name.setForeground(muted)
            dest_dir = p.dest.parent.relative_to(self.root).as_posix()
            dest = QTableWidgetItem(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), dest_dir)
            reason = QTableWidgetItem(p.reason)
            reason.setForeground(muted)
            for c, it in enumerate((chk, src, new_name, dest, reason)):
                t.setItem(r, c, it)

        t.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        t.setSortingEnabled(True)
        t.blockSignals(False)
        self.stack.setCurrentIndex(1 if self.props else 0)
        self.apply_filter()
        self.refresh_ui_state()
        self.update_details()

    def apply_filter(self, *_):
        text = self.search.text().strip().lower()
        sel = self.tree.selectedItems()
        cat = sel[0].data(0, Qt.ItemDataRole.UserRole) if sel else ""
        for r in range(self.table.rowCount()):
            idx = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            p = self.props[idx]
            ok = not text or text in p.src.name.lower() or text in p.dest.name.lower()
            if ok and cat:
                ok = top_category(p, self.root) == cat
            self.table.setRowHidden(r, not ok)
        self.refresh_ui_state()

    def set_all(self, checked):
        if not self.props:
            return
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        t = self.table
        t.blockSignals(True)
        t.setSortingEnabled(False)
        for r in range(t.rowCount()):
            if t.isRowHidden(r):
                continue
            item = t.item(r, 0)
            item.setCheckState(state)
            self.props[item.data(Qt.ItemDataRole.UserRole)].enabled = checked
        t.setSortingEnabled(True)
        t.blockSignals(False)
        self.refresh_ui_state()

    def on_item_changed(self, item):
        if item.column() == 0:
            self.props[item.data(Qt.ItemDataRole.UserRole)].enabled = (
                item.checkState() == Qt.CheckState.Checked)
            self.refresh_ui_state()

    def _row_prop(self, row):
        item = self.table.item(row, 0)
        return self.props[item.data(Qt.ItemDataRole.UserRole)] if item else None

    def update_details(self):
        rows = self.table.selectionModel().selectedRows() if self.props else []
        if not rows:
            self.details_lbl.setText("")
            return
        p = self._row_prop(rows[0].row())
        if p:
            self.details_lbl.setText(f"من:  {p.src}\nإلى:  {p.dest}")

    def refresh_ui_state(self):
        selected = sum(p.enabled for p in self.props)
        visible = sum(1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r))
        self.count_lbl.setText(f"{selected} محدد من {len(self.props)}   |   معروض: {visible}   ")
        self.act_apply.setEnabled(selected > 0)
        self.act_selall.setEnabled(bool(self.props))
        self.act_selnone.setEnabled(bool(self.props))

    # ------------------------------------------------------------- كليك يمين
    def open_row(self, row):
        p = self._row_prop(row)
        if p and p.src.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.src)))

    def row_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        p = self._row_prop(row)
        if not p:
            return
        m = QMenu(self)
        a_open = m.addAction("فتح الملف")
        a_show = m.addAction("إظهار في المجلد")
        m.addSeparator()
        a_tog = m.addAction("استثناء من الترتيب" if p.enabled else "تضمين في الترتيب")
        chosen = m.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == a_open:
            self.open_row(row)
        elif chosen == a_show:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.src.parent)))
        elif chosen == a_tog:
            self.table.item(row, 0).setCheckState(
                Qt.CheckState.Unchecked if p.enabled else Qt.CheckState.Checked)

    # ------------------------------------------------------------- تنفيذ وتراجع
    def do_apply(self):
        n = sum(p.enabled for p in self.props)
        if not n:
            return
        r = QMessageBox.question(
            self, APP_TITLE,
            f"هيتم نقل {n} ملف إلى فولدرات مرتبة.\nمفيش ملف هيتحذف، وتقدر ترجع في أي وقت.\n\nتكمل؟")
        if r != QMessageBox.StandardButton.Yes:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            done = eng.apply_proposals(self.root, self.props)
        except Exception as e:  # noqa
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_TITLE, str(e))
            return
        QApplication.restoreOverrideCursor()
        self.props = []
        self.populate()
        self.msg(f"تم نقل {done} ملف. لو مش عاجبك: إجراءات > تراجع.")

    def do_undo(self, root=None):
        root = root or self._current_root() or self.root
        if not root:
            QMessageBox.information(self, APP_TITLE, "اختار الفولدر الأول.")
            return
        log = eng.load_log(root)
        if not log:
            QMessageBox.information(self, APP_TITLE, "مفيش عمليات سابقة للتراجع عنها.")
            return
        last = log[-1]
        r = QMessageBox.question(
            self, APP_TITLE,
            f"هيتم إرجاع {len(last['moves'])} ملف لأماكنهم الأصلية\n(عملية {last['time']}).\n\nتكمل؟")
        if r != QMessageBox.StandardButton.Yes:
            return
        n = eng.undo_last(root)
        self.msg(f"تم إرجاع {n} ملف.")

    def show_history(self):
        root = self._current_root() or self.root
        if not root:
            QMessageBox.information(self, APP_TITLE, "اختار الفولدر الأول.")
            return
        HistoryDialog(self, root).exec()

    def about(self):
        QMessageBox.about(self, APP_TITLE,
                          "مرتّب الملفات\nالنسخة 1.0\n\nبيقرا محتوى الملفات ويقترح ترتيبها.\n"
                          "كل حاجة بتتم على جهازك، ومفيش ملف بيتحذف.")

    def closeEvent(self, e):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(e)


def main():
    if sys.platform == "win32":
        try:  # عشان ويندوز يعرض أيقونة البرنامج في شريط المهام مش أيقونة بايثون
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SmartOrganizer.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    icon_file = resource_path("app.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
