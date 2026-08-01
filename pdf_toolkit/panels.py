# -*- coding: utf-8 -*-
"""
panels.py - 功能面板模块
包含合并/拆分/压缩/旋转/页面管理/提取/页面检测 功能面板，
以及后台工作线程 PDFWorker。
"""

import os
from typing import List

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QPoint, QRect
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QLineEdit, QSpinBox, QComboBox, QRadioButton,
    QButtonGroup, QProgressBar, QMessageBox, QScrollArea, QGridLayout,
    QFrame, QMenu, QAction, QSizePolicy, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QCheckBox, QDialog, QSplitter, QDoubleSpinBox, QTabWidget
)

import pdf_core
from i18n import tr, translator
from log_window import log_info, log_warn, log_error


def _default_output_name(src_path: str, suffix: str) -> str:
    """根据源文件名生成默认输出名: 原名_后缀.pdf"""
    base = os.path.splitext(os.path.basename(src_path))[0]
    return f"{base}_{suffix}.pdf"


# ===========================================================================
# 后台工作线程 / Background Worker
# ===========================================================================

class PDFWorker(QThread):
    """在后台线程执行 PDF 任务，避免阻塞 UI。"""
    progress = pyqtSignal(int, int, str)   # current, total, message
    finished_ok = pyqtSignal(object)      # result
    failed = pyqtSignal(str)              # error message

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            # 注入进度回调 / Inject progress callback
            self._kwargs.setdefault("progress_cb", self._on_progress)
            result = self._func(*self._args, **self._kwargs)
            self.finished_ok.emit(result)
        except pdf_core.PDFError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")

    def _on_progress(self, current, total, message):
        self.progress.emit(current, total, message)


class _PreviewWorker(QThread):
    """后台渲染单页预览图，避免点击行时卡顿。"""
    preview_ready = pyqtSignal(int, QImage, dict)  # page_idx, image, stats

    def __init__(self, src_path: str, page_idx: int, max_size: int = 700):
        super().__init__()
        self._src = src_path
        self._page_idx = page_idx
        self._max_size = max_size

    def run(self):
        try:
            png = pdf_core.render_page_image(self._src, self._page_idx,
                                             self._max_size)
            img = QImage.fromData(png, "PNG")
            stats = pdf_core.page_stats(self._src, self._page_idx)
            self.preview_ready.emit(self._page_idx, img, stats)
        except Exception as e:
            log_error(f"[Preview] page {self._page_idx + 1} failed: {e}")
            self.preview_ready.emit(self._page_idx, QImage(),
                                    {"white_ratio": 0, "mean": 0, "std": 0,
                                     "is_blank": False})


class _ThumbLoader(QThread):
    """后台批量加载缩略图，逐页发回，避免大 PDF 阻塞 UI。"""
    thumb_ready = pyqtSignal(int, QImage)   # orig_page_idx, image
    progress = pyqtSignal(int, int)         # current, total

    def __init__(self, src_path: str, page_indices: List[int],
                 max_size: int = 180):
        super().__init__()
        self._src = src_path
        self._indices = list(page_indices)
        self._max_size = max_size
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        total = len(self._indices)
        for i, idx in enumerate(self._indices):
            if self._cancel:
                return
            try:
                png = pdf_core.generate_thumbnail(self._src, idx,
                                                  self._max_size)
                img = QImage.fromData(png, "PNG")
            except Exception:
                img = QImage()
            self.thumb_ready.emit(idx, img)
            self.progress.emit(i + 1, total)
        self.progress.emit(total, total)


# ===========================================================================
# 基础面板 / Base Panel
# ===========================================================================

class BasePanel(QWidget):
    """所有功能面板的基类，提供标题、描述、进度条、执行按钮的通用布局。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: PDFWorker = None
        self._build_common_ui()

    def _build_common_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 20, 20, 20)
        self._root.setSpacing(10)

        # 标题 / Title
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            "font-size:18px; font-weight:bold; color:#2c3e50;")
        self._root.addWidget(self._title_label)

        # 描述 / Description
        self._desc_label = QLabel()
        self._desc_label.setStyleSheet("color:#7f8c8d;")
        self._desc_label.setWordWrap(True)
        self._root.addWidget(self._desc_label)

        # 内容区占位 (子类填充) / Content area placeholder
        self._content = QVBoxLayout()
        self._content.setSpacing(8)
        self._root.addLayout(self._content, 1)

        # 底部: 进度条 + 执行按钮 / Bottom: progress + execute
        self._bottom = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFixedHeight(20)
        self._progress.setVisible(False)
        self._bottom.addWidget(self._progress, 1)

        self._run_btn = QPushButton()
        self._run_btn.setFixedHeight(34)
        self._run_btn.setMinimumWidth(120)
        self._run_btn.setStyleSheet(
            "QPushButton{background:#3498db; color:white; border:none;"
            "border-radius:4px; font-weight:bold; padding:0 20px;}"
            "QPushButton:hover{background:#2980b9;}"
            "QPushButton:disabled{background:#bdc3c7;}")
        self._run_btn.clicked.connect(self.on_execute)
        self._bottom.addWidget(self._run_btn)
        self._root.addLayout(self._bottom)

    # --- 子类重写钩子 / Hooks for subclasses ---
    def title_key(self) -> str:
        return ""

    def desc_key(self) -> str:
        return ""

    def run_button_key(self) -> str:
        return "run"

    def on_execute(self):
        """子类实现：组装任务并启动 PDFWorker。"""
        pass

    # --- 通用方法 / Common methods ---
    def start_worker(self, func, *args, **kwargs):
        if self._worker and self._worker.isRunning():
            return
        self._set_running(True)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        log_info(f"[{self.__class__.__name__}] start: {func.__name__}")
        self._worker = PDFWorker(func, *args, **kwargs)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, current, total, message):
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(current)

    def _on_finished(self, result):
        self._set_running(False)
        self._progress.setVisible(False)
        log_info(f"[{self.__class__.__name__}] done: {self._worker._func.__name__}")
        self.on_success(result)

    def _on_failed(self, err):
        self._set_running(False)
        self._progress.setVisible(False)
        log_error(f"[{self.__class__.__name__}] failed: {err}")
        QMessageBox.critical(self, tr("failed"), err)

    def _set_running(self, running: bool):
        self._run_btn.setEnabled(not running)

    def on_success(self, result):
        """子类实现：处理成功结果。"""
        pass

    def retranslate(self):
        """语言切换时刷新所有文本。"""
        if self.title_key():
            self._title_label.setText(tr(self.title_key()))
        if self.desc_key():
            self._desc_label.setText(tr(self.desc_key()))
        self._run_btn.setText(tr(self.run_button_key()))
        self._do_retranslate()

    def _do_retranslate(self):
        """子类重写以刷新子控件文本。"""
        pass


# ===========================================================================
# 输出目录选择器 / Output Dir Picker (复用组件)
# ===========================================================================

class OutputDirPicker(QWidget):
    """输出目录选择器组件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._browse_btn = QPushButton()
        self._browse_btn.clicked.connect(self._browse)
        h.addWidget(self._label)
        h.addWidget(self._path_edit, 1)
        h.addWidget(self._browse_btn)
        self.retranslate()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("select_output"))
        if d:
            self._path_edit.setText(d)

    def path(self) -> str:
        return self._path_edit.text().strip()

    def set_path(self, p: str):
        self._path_edit.setText(p)

    def retranslate(self):
        self._label.setText(tr("select_output") + ":")
        self._browse_btn.setText(tr("browse"))


# ===========================================================================
# 1. 合并 PDF 面板 / Merge Panel
# ===========================================================================

class MergePanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        # 文件列表 + 操作按钮 / File list + buttons
        row = QHBoxLayout()
        self._file_list = QListWidget()
        self._file_list.setAcceptDrops(True)
        self._file_list.setDragDropMode(QListWidget.InternalMove)
        self._file_list.setSelectionMode(QListWidget.ExtendedSelection)
        row.addWidget(self._file_list, 1)

        btn_col = QVBoxLayout()
        self._add_btn = QPushButton()
        self._add_btn.clicked.connect(self._add_files)
        self._remove_btn = QPushButton()
        self._remove_btn.clicked.connect(self._remove_selected)
        self._clear_btn = QPushButton()
        self._clear_btn.clicked.connect(self._clear_all)
        self._up_btn = QPushButton()
        self._up_btn.clicked.connect(lambda: self._move(-1))
        self._down_btn = QPushButton()
        self._down_btn.clicked.connect(lambda: self._move(1))
        for b in (self._add_btn, self._remove_btn, self._clear_btn,
                  self._up_btn, self._down_btn):
            b.setFixedWidth(110)
            btn_col.addWidget(b)
        btn_col.addStretch(1)
        row.addLayout(btn_col)

        grp = QGroupBox()
        grp.setLayout(row)
        self._content.addWidget(grp)

        # 输出配置 / Output config
        out_row = QHBoxLayout()
        self._out_name_label = QLabel()
        self._out_name_edit = QLineEdit("merged.pdf")
        out_row.addWidget(self._out_name_label)
        out_row.addWidget(self._out_name_edit, 1)
        self._content.addLayout(out_row)

        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("select_pdfs"), "", "PDF (*.pdf)")
        for f in files:
            item = QListWidgetItem(f)
            item.setIcon(QIcon.fromTheme("document-open"))
            self._file_list.addItem(item)
        # 默认输出名取第一个文件名 + _merged / Default name from first file
        if self._file_list.count() > 0:
            first = self._file_list.item(0).text()
            self._out_name_edit.setText(_default_output_name(first, "merged"))

    def _remove_selected(self):
        for item in self._file_list.selectedItems():
            self._file_list.takeItem(self._file_list.row(item))

    def _clear_all(self):
        self._file_list.clear()

    def _move(self, delta):
        row = self._file_list.currentRow()
        if row < 0:
            return
        target = row + delta
        if 0 <= target < self._file_list.count():
            item = self._file_list.takeItem(row)
            self._file_list.insertItem(target, item)
            self._file_list.setCurrentRow(target)

    def on_execute(self):
        files = [self._file_list.item(i).text()
                 for i in range(self._file_list.count())]
        if not files:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_files"))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        name = self._out_name_edit.text().strip() or "merged.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        out_path = os.path.join(out_dir, name)
        self.start_worker(pdf_core.merge_pdfs, files, out_path)

    def on_success(self, result):
        QMessageBox.information(
            self, tr("success"), tr("merge_success", n=result))
        self._out_dir.set_path(self._out_dir.path())

    def _do_retranslate(self):
        self._add_btn.setText(tr("add_files"))
        self._remove_btn.setText(tr("remove"))
        self._clear_btn.setText(tr("remove_all"))
        self._up_btn.setText(tr("move_up"))
        self._down_btn.setText(tr("move_down"))
        self._out_name_label.setText(tr("merge_output_name") + ":")
        self._file_list.setToolTip(tr("merge_files"))

    def title_key(self):
        return "tab_merge"

    def desc_key(self):
        return "merge_desc"


# ===========================================================================
# 2. 拆分 PDF 面板 / Split Panel
# ===========================================================================

class SplitPanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        # 源文件选择 / Source file
        src_row = QHBoxLayout()
        self._src_label = QLabel()
        self._src_edit = QLineEdit()
        self._src_edit.setReadOnly(True)
        self._src_btn = QPushButton()
        self._src_btn.clicked.connect(self._pick_source)
        src_row.addWidget(self._src_label)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(self._src_btn)
        self._content.addLayout(src_row)

        # 模式选择 / Mode
        mode_row = QHBoxLayout()
        self._mode_label = QLabel()
        self._mode_each = QRadioButton()
        self._mode_each.setChecked(True)
        self._mode_range = QRadioButton()
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._mode_each)
        self._mode_group.addButton(self._mode_range)
        self._mode_each.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self._mode_label)
        mode_row.addWidget(self._mode_each)
        mode_row.addWidget(self._mode_range)
        mode_row.addStretch(1)
        self._content.addLayout(mode_row)

        # 范围输入 / Ranges input
        range_row = QHBoxLayout()
        self._range_label = QLabel()
        self._range_edit = QLineEdit()
        self._range_edit.setPlaceholderText("1-3,5,7-9")
        range_row.addWidget(self._range_label)
        range_row.addWidget(self._range_edit, 1)
        self._content.addLayout(range_row)

        # 前缀 / Prefix
        prefix_row = QHBoxLayout()
        self._prefix_label = QLabel()
        self._prefix_edit = QLineEdit("page")
        prefix_row.addWidget(self._prefix_label)
        prefix_row.addWidget(self._prefix_edit, 1)
        self._content.addLayout(prefix_row)

        # 输出目录 / Output dir
        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

    def _pick_source(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if f:
            self._src_edit.setText(f)
            # 默认前缀: 原名_split / Default prefix: base_split
            base = os.path.splitext(os.path.basename(f))[0]
            self._prefix_edit.setText(f"{base}_split")

    def _on_mode_change(self):
        is_range = self._mode_range.isChecked()
        self._range_edit.setEnabled(is_range)
        self._range_label.setEnabled(is_range)

    def on_execute(self):
        src = self._src_edit.text().strip()
        if not src:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        mode = "ranges" if self._mode_range.isChecked() else "each"
        ranges = self._range_edit.text().strip()
        if mode == "ranges" and not ranges:
            QMessageBox.warning(self, tr("invalid_input"),
                                tr("split_ranges_hint"))
            return
        prefix = self._prefix_edit.text().strip() or "page"
        self.start_worker(pdf_core.split_pdf, src, out_dir, mode, ranges, prefix)

    def on_success(self, result):
        QMessageBox.information(
            self, tr("success"), tr("split_success", n=len(result)))

    def _do_retranslate(self):
        self._src_label.setText(tr("split_source") + ":")
        self._src_btn.setText(tr("browse"))
        self._mode_label.setText(tr("split_mode") + ":")
        self._mode_each.setText(tr("split_each_page"))
        self._mode_range.setText(tr("split_by_range"))
        self._range_label.setText(tr("split_ranges_hint"))
        self._prefix_label.setText(tr("split_prefix") + ":")
        self._on_mode_change()

    def title_key(self):
        return "tab_split"

    def desc_key(self):
        return "split_desc"


# ===========================================================================
# 3. 压缩 PDF 面板 / Compress Panel
# ===========================================================================

class CompressPanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        # 源文件
        src_row = QHBoxLayout()
        self._src_label = QLabel()
        self._src_edit = QLineEdit()
        self._src_edit.setReadOnly(True)
        self._src_btn = QPushButton()
        self._src_btn.clicked.connect(self._pick_source)
        src_row.addWidget(self._src_label)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(self._src_btn)
        self._content.addLayout(src_row)

        # 质量与 DPI
        q_row = QHBoxLayout()
        self._q_label = QLabel()
        self._q_spin = QSpinBox()
        self._q_spin.setRange(1, 100)
        self._q_spin.setValue(60)
        q_row.addWidget(self._q_label)
        q_row.addWidget(self._q_spin)
        q_row.addSpacing(30)
        self._dpi_label = QLabel()
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(36, 600)
        self._dpi_spin.setValue(96)
        q_row.addWidget(self._dpi_label)
        q_row.addWidget(self._dpi_spin)
        q_row.addStretch(1)
        self._content.addLayout(q_row)

        # 输出目录 + 文件名
        name_row = QHBoxLayout()
        self._name_label = QLabel()
        self._name_edit = QLineEdit("compressed.pdf")
        name_row.addWidget(self._name_label)
        name_row.addWidget(self._name_edit, 1)
        self._content.addLayout(name_row)

        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

        # 大小信息 / Size info
        self._size_info = QLabel()
        self._size_info.setStyleSheet("color:#27ae60; font-weight:bold;")
        self._content.addWidget(self._size_info)

    def _pick_source(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if f:
            self._src_edit.setText(f)
            self._name_edit.setText(_default_output_name(f, "compressed"))
            try:
                self._size_info.setText(
                    f"{tr('compress_original')}: {pdf_core.file_size_str(f)}")
            except Exception:
                pass

    def on_execute(self):
        src = self._src_edit.text().strip()
        if not src:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        name = self._name_edit.text().strip() or "compressed.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        out_path = os.path.join(out_dir, name)
        if os.path.abspath(out_path) == os.path.abspath(src):
            QMessageBox.warning(self, tr("invalid_input"), tr("err_same_output"))
            return
        self.start_worker(pdf_core.compress_pdf, src, out_path,
                          self._q_spin.value(), self._dpi_spin.value())

    def on_success(self, result):
        orig, new = result
        ratio = (new / orig * 100) if orig > 0 else 0
        msg = tr("compress_success",
                 old=f"{orig/1024/1024:.2f} MB",
                 new=f"{new/1024/1024:.2f} MB")
        self._size_info.setText(
            f"{tr('compress_original')}: {orig/1024/1024:.2f} MB | "
            f"{tr('compress_compressed')}: {new/1024/1024:.2f} MB | "
            f"{tr('compress_ratio')}: {ratio:.1f}%")
        QMessageBox.information(self, tr("success"), msg)

    def _do_retranslate(self):
        self._src_label.setText(tr("compress_source") + ":")
        self._src_btn.setText(tr("browse"))
        self._q_label.setText(tr("compress_quality"))
        self._dpi_label.setText(tr("compress_dpi"))
        self._name_label.setText(tr("merge_output_name") + ":")
        if self._src_edit.text():
            try:
                self._size_info.setText(
                    f"{tr('compress_original')}: "
                    f"{pdf_core.file_size_str(self._src_edit.text())}")
            except Exception:
                pass

    def title_key(self):
        return "tab_compress"

    def desc_key(self):
        return "compress_desc"


# ===========================================================================
# 4. 旋转 PDF 面板 / Rotate Panel
# ===========================================================================

class RotatePanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        # 源文件
        src_row = QHBoxLayout()
        self._src_label = QLabel()
        self._src_edit = QLineEdit()
        self._src_edit.setReadOnly(True)
        self._src_btn = QPushButton()
        self._src_btn.clicked.connect(self._pick_source)
        src_row.addWidget(self._src_label)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(self._src_btn)
        self._content.addLayout(src_row)

        # 角度选择
        ang_row = QHBoxLayout()
        self._ang_label = QLabel()
        self._ang_combo = QComboBox()
        self._ang_combo.addItem("90°", 90)
        self._ang_combo.addItem("180°", 180)
        self._ang_combo.addItem("270°", 270)
        ang_row.addWidget(self._ang_label)
        ang_row.addWidget(self._ang_combo)
        ang_row.addStretch(1)
        self._content.addLayout(ang_row)

        # 页面范围
        pg_row = QHBoxLayout()
        self._pg_label = QLabel()
        self._pg_edit = QLineEdit()
        self._pg_edit.setPlaceholderText("1-3,5")
        pg_row.addWidget(self._pg_label)
        pg_row.addWidget(self._pg_edit, 1)
        self._content.addLayout(pg_row)

        # 输出
        name_row = QHBoxLayout()
        self._name_label = QLabel()
        self._name_edit = QLineEdit("rotated.pdf")
        name_row.addWidget(self._name_label)
        name_row.addWidget(self._name_edit, 1)
        self._content.addLayout(name_row)

        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

    def _pick_source(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if f:
            self._src_edit.setText(f)
            self._name_edit.setText(_default_output_name(f, "rotated"))

    def on_execute(self):
        src = self._src_edit.text().strip()
        if not src:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        name = self._name_edit.text().strip() or "rotated.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        out_path = os.path.join(out_dir, name)
        angle = self._ang_combo.currentData()
        pages = self._pg_edit.text().strip()
        self.start_worker(pdf_core.rotate_pdf, src, out_path, angle, pages)

    def on_success(self, result):
        QMessageBox.information(self, tr("success"), tr("rotate_success"))

    def _do_retranslate(self):
        self._src_label.setText(tr("compress_source") + ":")
        self._src_btn.setText(tr("browse"))
        self._ang_label.setText(tr("rotate_angle") + ":")
        # 重新填充下拉项文本
        self._ang_combo.setItemText(0, tr("rotate_90"))
        self._ang_combo.setItemText(1, tr("rotate_180"))
        self._ang_combo.setItemText(2, tr("rotate_270"))
        self._pg_label.setText(tr("rotate_pages") + ":")
        self._name_label.setText(tr("merge_output_name") + ":")

    def title_key(self):
        return "tab_rotate"

    def desc_key(self):
        return "rotate_desc"


# ===========================================================================
# 5. 提取页面 面板 / Extract Panel
# ===========================================================================

class ExtractPanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        src_row = QHBoxLayout()
        self._src_label = QLabel()
        self._src_edit = QLineEdit()
        self._src_edit.setReadOnly(True)
        self._src_btn = QPushButton()
        self._src_btn.clicked.connect(self._pick_source)
        src_row.addWidget(self._src_label)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(self._src_btn)
        self._content.addLayout(src_row)

        pg_row = QHBoxLayout()
        self._pg_label = QLabel()
        self._pg_edit = QLineEdit()
        self._pg_edit.setPlaceholderText("1-3,5,7-9")
        pg_row.addWidget(self._pg_label)
        pg_row.addWidget(self._pg_edit, 1)
        self._content.addLayout(pg_row)

        name_row = QHBoxLayout()
        self._name_label = QLabel()
        self._name_edit = QLineEdit("extracted.pdf")
        name_row.addWidget(self._name_label)
        name_row.addWidget(self._name_edit, 1)
        self._content.addLayout(name_row)

        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

    def _pick_source(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if f:
            self._src_edit.setText(f)
            self._name_edit.setText(_default_output_name(f, "extracted"))

    def on_execute(self):
        src = self._src_edit.text().strip()
        if not src:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        pages = self._pg_edit.text().strip()
        if not pages:
            QMessageBox.warning(self, tr("invalid_input"), tr("extract_pages"))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        name = self._name_edit.text().strip() or "extracted.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        out_path = os.path.join(out_dir, name)
        self.start_worker(pdf_core.extract_pages, src, out_path, pages)

    def on_success(self, result):
        QMessageBox.information(
            self, tr("success"), tr("extract_success", n=result))

    def _do_retranslate(self):
        self._src_label.setText(tr("extract_source") + ":")
        self._src_btn.setText(tr("browse"))
        self._pg_label.setText(tr("extract_pages") + ":")
        self._name_label.setText(tr("extract_output") + ":")

    def title_key(self):
        return "tab_extract"

    def desc_key(self):
        return "extract_desc"


# ===========================================================================
# 6. 页面管理 面板 / Organize Panel
# ===========================================================================

class PageThumbnail(QLabel):
    """单个页面缩略图控件，支持右键菜单、拖拽排序、多选。"""
    rotateRequested = pyqtSignal(int)    # new_index
    deleteRequested = pyqtSignal(int)
    extractRequested = pyqtSignal(int)
    dragDropped = pyqtSignal(int, int)   # from_idx, to_idx
    selectionToggled = pyqtSignal(int, bool)  # new_idx, selected

    def __init__(self, page_idx: int, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.page_idx = page_idx
        self.setPixmap(pixmap)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(180, 240)
        self.setMaximumSize(180, 240)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"#{page_idx + 1}")
        self.setAcceptDrops(True)
        self._drag_start = None
        self._selected = False
        self._multi_select_mode = False  # 由父面板设置 / set by parent
        self._apply_frame()

    def set_multi_select_mode(self, enabled: bool):
        self._multi_select_mode = enabled
        if not enabled:
            self.set_selected(False)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_frame()

    def is_selected(self) -> bool:
        return self._selected

    def _apply_frame(self):
        if self._selected:
            self.setStyleSheet(
                "border: 3px solid #e74c3c; background: #fdeaea;")
        else:
            self.setStyleSheet(
                "border: 1px solid #bdc3c7; background: #ffffff;")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self._multi_select_mode:
                # 多选模式: 点击切换选中 / Toggle selection
                self.set_selected(not self._selected)
                self.selectionToggled.emit(self.page_idx, self._selected)
            else:
                self._drag_start = e.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # 多选模式下禁用拖拽 / Disable drag in multi-select mode
        if self._multi_select_mode:
            return
        if self._drag_start and (e.pos() - self._drag_start).manhattanLength() > 10:
            from PyQt5.QtCore import QMimeData
            from PyQt5.QtGui import QDrag
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self.page_idx))
            drag.setMimeData(mime)
            drag.exec_(Qt.MoveAction)
        super().mouseMoveEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText() and not self._multi_select_mode:
            e.acceptProposedAction()

    def dropEvent(self, e):
        if self._multi_select_mode:
            return
        try:
            from_idx = int(e.mimeData().text())
        except ValueError:
            return
        if from_idx != self.page_idx:
            self.dragDropped.emit(from_idx, self.page_idx)
        e.acceptProposedAction()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        act_rot = QAction(tr("organize_rotate_page"), menu)
        act_del = QAction(tr("organize_delete_page"), menu)
        act_ext = QAction(tr("organize_extract_page"), menu)
        act_rot.triggered.connect(lambda: self.rotateRequested.emit(self.page_idx))
        act_del.triggered.connect(lambda: self.deleteRequested.emit(self.page_idx))
        act_ext.triggered.connect(lambda: self.extractRequested.emit(self.page_idx))
        menu.addAction(act_rot)
        menu.addAction(act_del)
        menu.addAction(act_ext)
        menu.exec_(e.globalPos())


class OrganizePanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._src_path = ""
        self._order: List[int] = []  # 当前顺序(指向原 PDF 页索引)
        self._deleted: set = set()
        self._rotations: dict = {}   # {new_idx: angle}
        self._selected: set = set()  # 多选模式下选中的 new_idx
        self._multi_select = False
        self._thumb_cache: dict = {}      # {orig_page_idx: QPixmap}
        self._thumb_widgets: dict = {}    # {orig_page_idx: PageThumbnail}
        self._thumb_loader: _ThumbLoader = None
        # 本面板使用顶部的"保存"按钮，隐藏底部默认执行按钮
        self._run_btn.setVisible(False)
        self._progress.setVisible(False)
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        # 顶部: 加载 + 保存 + 多选切换 + 批量删除 + 状态
        top = QHBoxLayout()
        self._load_btn = QPushButton()
        self._load_btn.clicked.connect(self._load_pdf)
        self._save_btn = QPushButton()
        self._save_btn.clicked.connect(self._save_pdf)
        self._multi_cb = QCheckBox()
        self._multi_cb.toggled.connect(self._on_multi_toggle)
        self._batch_del_btn = QPushButton()
        self._batch_del_btn.clicked.connect(self._batch_delete)
        self._batch_del_btn.setEnabled(False)
        self._status = QLabel()
        top.addWidget(self._load_btn)
        top.addWidget(self._save_btn)
        top.addWidget(self._multi_cb)
        top.addWidget(self._batch_del_btn)
        top.addStretch(1)
        top.addWidget(self._status)
        self._content.addLayout(top)

        # 缩略图滚动区 / Thumbnail scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(10)
        self._grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._scroll.setWidget(self._grid_container)
        self._content.addWidget(self._scroll, 1)

        # 输出目录
        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

    def _on_multi_toggle(self, checked):
        self._multi_select = checked
        self._selected.clear()
        self._render_thumbnails()
        self._update_batch_btn()
        self._status.setText(tr("batch_select_hint") if checked else "")

    def _update_batch_btn(self):
        n = len(self._selected)
        self._batch_del_btn.setText(
            tr("batch_delete") + f" ({n})" if n else tr("batch_delete"))
        self._batch_del_btn.setEnabled(n > 0)

    def _on_selection_toggled(self, new_idx, selected):
        if selected:
            self._selected.add(new_idx)
        else:
            self._selected.discard(new_idx)
        self._update_batch_btn()

    def _batch_delete(self):
        if not self._selected:
            return
        n = len(self._selected)
        if QMessageBox.question(
                self, tr("batch_delete"),
                tr("batch_confirm", n=n)) != QMessageBox.Yes:
            return
        # 从大到小删除，避免索引错位 / Delete descending to keep indices valid
        for idx in sorted(self._selected, reverse=True):
            self._on_delete(idx)
        self._selected.clear()
        self._update_batch_btn()
        log_info(f"[Organize] batch deleted {n} pages")

    def _load_pdf(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if not f:
            return
        try:
            info = pdf_core.get_pdf_info(f)
        except Exception as e:
            QMessageBox.critical(self, tr("failed"), str(e))
            return
        # 取消上一个加载器 / Cancel previous loader
        if self._thumb_loader and self._thumb_loader.isRunning():
            self._thumb_loader.cancel()
            self._thumb_loader.quit()
            self._thumb_loader.wait(500)
        self._src_path = f
        self._order = list(range(info["pages"]))
        self._deleted = set()
        self._rotations = {}
        self._thumb_cache = {}
        self._thumb_widgets = {}
        self._render_thumbnails()
        self._status.setText(
            tr("organize_loaded", name=os.path.basename(f), n=info["pages"]))
        log_info(f"[Organize] loaded {os.path.basename(f)} "
                 f"({info['pages']} pages), loading thumbnails in background")
        # 后台加载缩略图 / Background load thumbnails
        self._thumb_loader = _ThumbLoader(f, list(self._order))
        self._thumb_loader.thumb_ready.connect(self._on_thumb_ready)
        self._thumb_loader.progress.connect(self._on_thumb_progress)
        self._thumb_loader.start()

    def _on_thumb_ready(self, orig_idx, image):
        """单页缩略图加载完成。"""
        pix = QPixmap.fromImage(image)
        self._thumb_cache[orig_idx] = pix
        widget = self._thumb_widgets.get(orig_idx)
        if widget:
            widget.setPixmap(pix)

    def _on_thumb_progress(self, current, total):
        if total > 0 and current < total:
            self._status.setText(
                f"{tr('organize_load')}... {current}/{total}")
        elif total > 0:
            self._status.setText("")

    def _render_thumbnails(self):
        # 清空 / Clear
        self._thumb_widgets = {}
        while self._grid.count():
            it = self._grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        if not self._src_path or not self._order:
            return
        cols = 5
        for new_idx, orig_idx in enumerate(self._order):
            # 优先用缓存，否则占位 (后台加载器会回填) / Use cache or placeholder
            pix = self._thumb_cache.get(orig_idx, QPixmap())
            # 标签: 序号 + 原页码 / Label: new index + original page
            wrap = QWidget()
            wlay = QVBoxLayout(wrap)
            wlay.setContentsMargins(0, 0, 0, 0)
            wlay.setSpacing(2)
            thumb = PageThumbnail(new_idx, pix)
            thumb.set_multi_select_mode(self._multi_select)
            thumb.rotateRequested.connect(self._on_rotate)
            thumb.deleteRequested.connect(self._on_delete)
            thumb.extractRequested.connect(self._on_extract)
            thumb.dragDropped.connect(self._on_drop)
            thumb.selectionToggled.connect(self._on_selection_toggled)
            # 登记 widget 以便后台回填 / Register widget for background fill
            self._thumb_widgets[orig_idx] = thumb
            lbl = QLabel(f"#{new_idx + 1} (p{orig_idx + 1})")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#34495e; font-size:11px;")
            wlay.addWidget(thumb)
            wlay.addWidget(lbl)
            r, c = divmod(new_idx, cols)
            self._grid.addWidget(wrap, r, c)

    def _on_rotate(self, new_idx):
        self._rotations[new_idx] = (self._rotations.get(new_idx, 0) + 90) % 360
        self._render_thumbnails()

    def _on_delete(self, new_idx):
        if new_idx < 0 or new_idx >= len(self._order):
            return
        del self._order[new_idx]
        # 旋转字典重新映射 / Reindex rotations
        new_rot = {}
        for k, v in self._rotations.items():
            if k < new_idx:
                new_rot[k] = v
            elif k > new_idx:
                new_rot[k - 1] = v
        self._rotations = new_rot
        self._render_thumbnails()

    def _on_extract(self, new_idx):
        if new_idx < 0 or new_idx >= len(self._order):
            return
        orig_idx = self._order[new_idx]
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        out_path = os.path.join(out_dir, f"page_{orig_idx + 1}.pdf")
        try:
            pdf_core.extract_pages(self._src_path, out_path,
                                   str(orig_idx + 1))
            QMessageBox.information(self, tr("success"), tr("extract_success", n=1))
        except Exception as e:
            QMessageBox.critical(self, tr("failed"), str(e))

    def _on_drop(self, from_idx, to_idx):
        if 0 <= from_idx < len(self._order) and 0 <= to_idx < len(self._order):
            item = self._order.pop(from_idx)
            self._order.insert(to_idx, item)
            # 旋转跟随移动 / Move rotations too
            new_rot = {}
            for k, v in self._rotations.items():
                if k == from_idx:
                    new_rot[to_idx] = v
                elif from_idx < k <= to_idx:
                    new_rot[k - 1] = v
                elif to_idx <= k < from_idx:
                    new_rot[k + 1] = v
                else:
                    new_rot[k] = v
            self._rotations = new_rot
            self._render_thumbnails()

    def _save_pdf(self):
        if not self._src_path or not self._order:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        out_path = os.path.join(
            out_dir, _default_output_name(self._src_path, "organized"))
        self.start_worker(pdf_core.reorganize_pdf, self._src_path, out_path,
                          list(self._order), dict(self._rotations))

    def on_success(self, result):
        QMessageBox.information(self, tr("success"), tr("organize_success"))

    def _do_retranslate(self):
        self._load_btn.setText(tr("organize_load"))
        self._save_btn.setText(tr("organize_save"))
        self._multi_cb.setText(tr("batch_select"))
        self._batch_del_btn.setText(tr("batch_delete"))
        self._update_batch_btn()

    def title_key(self):
        return "tab_organize"

    def desc_key(self):
        return "organize_desc"

    def run_button_key(self):
        # 此面板用单独的保存按钮，隐藏默认执行按钮
        return "organize_save"


# ===========================================================================
# 7. 页面检测 面板 / Detect Panel
# ===========================================================================

class DetectPanel(BasePanel):
    """扫描空白页与重复页，标记可疑页面，支持批量删除。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._src_path = ""
        self._total_pages = 0
        self._blanks: List[int] = []        # 0-based
        self._dup_groups: List[List[int]] = []  # 每组 0-based 列表
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        # 源文件选择 / Source file
        src_row = QHBoxLayout()
        self._src_label = QLabel()
        self._src_edit = QLineEdit()
        self._src_edit.setReadOnly(True)
        self._src_btn = QPushButton()
        self._src_btn.clicked.connect(self._pick_source)
        src_row.addWidget(self._src_label)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(self._src_btn)
        self._content.addLayout(src_row)

        # 阈值参数 / Threshold params
        param_row = QHBoxLayout()
        self._blank_thr_label = QLabel()
        self._blank_thr = QSpinBox()
        self._blank_thr.setRange(0, 100)
        self._blank_thr.setValue(99)
        self._blank_thr.setSuffix(" %")
        self._blank_thr.setToolTip(tr("detect_blank_tip"))
        self._blank_thr_label.setToolTip(tr("detect_blank_tip"))
        self._dup_thr_label = QLabel()
        self._dup_thr = QSpinBox()
        self._dup_thr.setRange(0, 64)
        self._dup_thr.setValue(5)
        param_row.addWidget(self._blank_thr_label)
        param_row.addWidget(self._blank_thr)
        param_row.addSpacing(20)
        param_row.addWidget(self._dup_thr_label)
        param_row.addWidget(self._dup_thr)
        param_row.addStretch(1)
        self._content.addLayout(param_row)

        # 检测按钮 / Detect buttons
        detect_row = QHBoxLayout()
        self._detect_all_btn = QPushButton()
        self._detect_all_btn.clicked.connect(self._detect_all)
        self._detect_blank_btn = QPushButton()
        self._detect_blank_btn.clicked.connect(self._detect_blank)
        self._detect_dup_btn = QPushButton()
        self._detect_dup_btn.clicked.connect(self._detect_dup)
        for b in (self._detect_all_btn, self._detect_blank_btn,
                  self._detect_dup_btn):
            b.setStyleSheet(
                "QPushButton{background:#27ae60; color:white; border:none;"
                "border-radius:4px; padding:6px 14px; font-weight:bold;}"
                "QPushButton:hover{background:#229954;}"
                "QPushButton:disabled{background:#bdc3c7;}")
            detect_row.addWidget(b)
        detect_row.addStretch(1)
        self._content.addLayout(detect_row)

        # 结果表格 + 预览 分栏 / Results table + preview splitter
        splitter = QSplitter(Qt.Horizontal)
        # 表格 / Table
        self._table = QTableWidget(0, 4)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._on_table_selection)
        splitter.addWidget(self._table)

        # 预览区 / Preview pane
        preview_widget = QWidget()
        pv = QVBoxLayout(preview_widget)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(4)
        self._preview_title = QLabel()
        self._preview_title.setStyleSheet(
            "font-weight:bold; color:#2c3e50;")
        pv.addWidget(self._preview_title)
        # 预览图 (可滚动) / Preview image (scrollable)
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setAlignment(Qt.AlignCenter)
        self._preview_label = QLabel(tr("preview_hint"))
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumWidth(360)
        self._preview_label.setStyleSheet("color:#95a5a6; background:#ffffff;")
        self._preview_scroll.setWidget(self._preview_label)
        pv.addWidget(self._preview_scroll, 1)
        # 统计信息 / Stats
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(
            "background:#34495e; color:#ecf0f1; padding:8px;"
            "border-radius:4px; font-family:Consolas;")
        self._stats_label.setWordWrap(True)
        pv.addWidget(self._stats_label)
        # 上一页/下一页 / Prev/Next
        nav_row = QHBoxLayout()
        self._prev_btn = QPushButton()
        self._prev_btn.clicked.connect(lambda: self._navigate(-1))
        self._next_btn = QPushButton()
        self._next_btn.clicked.connect(lambda: self._navigate(1))
        nav_row.addWidget(self._prev_btn)
        nav_row.addWidget(self._next_btn)
        pv.addLayout(nav_row)
        splitter.addWidget(preview_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self._content.addWidget(splitter, 1)
        self._preview_worker = None
        self._preview_cache = {}  # {page_idx: (QPixmap, stats)}

        # 选择 + 删除 + 导出 / Select + delete + export
        action_row = QHBoxLayout()
        self._sel_all_blank_btn = QPushButton()
        self._sel_all_blank_btn.clicked.connect(self._select_all_blank)
        self._sel_all_dup_btn = QPushButton()
        self._sel_all_dup_btn.clicked.connect(self._select_all_dup)
        self._sel_none_btn = QPushButton()
        self._sel_none_btn.clicked.connect(self._select_none)
        self._marked_label = QLabel()
        self._del_btn = QPushButton()
        self._del_btn.clicked.connect(self._delete_selected)
        self._del_btn.setStyleSheet(
            "QPushButton{background:#e74c3c; color:white; border:none;"
            "border-radius:4px; padding:6px 14px; font-weight:bold;}"
            "QPushButton:hover{background:#c0392b;}"
            "QPushButton:disabled{background:#bdc3c7;}")
        self._export_btn = QPushButton()
        self._export_btn.clicked.connect(self._export_report)
        action_row.addWidget(self._sel_all_blank_btn)
        action_row.addWidget(self._sel_all_dup_btn)
        action_row.addWidget(self._sel_none_btn)
        action_row.addStretch(1)
        action_row.addWidget(self._marked_label)
        action_row.addWidget(self._export_btn)
        action_row.addWidget(self._del_btn)
        self._content.addLayout(action_row)

        # 输出目录 (用于删除后输出) / Output dir
        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

        # 表格勾选变化时更新计数 / Update count on checkbox change
        self._table.itemChanged.connect(self._on_table_item_changed)

    # --- 文件选择 / File pick ---
    def _pick_source(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if not f:
            return
        try:
            info = pdf_core.get_pdf_info(f)
        except Exception as e:
            QMessageBox.critical(self, tr("failed"), str(e))
            return
        self._src_path = f
        self._total_pages = info["pages"]
        self._blanks = []
        self._dup_groups = []
        self._src_edit.setText(f)
        self._table.setRowCount(0)
        log_info(f"[Detect] loaded {os.path.basename(f)} ({info['pages']} pages)")

    # --- 检测 / Detection ---
    def _detect_blank(self):
        if not self._check_source():
            return
        self._blanks = []
        self._run_detection("blank")

    def _detect_dup(self):
        if not self._check_source():
            return
        self._dup_groups = []
        self._run_detection("dup")

    def _detect_all(self):
        if not self._check_source():
            return
        self._blanks = []
        self._dup_groups = []
        self._run_detection("all")

    def _check_source(self) -> bool:
        if not self._src_path:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return False
        return True

    def _run_detection(self, mode: str):
        """串行执行检测任务 (每个检测单独 worker)。"""
        self._detect_mode = mode
        self._set_running(True)
        self._progress.setValue(0)
        self._progress.setVisible(True)

        if mode in ("blank", "all"):
            log_info(f"[Detect] start blank detection: {os.path.basename(self._src_path)}")
            self._worker = PDFWorker(
                pdf_core.detect_blank_pages, self._src_path,
                float(self._blank_thr.value()))
            self._worker.progress.connect(self._on_progress)
            self._worker.finished_ok.connect(self._on_blank_done)
            self._worker.failed.connect(self._on_failed)
            self._worker.start()
        elif mode == "dup":
            self._detect_dup_only()

    def _on_blank_done(self, result):
        self._blanks = result
        if result:
            log_warn(f"[Detect] found {len(result)} blank pages: "
                     f"{[p+1 for p in result]}")
        else:
            log_info("[Detect] no blank pages found")
        if self._detect_mode == "all":
            self._detect_dup_only()
        else:
            self._finish_detection()

    def _detect_dup_only(self):
        log_info(f"[Detect] start duplicate detection: {os.path.basename(self._src_path)}")
        self._worker = PDFWorker(
            pdf_core.detect_duplicate_pages, self._src_path,
            self._dup_thr.value())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_dup_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_dup_done(self, result):
        self._dup_groups = result
        if result:
            log_warn(f"[Detect] found {len(result)} duplicate groups")
            for i, g in enumerate(result):
                log_warn(f"[Detect] group {i+1}: pages {[p+1 for p in g]}")
        else:
            log_info("[Detect] no duplicate pages found")
        self._finish_detection()

    def _finish_detection(self):
        self._set_running(False)
        self._progress.setVisible(False)
        self._populate_table()

    # --- 结果表格 / Results table ---
    def _populate_table(self):
        self._table.itemChanged.disconnect(self._on_table_item_changed)
        self._table.setRowCount(0)
        # 空白页行 / Blank page rows
        for p in self._blanks:
            self._add_result_row(p, tr("detect_blank_tag"),
                                 "BLANK", QColor("#e67e22"))
        # 重复页行 / Duplicate page rows
        for gi, group in enumerate(self._dup_groups):
            tag = tr("detect_dup_group", g=gi + 1, n=len(group))
            for p in group:
                self._add_result_row(p, tag, "DUP", QColor("#9b59b6"))
        self._table.itemChanged.connect(self._on_table_item_changed)
        self._update_marked_count()

    def _add_result_row(self, page_idx: int, tag: str, kind: str, color: QColor):
        r = self._table.rowCount()
        self._table.insertRow(r)
        # 复选框 / Checkbox
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk_item.setCheckState(Qt.Unchecked)
        # 页码 (1-based 显示) / Page number (1-based display)
        page_item = QTableWidgetItem(f"p{page_idx + 1}")
        page_item.setForeground(color)
        page_item.setData(Qt.UserRole, page_idx)  # 存 0-based
        # 类型 / Kind
        kind_item = QTableWidgetItem(kind)
        kind_item.setForeground(color)
        # 说明 / Description
        desc_item = QTableWidgetItem(tag)
        self._table.setItem(r, 0, chk_item)
        self._table.setItem(r, 1, page_item)
        self._table.setItem(r, 2, kind_item)
        self._table.setItem(r, 3, desc_item)

    def _on_table_item_changed(self, item):
        if item.column() == 0:
            self._update_marked_count()

    def _collect_checked_pages(self) -> List[int]:
        pages = []
        for r in range(self._table.rowCount()):
            chk = self._table.item(r, 0)
            page_item = self._table.item(r, 1)
            if chk and chk.checkState() == Qt.Checked and page_item:
                pages.append(page_item.data(Qt.UserRole))
        return pages

    def _update_marked_count(self):
        n = len(self._collect_checked_pages())
        self._marked_label.setText(tr("detect_marked_pages", n=n))
        self._del_btn.setEnabled(n > 0)

    def _select_all_blank(self):
        self._select_by_kind("BLANK", True)

    def _select_all_dup(self):
        # 每组只勾选除首页外的 (保留首页) / Check all except first in each group
        # 这里按 kind=DUP 全选非首页: 用 desc 是否含 "第1组" 之类不可靠，
        # 改为: 同组第二个起才勾选 / Check from 2nd in each group
        self._table.itemChanged.disconnect(self._on_table_item_changed)
        seen_groups = set()
        for r in range(self._table.rowCount()):
            kind_item = self._table.item(r, 2)
            desc_item = self._table.item(r, 3)
            chk_item = self._table.item(r, 0)
            if not (kind_item and desc_item and chk_item):
                continue
            if kind_item.text() != "DUP":
                continue
            tag = desc_item.text()
            # 每组首次出现标记组号，保留不勾 / Keep first of each group unchecked
            if tag not in seen_groups:
                seen_groups.add(tag)
                chk_item.setCheckState(Qt.Unchecked)
            else:
                chk_item.setCheckState(Qt.Checked)
        self._table.itemChanged.connect(self._on_table_item_changed)
        self._update_marked_count()

    def _select_by_kind(self, kind: str, checked: bool):
        self._table.itemChanged.disconnect(self._on_table_item_changed)
        for r in range(self._table.rowCount()):
            kind_item = self._table.item(r, 2)
            chk_item = self._table.item(r, 0)
            if kind_item and kind_item.text() == kind and chk_item:
                chk_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._table.itemChanged.connect(self._on_table_item_changed)
        self._update_marked_count()

    def _select_none(self):
        self._table.itemChanged.disconnect(self._on_table_item_changed)
        for r in range(self._table.rowCount()):
            chk_item = self._table.item(r, 0)
            if chk_item:
                chk_item.setCheckState(Qt.Unchecked)
        self._table.itemChanged.connect(self._on_table_item_changed)
        self._update_marked_count()

    def _delete_selected(self):
        pages = self._collect_checked_pages()
        if not pages:
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        name = os.path.splitext(os.path.basename(self._src_path))[0] + "_cleaned.pdf"
        out_path = os.path.join(out_dir, name)
        if os.path.abspath(out_path) == os.path.abspath(self._src_path):
            QMessageBox.warning(self, tr("invalid_input"), tr("err_same_output"))
            return
        n_del = len(pages)
        log_info(f"[Detect] deleting {n_del} pages: {[p+1 for p in pages]}")
        self._pending_del_count = n_del
        self.start_worker(pdf_core.delete_pages, self._src_path, out_path, pages)

    def on_success(self, result):
        # result = 新 PDF 页数
        n_del = getattr(self, "_pending_del_count", 0)
        QMessageBox.information(
            self, tr("success"),
            tr("detect_delete_success", n=n_del, m=result))
        log_info(f"[Detect] deleted {n_del} pages, output has {result} pages")

    def _export_report(self):
        if self._table.rowCount() == 0:
            QMessageBox.information(self, tr("detect_results"),
                                    tr("detect_no_result"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("detect_export"), "detection_report.txt",
            "Text (*.txt);;All (*.*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"PDF Detection Report\n")
                f.write(f"File: {self._src_path}\n")
                f.write(f"Total pages: {self._total_pages}\n")
                f.write(f"Blank pages ({len(self._blanks)}): "
                        f"{[p+1 for p in self._blanks]}\n")
                f.write(f"Duplicate groups ({len(self._dup_groups)}):\n")
                for i, g in enumerate(self._dup_groups):
                    f.write(f"  Group {i+1}: {[p+1 for p in g]}\n")
            log_info(f"[Detect] report exported to {path}")
            QMessageBox.information(self, tr("success"), path)
        except Exception as e:
            log_error(f"[Detect] export failed: {e}")
            QMessageBox.critical(self, tr("failed"), str(e))

    # --- 页面预览 / Page Preview ---
    def _on_table_selection(self):
        """表格行选中变化时，预览该页。"""
        items = self._table.selectedItems()
        if not items:
            return
        row = items[0].row()
        page_item = self._table.item(row, 1)
        if not page_item:
            return
        page_idx = page_item.data(Qt.UserRole)
        if page_idx is None:
            return
        self._request_preview(page_idx)

    def _navigate(self, delta):
        """上一页/下一页 (基于当前预览页)。"""
        cur = getattr(self, "_cur_preview_idx", None)
        if cur is None:
            return
        new_idx = cur + delta
        if 0 <= new_idx < self._total_pages:
            self._request_preview(new_idx)

    def _request_preview(self, page_idx: int):
        """请求预览某页 (有缓存直接用，否则后台渲染)。"""
        self._cur_preview_idx = page_idx
        self._preview_title.setText(
            tr("preview_page", n=page_idx + 1, t=self._total_pages))
        self._prev_btn.setEnabled(page_idx > 0)
        self._next_btn.setEnabled(page_idx < self._total_pages - 1)

        # 命中缓存 / Cache hit
        if page_idx in self._preview_cache:
            pix, stats = self._preview_cache[page_idx]
            self._show_preview(pix, stats)
            return

        # 显示加载中 / Show loading
        self._preview_label.setText(tr("preview_loading"))
        self._preview_label.setPixmap(QPixmap())
        self._stats_label.setText("")

        # 取消上一个 worker / Cancel previous worker
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.quit()
            self._preview_worker.wait(500)

        self._preview_worker = _PreviewWorker(self._src_path, page_idx)
        self._preview_worker.preview_ready.connect(self._on_preview_ready)
        self._preview_worker.start()

    def _on_preview_ready(self, page_idx, image, stats):
        """后台渲染完成回调。"""
        if page_idx != getattr(self, "_cur_preview_idx", None):
            return  # 已切到其他页，丢弃过期结果
        pix = QPixmap.fromImage(image)
        self._preview_cache[page_idx] = (pix, stats)
        self._show_preview(pix, stats)

    def _show_preview(self, pix: QPixmap, stats: dict):
        """显示预览图与统计。"""
        if pix.isNull():
            self._preview_label.setText(tr("failed"))
            self._preview_label.setPixmap(QPixmap())
        else:
            # 等比缩放到预览区宽度 / Scale to fit preview width
            w = self._preview_scroll.viewport().width() - 20
            if w < 200:
                w = 360
            scaled = pix.scaledToWidth(w, Qt.SmoothTransformation)
            self._preview_label.setPixmap(scaled)
            self._preview_label.setText("")
        # 统计文本 / Stats text
        is_blank = stats.get("is_blank", False)
        status = tr("preview_blank") if is_blank else tr("preview_normal")
        status_color = "#e74c3c" if is_blank else "#27ae60"
        self._stats_label.setText(
            f"<b>{tr('preview_whiteness')}</b>: {stats['white_ratio']:.1f}%　"
            f"<b>{tr('preview_mean')}</b>: {stats['mean']:.1f}　"
            f"<b>{tr('preview_std')}</b>: {stats['std']:.1f}<br>"
            f"<b>{tr('preview_status')}</b>: "
            f"<span style='color:{status_color};'>{status}</span>")

    # --- 翻译 / Translation ---
    def title_key(self):
        return "tab_detect"

    def desc_key(self):
        return "detect_desc"

    def _do_retranslate(self):
        self._src_label.setText(tr("detect_source") + ":")
        self._src_btn.setText(tr("browse"))
        self._blank_thr_label.setText(tr("detect_blank_thr"))
        self._blank_thr.setToolTip(tr("detect_blank_tip"))
        self._blank_thr_label.setToolTip(tr("detect_blank_tip"))
        self._dup_thr_label.setText(tr("detect_dup_thr"))
        self._detect_all_btn.setText(tr("detect_run_all"))
        self._detect_blank_btn.setText(tr("detect_run_blank"))
        self._detect_dup_btn.setText(tr("detect_run_dup"))
        self._preview_title.setText(tr("preview_title"))
        if getattr(self, "_cur_preview_idx", None) is not None:
            self._preview_title.setText(
                tr("preview_page", n=self._cur_preview_idx + 1,
                   t=self._total_pages))
        self._prev_btn.setText(tr("preview_prev"))
        self._next_btn.setText(tr("preview_next"))
        if getattr(self, "_cur_preview_idx", None) is None:
            self._preview_label.setText(tr("preview_hint"))
        # 表格表头 / Table headers
        self._table.setHorizontalHeaderLabels(
            ["✔", "Page / 页码", "Type / 类型", "Detail / 说明"])
        self._sel_all_blank_btn.setText(tr("detect_select_all_blank"))
        self._sel_all_dup_btn.setText(tr("detect_select_all_dup"))
        self._sel_none_btn.setText(tr("detect_select_none"))
        self._del_btn.setText(tr("detect_delete_sel"))
        self._export_btn.setText(tr("detect_export"))
        self._update_marked_count()


# ===========================================================================
# 8. 裁剪 PDF 面板 / Crop Panel
# ===========================================================================

class CropPreviewWidget(QWidget):
    """
    可视化裁剪框选控件：显示页面图像，鼠标拖拽框选裁剪区域。
    发出 crop_rect_changed(x0, y0, x1, y1) 信号 (PDF 点坐标)。
    """
    crop_rect_changed = pyqtSignal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None        # 显示用 QPixmap
        self._scale = 1.0          # 像素/PDF点
        self._page_w = 0           # 页面宽 (PDF 点)
        self._page_h = 0           # 页面高 (PDF 点)
        self._start = None         # 拖拽起点 (像素)
        self._end = None           # 拖拽终点 (像素)
        self._rect = None          # 最终选区 (像素 QRect)
        self._drawing = False
        self._moving = False       # 移动已有选区
        self._move_start = None    # 移动起点 (像素)
        self._move_rect_start = None  # 移动时的原始 rect
        # 固定裁剪尺寸 (像素 w, h)，None = 自由
        self._fixed_size: tuple = None
        self.setMouseTracking(True)
        self.setMinimumSize(420, 520)
        self.setStyleSheet("background:#2c3e50;")
        self.setCursor(Qt.CrossCursor)

    def set_fixed_crop_size(self, w_pt: float = None, h_pt: float = None):
        """
        锁定裁剪框大小。传入 (None, None) 恢复自由。
        固定后: 只允许移动框位置，不允许改变大小。
        """
        if w_pt is None or h_pt is None or self._scale <= 0:
            self._fixed_size = None
        else:
            self._fixed_size = (int(w_pt * self._scale), int(h_pt * self._scale))
        if self._fixed_size and self._rect:
            # 对齐当前选中到锁定尺寸 / Force rect to locked size
            fw, fh = self._fixed_size
            if self._rect.width() != fw or self._rect.height() != fh:
                cx = self._rect.x() + self._rect.width() // 2
                cy = self._rect.y() + self._rect.height() // 2
                self._rect = self._clamp_rect(QRect(cx - fw // 2, cy - fh // 2, fw, fh))
                self._emit_rect(self._rect)
        self.update()

    def set_page(self, pixmap: QPixmap, page_w: float, page_h: float,
                 scale: float, fixed_w_pt: float = None, fixed_h_pt: float = None):
        """
        设置页面图像与尺寸。可选传入固定裁剪宽高 (PDF 点)。
        """
        self._pixmap = pixmap
        self._page_w = page_w
        self._page_h = page_h
        self._scale = scale
        self._rect = None
        self._start = None
        self._end = None
        self.setFixedSize(pixmap.size())
        # 设置固定裁剪尺寸 / Set fixed crop size
        if fixed_w_pt and fixed_h_pt:
            self._fixed_size = (int(fixed_w_pt * self._scale),
                                int(fixed_h_pt * self._scale))
        else:
            self._fixed_size = None
        self.update()

    def reset(self):
        self._rect = None
        self._start = None
        self._end = None
        self._moving = False
        self._drawing = False
        self.update()
        self.crop_rect_changed.emit(0, 0, 0, 0)

    def set_initial_crop(self, x0_pt: float, y0_pt: float,
                         x1_pt: float, y1_pt: float):
        """设置初始裁剪区域 (PDF 点坐标)。若处于锁定尺寸模式，则按尺寸调整。"""
        if not self._pixmap or self._scale <= 0:
            return
        if self._fixed_size:
            # 锁定尺寸: 使用固定宽高，中心点在 (x0+x1)/2, (y0+y1)/2
            fw, fh = self._fixed_size
            cx = int((x0_pt + x1_pt) * self._scale / 2)
            cy = int((y0_pt + y1_pt) * self._scale / 2)
            r = QRect(cx - fw // 2, cy - fh // 2, fw, fh)
            self._rect = self._clamp_rect(r)
        else:
            px0 = max(0, int(x0_pt * self._scale))
            py0 = max(0, int(y0_pt * self._scale))
            px1 = min(self._pixmap.width(), int(x1_pt * self._scale))
            py1 = min(self._pixmap.height(), int(y1_pt * self._scale))
            if px1 - px0 > 5 and py1 - py0 > 5:
                self._rect = QRect(px0, py0, px1 - px0, py1 - py0)
        self._start = None
        self._end = None
        if self._rect:
            self._emit_rect(self._rect)
        self.update()

    def _clamp_rect(self, r: QRect) -> QRect:
        """将矩形限制在 pixmap 范围内。"""
        x = max(0, r.x())
        y = max(0, r.y())
        x2 = min(self._pixmap.width(), r.x() + r.width())
        y2 = min(self._pixmap.height(), r.y() + r.height())
        return QRect(x, y, x2 - x, y2 - y)

    def paintEvent(self, e):
        p = QPainter(self)
        if not self._pixmap:
            p.setPen(QColor("#ecf0f1"))
            p.drawText(self.rect(), Qt.AlignCenter, tr("crop_hint"))
            return
        p.drawPixmap(0, 0, self._pixmap)
        # 当前选区 / Current selection
        r = self._current_rect()
        if r and r.width() > 2 and r.height() > 2:
            # 暗化选区外 / Darken outside
            overlay = QColor(0, 0, 0, 110)
            p.setBrush(QBrush(overlay))
            p.setPen(Qt.NoPen)
            # 四周遮罩 / Four surrounding masks
            p.drawRect(0, 0, self.width(), r.top())
            p.drawRect(0, r.bottom() + 1, self.width(),
                       self.height() - r.bottom() - 1)
            p.drawRect(0, r.top(), r.left(), r.height())
            p.drawRect(r.right() + 1, r.top(),
                       self.width() - r.right() - 1, r.height())
            # 选区边框 / Selection border
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#3498db"), 2, Qt.DashLine))
            p.drawRect(r)
            # 尺寸标注 / Dimension label
            cw_pt = r.width() / self._scale
            ch_pt = r.height() / self._scale
            cw_mm = cw_pt * 25.4 / 72
            ch_mm = ch_pt * 25.4 / 72
            txt = f"{cw_pt:.0f}x{ch_pt:.0f} pt  ({cw_mm:.0f}x{ch_mm:.0f} mm)"
            p.setPen(QColor("#ffffff"))
            p.setFont(self.font())
            p.fillRect(r.left(), max(0, r.top() - 18),
                       p.fontMetrics().width(txt) + 8, 18,
                       QColor(52, 152, 219, 220))
            p.drawText(r.left() + 4, max(12, r.top() - 4), txt)

    def _current_rect(self):
        """返回当前显示的选区 (像素 QRect)。"""
        if self._rect:
            return self._rect
        if self._start and self._end:
            return QRect(self._start, self._end).normalized()
        return None

    def mousePressEvent(self, e):
        if not self._pixmap or e.button() != Qt.LeftButton:
            return
        r = self._current_rect()
        if self._fixed_size:
            fw, fh = self._fixed_size
            if r and r.contains(e.pos()):
                self._moving = True
                self._move_start = e.pos()
                self._move_rect_start = QRect(r)
            else:
                # 点击任意位置 → 以该点为中心落下固定框 / Drop fixed box centered on click
                cx, cy = e.pos().x(), e.pos().y()
                nr = self._clamp_rect(QRect(cx - fw // 2, cy - fh // 2, fw, fh))
                self._rect = nr
                self._emit_rect(nr)
            self.update()
            return
        if r and r.contains(e.pos()):
            self._moving = True
            self._move_start = e.pos()
            self._move_rect_start = QRect(r)
        else:
            self._drawing = True
            self._start = e.pos()
            self._end = e.pos()
            self._rect = None
        self.update()

    def mouseMoveEvent(self, e):
        if self._moving:
            delta = e.pos() - self._move_start
            new_rect = self._move_rect_start.translated(delta)
            self._rect = self._clamp_rect(new_rect)
            self.update()
        elif self._drawing:
            self._end = self._clamp(e.pos())
            self.update()
        else:
            r = self._current_rect()
            if r and r.contains(e.pos()):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.CrossCursor)

    def mouseReleaseEvent(self, e):
        if self._fixed_size:
            # 固定尺寸模式: 点击即选中，移动后确认 / Fixed size: click sets, move confirms
            if self._moving:
                self._moving = False
                if self._rect and self._rect.width() > 2 and self._rect.height() > 2:
                    self._emit_rect(self._rect)
            self.update()
            return
        if self._moving:
            self._moving = False
            r = self._rect
            if r and r.width() > 5 and r.height() > 5:
                self._emit_rect(r)
            else:
                self._rect = None
                self.crop_rect_changed.emit(0, 0, 0, 0)
            self.update()
        elif self._drawing:
            self._drawing = False
            self._end = self._clamp(e.pos())
            r = QRect(self._start, self._end).normalized()
            if r.width() > 5 and r.height() > 5:
                self._rect = r
                self._emit_rect(r)
            else:
                self._rect = None
                self.crop_rect_changed.emit(0, 0, 0, 0)
            self.update()

    def _clamp(self, pt: QPoint) -> QPoint:
        x = max(0, min(pt.x(), self._pixmap.width() - 1))
        y = max(0, min(pt.y(), self._pixmap.height() - 1))
        return QPoint(x, y)

    def _emit_rect(self, r: QRect):
        """将像素选区转为 PDF 点坐标并发出。"""
        x0 = r.left() / self._scale
        y0 = r.top() / self._scale
        x1 = (r.right() + 1) / self._scale
        y1 = (r.bottom() + 1) / self._scale
        self.crop_rect_changed.emit(x0, y0, x1, y1)


class CropPanel(BasePanel):
    """裁剪面板：框选区域 → 应用到相同尺寸页或自定义页码。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._src_path = ""
        self._total_pages = 0
        self._crop_rect = None  # (x0,y0,x1,y1) PDF 点
        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        # 源文件 + 参考页 / Source + reference page
        src_row = QHBoxLayout()
        self._src_label = QLabel()
        self._src_edit = QLineEdit()
        self._src_edit.setReadOnly(True)
        self._src_btn = QPushButton()
        self._src_btn.clicked.connect(self._pick_source)
        self._ref_label = QLabel()
        self._ref_spin = QSpinBox()
        self._ref_spin.setMinimum(1)
        self._ref_spin.setValue(1)
        self._load_btn = QPushButton()
        self._load_btn.clicked.connect(self._load_preview)
        src_row.addWidget(self._src_label)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(self._ref_label)
        src_row.addWidget(self._ref_spin)
        src_row.addWidget(self._src_btn)
        src_row.addWidget(self._load_btn)
        self._content.addLayout(src_row)

        # 预览框选区 (可滚动) / Crop preview (scrollable)
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setAlignment(Qt.AlignCenter)
        self._preview = CropPreviewWidget()
        self._preview.crop_rect_changed.connect(self._on_crop_changed)
        self._preview_scroll.setWidget(self._preview)
        self._content.addWidget(self._preview_scroll, 1)

        # 裁剪区域信息 + 重置 / Crop info + reset
        info_row = QHBoxLayout()
        self._region_label = QLabel()
        self._region_info = QLabel("")
        self._region_info.setStyleSheet(
            "color:#2980b9; font-weight:bold; font-family:Consolas;")
        self._reset_btn = QPushButton()
        self._reset_btn.clicked.connect(self._preview.reset)
        info_row.addWidget(self._region_label)
        info_row.addWidget(self._region_info, 1)
        info_row.addWidget(self._reset_btn)
        self._content.addLayout(info_row)

        # 应用范围 / Apply to
        apply_row = QHBoxLayout()
        self._apply_label = QLabel()
        self._same_size_rb = QRadioButton()
        self._same_size_rb.setChecked(True)
        self._same_size_rb.toggled.connect(self._on_apply_change)
        self._custom_rb = QRadioButton()
        self._custom_rb.toggled.connect(self._on_apply_change)
        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("1-3,5,7-9")
        self._custom_edit.setEnabled(False)
        self._same_size_info = QLabel("")
        self._same_size_info.setStyleSheet("color:#27ae60;")
        apply_row.addWidget(self._apply_label)
        apply_row.addWidget(self._same_size_rb)
        apply_row.addWidget(self._same_size_info)
        apply_row.addWidget(self._custom_rb)
        apply_row.addWidget(self._custom_edit, 1)
        self._content.addLayout(apply_row)

        # 输出名 + 目录 / Output name + dir
        out_row = QHBoxLayout()
        self._name_label = QLabel()
        self._name_edit = QLineEdit()
        out_row.addWidget(self._name_label)
        out_row.addWidget(self._name_edit, 1)
        self._content.addLayout(out_row)

        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

    # --- 事件 / Events ---
    def _pick_source(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if not f:
            return
        try:
            info = pdf_core.get_pdf_info(f)
        except Exception as e:
            QMessageBox.critical(self, tr("failed"), str(e))
            return
        self._src_path = f
        self._total_pages = info["pages"]
        self._src_edit.setText(f)
        self._ref_spin.setMaximum(info["pages"])
        self._ref_spin.setValue(1)
        self._name_edit.setText(_default_output_name(f, "cropped"))
        self._crop_rect = None
        self._update_same_size_info()
        log_info(f"[Crop] loaded {os.path.basename(f)} ({info['pages']} pages)")

    def _load_preview(self):
        if not self._src_path:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        ref = self._ref_spin.value() - 1  # 0-based
        try:
            w, h = pdf_core.get_page_size(self._src_path, ref)
            # 渲染到适合预览的尺寸 / Render to fit preview
            max_w = 700
            scale = min(max_w / w, 700 / h, 2.0)
            png = pdf_core.render_page_image(self._src_path, ref, max_w)
            img = QImage.fromData(png, "PNG")
            pix = QPixmap.fromImage(img)
            self._preview.set_page(pix, w, h, scale)
            self._crop_rect = None
            self._region_info.setText("")
            self._update_same_size_info()
            log_info(f"[Crop] preview page {ref+1} ({w:.0f}x{h:.0f} pt)")
        except Exception as e:
            QMessageBox.critical(self, tr("failed"), str(e))

    def _on_crop_changed(self, x0, y0, x1, y1):
        if x1 - x0 < 1 or y1 - y0 < 1:
            self._crop_rect = None
            self._region_info.setText("")
            return
        self._crop_rect = (x0, y0, x1, y1)
        cw, ch = x1 - x0, y1 - y0
        self._region_info.setText(
            f"x={x0:.0f} y={y0:.0f}  {tr('crop_width')}={cw:.0f}pt "
            f"({cw*25.4/72:.0f}mm)  {tr('crop_height')}={ch:.0f}pt "
            f"({ch*25.4/72:.0f}mm)")

    def _on_apply_change(self):
        self._custom_edit.setEnabled(self._custom_rb.isChecked())

    def _update_same_size_info(self):
        if not self._src_path:
            self._same_size_info.setText("")
            return
        ref = self._ref_spin.value() - 1
        same = pdf_core.find_same_size_pages(self._src_path, ref)
        self._same_size_info.setText(tr("crop_same_size_info", n=len(same)))

    # --- 执行 / Execute ---
    def on_execute(self):
        if not self._src_path:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        if not self._crop_rect:
            QMessageBox.warning(self, tr("invalid_input"),
                                tr("crop_no_selection"))
            return
        # 确定目标页 / Determine target pages
        ref = self._ref_spin.value() - 1
        if self._same_size_rb.isChecked():
            pages = pdf_core.find_same_size_pages(self._src_path, ref)
        else:
            spec = self._custom_edit.text().strip()
            if not spec:
                pages = list(range(self._total_pages))
            else:
                try:
                    pages = pdf_core.parse_page_ranges(
                        spec, self._total_pages)
                except Exception:
                    QMessageBox.warning(
                        self, tr("invalid_input"),
                        tr("err_invalid_range", rng=spec))
                    return
        if not pages:
            QMessageBox.warning(self, tr("invalid_input"),
                                tr("err_invalid_range", rng=""))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return
        name = self._name_edit.text().strip() or "cropped.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        out_path = os.path.join(out_dir, name)
        if os.path.abspath(out_path) == os.path.abspath(self._src_path):
            QMessageBox.warning(self, tr("invalid_input"), tr("err_same_output"))
            return
        log_info(f"[Crop] crop {len(pages)} pages, rect={self._crop_rect}")
        self._pending_crop_n = len(pages)
        self.start_worker(pdf_core.crop_pages, self._src_path, out_path,
                          pages, self._crop_rect)

    def on_success(self, result):
        n = getattr(self, "_pending_crop_n", 0)
        QMessageBox.information(
            self, tr("success"), tr("crop_success", n=n, m=result))
        log_info(f"[Crop] done: cropped {n} pages, output {result} pages")

    # --- 翻译 / Translation ---
    def title_key(self):
        return "tab_crop"

    def desc_key(self):
        return "crop_desc"

    def _do_retranslate(self):
        self._src_label.setText(tr("crop_source") + ":")
        self._src_btn.setText(tr("browse"))
        self._ref_label.setText(tr("crop_ref_page") + ":")
        self._load_btn.setText(tr("crop_load"))
        self._region_label.setText(tr("crop_region") + ":")
        self._reset_btn.setText(tr("crop_reset"))
        self._apply_label.setText(tr("crop_apply_to") + ":")
        self._same_size_rb.setText(tr("crop_same_size"))
        self._custom_rb.setText(tr("crop_custom"))
        self._custom_edit.setPlaceholderText(tr("crop_custom_hint"))
        self._name_label.setText(tr("merge_output_name") + ":")
        self._update_same_size_info()


# ===========================================================================
# 9a. 异常尺寸裁剪对话框 / Anomaly Crop Dialog
# ===========================================================================

class AnomalyCropDialog(QDialog):
    """
    逐页预览异常尺寸页面，用户可视化框选裁剪区域。
    支持: 自由尺寸 / 固定尺寸(A3/A4/A5/Letter/自定义) + 方向(竖/横)，
          上一页/下一页导航，拖拽移动选区，
          "应用到所有相同尺寸页" 选项。
    返回: {page_idx: (x0, y0, x1, y1)} via get_crop_rects()
    """

    # 尺寸模式选项: mode_key → label i18n key, pt_short, pt_long
    # pt_short=短边, pt_long=长边；方向组合决定 w, h
    SIZE_MODES = [
        ("free",   "size_detect_crop_free", 0.0, 0.0),
        ("A5",     "A5",    420.0,  595.0),
        ("A4",     "A4",    595.0,  842.0),
        ("A3",     "A3",    842.0, 1191.0),
        ("Letter", "Letter",612.0,  792.0),
        ("Legal",  "Legal", 612.0, 1008.0),
        ("Custom", "size_detect_maj_custom", 0.0, 0.0),
    ]

    def __init__(self, src_path: str, anomaly_pages: List[int],
                 majority_size: tuple, page_sizes: dict,
                 existing_crops: dict = None, start_page: int = None,
                 parent=None):
        super().__init__(parent)
        self._src = src_path
        self._pages = list(anomaly_pages)  # 0-based
        self._target = majority_size       # (w, h) PDF points
        self._page_sizes = page_sizes      # {page_idx: (w, h)}
        self._crop_rects: dict = dict(existing_crops) if existing_crops else {}
        self._cur = 0
        self._current_crop = None

        # 导入 settings (懒加载避免循环依赖)
        from settings import SettingsManager
        self._s = SettingsManager.instance()

        if start_page is not None and start_page in self._pages:
            self._cur = self._pages.index(start_page)

        self._build_ui()
        self._apply_settings_defaults()
        self._load_page()

    def _build_ui(self):
        self.setWindowTitle(tr("size_crop_dialog_title"))
        self.resize(860, 800)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # 目标尺寸信息 / Target size info
        tw, th = self._target
        tw_mm, th_mm = tw * 25.4 / 72, th * 25.4 / 72
        self._target_label = QLabel(
            f"<b>{tr('size_crop_target')}:</b> {tw:.0f}x{th:.0f}pt "
            f"({tw_mm:.0f}x{th_mm:.0f}mm)")
        self._target_label.setStyleSheet("color:#2980b9; font-size:13px;")
        lay.addWidget(self._target_label)

        # 裁剪模式行: 模式下拉 + 方向 + 自定义宽高
        mode_row = QHBoxLayout()
        self._mode_label = QLabel(tr("size_detect_crop_mode") + ":")
        self._mode_combo = QComboBox()
        for key, label_key, *_ in self.SIZE_MODES:
            if key in ("free", "Custom"):
                self._mode_combo.addItem(tr(label_key), key)
            else:
                self._mode_combo.addItem(label_key, key)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._orient_label = QLabel(tr("size_detect_crop_orientation") + ":")
        self._orient_combo = QComboBox()
        self._orient_combo.addItem(tr("size_detect_crop_portrait"), "portrait")
        self._orient_combo.addItem(tr("size_detect_crop_landscape"), "landscape")
        self._orient_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._w_label = QLabel(tr("settings_width"))
        self._w_spin = QDoubleSpinBox()
        self._w_spin.setRange(1, 99999)
        self._w_spin.setDecimals(1)
        self._w_spin.setSuffix(" pt")
        self._w_spin.setValue(595)
        self._h_label = QLabel(tr("settings_height"))
        self._h_spin = QDoubleSpinBox()
        self._h_spin.setRange(1, 99999)
        self._h_spin.setDecimals(1)
        self._h_spin.setSuffix(" pt")
        self._h_spin.setValue(842)
        self._mm_hint = QLabel("")
        self._mm_hint.setStyleSheet("color:#7f8c8d; font-size:11px;")
        self._w_spin.valueChanged.connect(self._on_custom_changed)
        self._h_spin.valueChanged.connect(self._on_custom_changed)
        mode_row.addWidget(self._mode_label)
        mode_row.addWidget(self._mode_combo)
        mode_row.addWidget(self._orient_label)
        mode_row.addWidget(self._orient_combo)
        mode_row.addWidget(self._w_label)
        mode_row.addWidget(self._w_spin)
        mode_row.addWidget(self._h_label)
        mode_row.addWidget(self._h_spin)
        mode_row.addSpacing(8)
        mode_row.addWidget(self._mm_hint, 1)
        lay.addLayout(mode_row)

        # 导航栏 / Navigation
        nav = QHBoxLayout()
        self._prev_btn = QPushButton()
        self._prev_btn.clicked.connect(self._go_prev)
        self._page_info = QLabel()
        self._page_info.setStyleSheet("font-weight:bold; color:#2c3e50;")
        self._page_info.setAlignment(Qt.AlignCenter)
        self._next_btn = QPushButton()
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._prev_btn)
        nav.addStretch(1)
        nav.addWidget(self._page_info)
        nav.addStretch(1)
        nav.addWidget(self._next_btn)
        lay.addLayout(nav)

        # 预览区 (可滚动) / Preview (scrollable)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignCenter)
        self._preview = CropPreviewWidget()
        self._preview.crop_rect_changed.connect(self._on_crop_changed)
        self._scroll.setWidget(self._preview)
        lay.addWidget(self._scroll, 1)

        # 裁剪区域信息 + 重置 / Crop info + reset
        info_row = QHBoxLayout()
        self._region_info = QLabel("")
        self._region_info.setStyleSheet(
            "color:#2980b9; font-weight:bold; font-family:Consolas;")
        self._reset_btn = QPushButton()
        self._reset_btn.clicked.connect(self._reset_crop)
        info_row.addWidget(self._region_info, 1)
        info_row.addWidget(self._reset_btn)
        lay.addLayout(info_row)

        # 警告标签 / Warning label
        self._warn_label = QLabel("")
        self._warn_label.setStyleSheet("color:#e67e22; font-size:11px;")
        lay.addWidget(self._warn_label)

        # 应用到相同尺寸 / Apply to same size
        self._apply_same_cb = QCheckBox()
        self._apply_same_cb.setChecked(True)
        self._apply_info = QLabel("")
        self._apply_info.setStyleSheet("color:#27ae60; font-size:11px;")
        apply_row = QHBoxLayout()
        apply_row.addWidget(self._apply_same_cb)
        apply_row.addWidget(self._apply_info, 1)
        lay.addLayout(apply_row)

        # 底部按钮 / Bottom buttons
        btn_row = QHBoxLayout()
        self._skip_btn = QPushButton()
        self._skip_btn.clicked.connect(self._skip_page)
        self._cancel_btn = QPushButton()
        self._cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton()
        self._ok_btn.setStyleSheet(
            "QPushButton{background:#27ae60; color:white; border:none;"
            "border-radius:4px; padding:8px 24px; font-weight:bold;}"
            "QPushButton:hover{background:#229954;}")
        self._ok_btn.clicked.connect(self._confirm)
        btn_row.addWidget(self._skip_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._ok_btn)
        lay.addLayout(btn_row)

        self.retranslate()

    def _apply_settings_defaults(self):
        """根据全局设置初始化模式选择。"""
        mode = self._s.get("crop_default_mode", "free")
        # 匹配到下拉 / Match to combo
        idx = self._mode_combo.findData(mode)
        if idx < 0:
            idx = 0
        self._mode_combo.setCurrentIndex(idx)
        if mode == "Custom":
            self._w_spin.setValue(float(self._s.get("crop_custom_w", 595)))
            self._h_spin.setValue(float(self._s.get("crop_custom_h", 842)))
        # 方向默认: 参考主尺寸方向
        tw, th = self._target
        self._orient_combo.setCurrentIndex(0 if th >= tw else 1)
        self._update_custom_widgets()
        self._update_mm_hint()

    def _update_custom_widgets(self):
        mode = self._mode_combo.currentData()
        free = (mode == "free")
        custom = (mode == "Custom")
        self._orient_label.setEnabled(not free)
        self._orient_combo.setEnabled(not free)
        self._w_label.setEnabled(custom)
        self._w_spin.setEnabled(custom)
        self._h_label.setEnabled(custom)
        self._h_spin.setEnabled(custom)

    def _get_crop_fixed_size(self):
        """
        基于模式 + 方向返回 (w_pt, h_pt) 或 None(自由)。
        """
        mode = self._mode_combo.currentData()
        orient = self._orient_combo.currentData()  # portrait / landscape
        if mode == "free":
            return None
        for key, _label, sw, lw in self.SIZE_MODES:
            if key != mode:
                continue
            if key == "Custom":
                sw = self._w_spin.value()
                lw = self._h_spin.value()
                # 对于自定义，短边/长边 先处理
                sw, lw = (sw, lw) if sw <= lw else (lw, sw)
            if orient == "portrait":
                return (sw, lw)
            else:
                return (lw, sw)
        return None

    def _update_mm_hint(self):
        sz = self._get_crop_fixed_size()
        if sz is None:
            self._mm_hint.setText("")
            return
        w, h = sz
        self._mm_hint.setText(
            f"{w*25.4/72:.1f} x {h*25.4/72:.1f} mm")

    def _on_mode_changed(self, *_):
        self._update_custom_widgets()
        self._update_mm_hint()
        # 应用模式到当前预览 / Apply mode to current preview
        fixed = self._get_crop_fixed_size()
        if fixed:
            self._preview.set_fixed_crop_size(fixed[0], fixed[1])
        else:
            self._preview.set_fixed_crop_size(None, None)
        # 重置当前页裁剪为默认居中
        self._reset_crop()

    def _on_custom_changed(self, *_):
        self._update_mm_hint()
        self._on_mode_changed()

    def retranslate(self):
        self._mode_label.setText(tr("size_detect_crop_mode") + ":")
        self._orient_label.setText(tr("size_detect_crop_orientation") + ":")
        self._w_label.setText(tr("settings_width"))
        self._h_label.setText(tr("settings_height"))
        # 更新下拉 i18n: free / Custom (其他为英文纸张名本身)
        for i in range(self._mode_combo.count()):
            key = self._mode_combo.itemData(i)
            if key == "free":
                self._mode_combo.setItemText(i, tr("size_detect_crop_free"))
            elif key == "Custom":
                self._mode_combo.setItemText(i, tr("size_detect_maj_custom"))
        for i, key in enumerate(("portrait", "landscape")):
            if key == "portrait":
                self._orient_combo.setItemText(i, tr("size_detect_crop_portrait"))
            else:
                self._orient_combo.setItemText(i, tr("size_detect_crop_landscape"))
        self._prev_btn.setText("← " + tr("preview_prev"))
        self._next_btn.setText(tr("preview_next") + " →")
        self._reset_btn.setText(tr("crop_reset"))
        self._apply_same_cb.setText(tr("size_crop_apply_same"))
        self._skip_btn.setText(tr("size_crop_skip"))
        self._cancel_btn.setText(tr("cancel"))
        self._ok_btn.setText(tr("size_crop_confirm"))
        self._update_mm_hint()

    # --- 页面加载 / Page loading ---
    def _load_page(self):
        """加载当前页的预览图与默认裁剪区域。"""
        if not self._pages:
            return
        page_idx = self._pages[self._cur]
        w, h = self._page_sizes.get(page_idx, (0, 0))

        # 渲染页面 / Render page
        max_w = 700
        scale = min(max_w / w, 700 / h, 2.0) if w > 0 and h > 0 else 1.0
        try:
            png = pdf_core.render_page_image(self._src, page_idx, max_w)
            img = QImage.fromData(png, "PNG")
            pix = QPixmap.fromImage(img)
        except Exception:
            pix = QPixmap()

        # 计算固定裁剪大小 / Compute fixed crop size
        fixed = self._get_crop_fixed_size()
        fw, fh = fixed if fixed else (None, None)
        self._preview.set_page(pix, w, h, scale, fw, fh)

        # 检查是否已有保存的裁剪 (按固定尺寸居中到原中心)
        if page_idx in self._crop_rects:
            x0, y0, x1, y1 = self._crop_rects[page_idx]
            self._preview.set_initial_crop(x0, y0, x1, y1)
        else:
            # 默认居中按当前模式尺寸 / Default centered by current mode size
            if fixed:
                tw, th = fixed
            else:
                tw, th = self._target
            # 如果页面小于目标尺寸，就取页面大小裁剪
            cx, cy = w / 2, h / 2
            bw = min(tw, w)
            bh = min(th, h)
            x0 = max(0, cx - bw / 2)
            y0 = max(0, cy - bh / 2)
            x1 = x0 + bw
            y1 = y0 + bh
            self._preview.set_initial_crop(x0, y0, x1, y1)

        # 更新页面信息 / Update page info
        paper = pdf_core.classify_page_size(w, h)
        w_mm, h_mm = w * 25.4 / 72, h * 25.4 / 72
        self._page_info.setText(
            tr("size_crop_page_info", cur=self._cur + 1,
               total=len(self._pages), page=page_idx + 1,
               paper=paper, w=f"{w_mm:.0f}", h=f"{h_mm:.0f}"))

        # 更新警告: 当前裁剪尺寸 > 页面尺寸 时提示
        tw, th = fixed if fixed else self._target
        if w < tw or h < th:
            w_mm2, h_mm2 = tw * 25.4 / 72, th * 25.4 / 72
            self._warn_label.setText(
                tr("size_crop_warn_small") +
                f" (目标 {w_mm2:.0f}x{h_mm2:.0f}mm)")
        else:
            self._warn_label.setText("")

        self._prev_btn.setEnabled(self._cur > 0)
        self._next_btn.setEnabled(self._cur < len(self._pages) - 1)
        self._update_apply_info()

    def _update_apply_info(self):
        if self._apply_same_cb.isChecked():
            page_idx = self._pages[self._cur]
            w, h = self._page_sizes.get(page_idx, (0, 0))
            n = sum(1 for p in self._pages
                    if self._is_same_size(p, w, h))
            self._apply_info.setText(tr("size_crop_apply_n", n=n))
        else:
            self._apply_info.setText("")

    def _is_same_size(self, page_idx, ref_w, ref_h, tol=2.0) -> bool:
        pw, ph = self._page_sizes.get(page_idx, (0, 0))
        nw1, nh1 = min(ref_w, ref_h), max(ref_w, ref_h)
        nw2, nh2 = min(pw, ph), max(pw, ph)
        return abs(nw1 - nw2) <= tol and abs(nh1 - nh2) <= tol

    # --- 事件 / Events ---
    def _on_crop_changed(self, x0, y0, x1, y1):
        if x1 - x0 < 1 or y1 - y0 < 1:
            self._current_crop = None
            self._region_info.setText("")
            return
        self._current_crop = (x0, y0, x1, y1)
        cw, ch = x1 - x0, y1 - y0
        self._region_info.setText(
            f"x={x0:.0f} y={y0:.0f}  {tr('crop_width')}={cw:.0f}pt "
            f"({cw*25.4/72:.0f}mm)  {tr('crop_height')}={ch:.0f}pt "
            f"({ch*25.4/72:.0f}mm)")

    def _save_current(self):
        """保存当前页的裁剪区域。"""
        if not self._pages or not self._current_crop:
            return
        page_idx = self._pages[self._cur]
        rect = self._current_crop
        if self._apply_same_cb.isChecked():
            # 应用到所有相同尺寸的异常页 / Apply to all same-size anomaly pages
            w, h = self._page_sizes.get(page_idx, (0, 0))
            for p in self._pages:
                if self._is_same_size(p, w, h):
                    self._crop_rects[p] = rect
        else:
            self._crop_rects[page_idx] = rect

    def _reset_crop(self):
        """重置为默认居中裁剪 (按当前模式尺寸)。"""
        if not self._pages:
            return
        page_idx = self._pages[self._cur]
        w, h = self._page_sizes.get(page_idx, (0, 0))
        fixed = self._get_crop_fixed_size()
        tw, th = fixed if fixed else self._target
        cx, cy = w / 2, h / 2
        bw = min(tw, w)
        bh = min(th, h)
        x0 = max(0, cx - bw / 2)
        y0 = max(0, cy - bh / 2)
        x1 = x0 + bw
        y1 = y0 + bh
        self._preview.set_initial_crop(x0, y0, x1, y1)

    def _go_prev(self):
        self._save_current()
        if self._cur > 0:
            self._cur -= 1
            self._current_crop = None
            self._load_page()

    def _go_next(self):
        self._save_current()
        if self._cur < len(self._pages) - 1:
            self._cur += 1
            self._current_crop = None
            self._load_page()

    def _skip_page(self):
        """跳过当前页 (不裁剪)。"""
        page_idx = self._pages[self._cur]
        self._crop_rects.pop(page_idx, None)
        self._current_crop = None
        if self._cur < len(self._pages) - 1:
            self._cur += 1
            self._load_page()
        else:
            self._confirm()

    def _confirm(self):
        self._save_current()
        if not self._crop_rects:
            QMessageBox.warning(self, tr("invalid_input"),
                                tr("size_crop_no_rect"))
            return
        self.accept()

    def get_crop_rects(self) -> dict:
        """返回 {page_idx: (x0, y0, x1, y1)} 字典。"""
        return self._crop_rects


# ===========================================================================
# 9. 尺寸检测 面板 / Size Detect Panel
# ===========================================================================

class SizeDetectPanel(BasePanel):
    """
    扫描 PDF 页面尺寸 → 识别主尺寸/异常尺寸 →
    双击异常页弹出裁剪对话框 → 右键标记删除/缩放 →
    导出前显示操作摘要确认 → 一次性应用所有操作。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._src_path = ""
        self._total_pages = 0
        self._result: dict = None
        self._pending_crops: dict = {}
        self._pending_deletes: set = set()
        self._pending_scales: set = set()
        self._page_sizes: dict = {}
        from settings import SettingsManager
        self._s = SettingsManager.instance()
        self._build_ui()
        self._load_defaults()
        self.retranslate()

    def _load_defaults(self):
        """从 settings 加载默认值 (容差/主尺寸/输出目录)。"""
        self._tol_spin.setValue(int(self._s.get("detect_tolerance_pt", 2)))
        mode = self._s.get("detect_majority_mode", "auto")
        idx = self._maj_combo.findData(mode)
        if idx >= 0:
            self._maj_combo.setCurrentIndex(idx)
        self._maj_w_spin.setValue(float(self._s.get("detect_majority_custom_w", 595)))
        self._maj_h_spin.setValue(float(self._s.get("detect_majority_custom_h", 842)))
        self._update_maj_widgets()
        # 默认输出目录
        out = self._s.get("default_output_dir", "")
        if os.path.isdir(out):
            self._out_dir.set_path(out)

    def _build_ui(self):
        # 第一行: 源文件选择 / Row 1: source file
        src_row = QHBoxLayout()
        self._src_label = QLabel()
        self._src_edit = QLineEdit()
        self._src_edit.setReadOnly(True)
        self._src_btn = QPushButton()
        self._src_btn.clicked.connect(self._pick_source)
        self._settings_btn = QPushButton()
        self._settings_btn.clicked.connect(self._open_settings)
        src_row.addWidget(self._src_label)
        src_row.addWidget(self._src_edit, 1)
        src_row.addWidget(self._src_btn)
        src_row.addWidget(self._settings_btn)
        self._content.addLayout(src_row)

        # 第二行: 检测参数 / Row 2: detection parameters
        det_row = QHBoxLayout()
        self._tol_label = QLabel()
        self._tol_spin = QSpinBox()
        self._tol_spin.setRange(1, 50)
        self._tol_spin.setValue(2)
        self._maj_label = QLabel()
        self._maj_combo = QComboBox()
        self._maj_combo.addItem("", "auto")
        for paper, _size in (
                ("A5", (420, 595)), ("A4", (595, 842)),
                ("A3", (842, 1191)), ("A2", (1191, 1684)),
                ("Letter", (612, 792)), ("Legal", (612, 1008))):
            self._maj_combo.addItem(paper, paper)
        self._maj_combo.addItem("", "Custom")
        self._maj_combo.currentIndexChanged.connect(self._on_maj_mode_changed)
        self._maj_w_label = QLabel()
        self._maj_w_spin = QDoubleSpinBox()
        self._maj_w_spin.setRange(1, 99999)
        self._maj_w_spin.setDecimals(1)
        self._maj_w_spin.setSuffix(" pt")
        self._maj_w_spin.setValue(595)
        self._maj_h_label = QLabel()
        self._maj_h_spin = QDoubleSpinBox()
        self._maj_h_spin.setRange(1, 99999)
        self._maj_h_spin.setDecimals(1)
        self._maj_h_spin.setSuffix(" pt")
        self._maj_h_spin.setValue(842)
        self._maj_mm_label = QLabel("")
        self._maj_mm_label.setStyleSheet("color:#7f8c8d; font-size:11px;")
        self._maj_w_spin.valueChanged.connect(self._on_maj_custom_changed)
        self._maj_h_spin.valueChanged.connect(self._on_maj_custom_changed)
        self._detect_btn = QPushButton()
        self._detect_btn.setStyleSheet(
            "QPushButton{background:#27ae60; color:white; border:none;"
            "border-radius:4px; padding:6px 14px; font-weight:bold;}"
            "QPushButton:hover{background:#229954;}"
            "QPushButton:disabled{background:#bdc3c7;}")
        self._detect_btn.clicked.connect(self._run_detect)
        det_row.addWidget(self._tol_label)
        det_row.addWidget(self._tol_spin)
        det_row.addSpacing(12)
        det_row.addWidget(self._maj_label)
        det_row.addWidget(self._maj_combo)
        det_row.addWidget(self._maj_w_label)
        det_row.addWidget(self._maj_w_spin)
        det_row.addWidget(self._maj_h_label)
        det_row.addWidget(self._maj_h_spin)
        det_row.addWidget(self._maj_mm_label)
        det_row.addStretch(1)
        det_row.addWidget(self._detect_btn)
        self._content.addLayout(det_row)

        # 汇总信息 / Summary
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(
            "background:#34495e; color:#ecf0f1; padding:8px;"
            "border-radius:4px; font-family:Consolas;")
        self._summary_label.setWordWrap(True)
        self._content.addWidget(self._summary_label)

        # 结果表格 / Results table
        self._table = QTableWidget(0, 6)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        for col in range(4):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.doubleClicked.connect(self._on_double_click)
        self._content.addWidget(self._table, 1)

        # 提示 / Tip
        self._tip_label = QLabel()
        self._tip_label.setStyleSheet("color:#7f8c8d; font-size:11px;")
        self._content.addWidget(self._tip_label)

        # 操作按钮 / Action buttons
        action_row = QHBoxLayout()
        self._ops_label = QLabel("")
        self._ops_label.setStyleSheet("color:#2980b9; font-weight:bold;")
        self._reset_btn = QPushButton()
        self._reset_btn.clicked.connect(self._reset_ops)
        self._export_btn = QPushButton()
        self._export_btn.setStyleSheet(
            "QPushButton{background:#e67e22; color:white; border:none;"
            "border-radius:4px; padding:8px 24px; font-weight:bold;}"
            "QPushButton:hover{background:#d35400;}"
            "QPushButton:disabled{background:#bdc3c7;}")
        self._export_btn.clicked.connect(self._export_all)
        action_row.addWidget(self._ops_label, 1)
        action_row.addWidget(self._reset_btn)
        action_row.addWidget(self._export_btn)
        self._content.addLayout(action_row)

        # 输出目录 / Output dir
        self._out_dir = OutputDirPicker()
        self._content.addWidget(self._out_dir)

    # --- 文件选择 / File pick ---
    def _pick_source(self):
        f, _ = QFileDialog.getOpenFileName(
            self, tr("select_pdf"), "", "PDF (*.pdf)")
        if not f:
            return
        try:
            info = pdf_core.get_pdf_info(f)
        except Exception as e:
            QMessageBox.critical(self, tr("failed"), str(e))
            return
        self._src_path = f
        self._total_pages = info["pages"]
        self._src_edit.setText(f)
        self._result = None
        self._pending_crops.clear()
        self._pending_deletes.clear()
        self._pending_scales.clear()
        self._table.setRowCount(0)
        self._summary_label.setText("")
        self._update_ops_label()
        log_info(f"[SizeDetect] loaded {os.path.basename(f)} ({info['pages']} pages)")

    # --- 检测 / Detection ---
    def _update_maj_widgets(self):
        """启用/禁用主尺寸自定义输入。"""
        mode = self._maj_combo.currentData()
        custom = (mode == "Custom")
        self._maj_w_spin.setEnabled(custom)
        self._maj_h_spin.setEnabled(custom)
        self._maj_w_label_en = (mode != "auto")
        # mm label
        if mode == "auto":
            self._maj_mm_label.setText("")
        else:
            w, h = self._get_force_majority_size() or (0, 0)
            self._maj_mm_label.setText(
                f"({w * 25.4 / 72:.1f} x {h * 25.4 / 72:.1f} mm)")

    def _get_force_majority_size(self):
        mode = self._maj_combo.currentData()
        if mode == "auto":
            return None
        if mode == "Custom":
            return (float(self._maj_w_spin.value()),
                    float(self._maj_h_spin.value()))
        # 固定纸张 (按短边×长边返回)
        sizes = {"A5": (420, 595), "A4": (595, 842),
                 "A3": (842, 1191), "A2": (1191, 1684),
                 "Letter": (612, 792), "Legal": (612, 1008)}
        if mode in sizes:
            return sizes[mode]
        return None

    def _on_maj_mode_changed(self, *_):
        self._update_maj_widgets()

    def _on_maj_custom_changed(self, *_):
        self._update_maj_widgets()

    def _open_settings(self):
        """打开全局设置对话框。"""
        dlg = SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            # 保存完立即应用到默认值 / Apply saved defaults immediately
            self._load_defaults()

    def _run_detect(self):
        if not self._src_path:
            QMessageBox.warning(self, tr("invalid_input"), tr("err_no_pdf"))
            return
        tol = float(self._tol_spin.value())
        force = self._get_force_majority_size()
        # 持久化当前容差/主尺寸选择到 settings (下次默认)
        self._s.set("detect_tolerance_pt", tol)
        self._s.set("detect_majority_mode", self._maj_combo.currentData())
        if force:
            self._s.set("detect_majority_custom_w", force[0])
            self._s.set("detect_majority_custom_h", force[1])
        self._s.save()

        log_info(f"[SizeDetect] start: {os.path.basename(self._src_path)}"
                 f" tol={tol}pt force={force}")
        self._set_running(True)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._worker = PDFWorker(pdf_core.detect_page_sizes,
                                 self._src_path, tol, force_majority=force)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_detect_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_detect_done(self, result):
        self._set_running(False)
        self._progress.setVisible(False)
        self._result = result
        self._pending_crops.clear()
        self._pending_deletes.clear()
        self._pending_scales.clear()
        # 构建 page_sizes 字典 / Build page sizes lookup
        self._page_sizes = {}
        for p_idx, w, h, _paper, _anom in result['pages']:
            self._page_sizes[p_idx] = (w, h)
        self._populate_table()
        self._update_summary()
        self._update_ops_label()
        n_anom = len(result['anomaly_pages'])
        if n_anom:
            log_warn(f"[SizeDetect] found {n_anom} anomalous pages: "
                     f"{[p+1 for p in result['anomaly_pages']]}")
        else:
            log_info("[SizeDetect] no anomalous pages found")

    def _update_summary(self):
        if not self._result:
            self._summary_label.setText("")
            return
        groups = self._result['groups']
        parts = []
        for g in sorted(groups, key=lambda x: len(x['pages']), reverse=True):
            w_mm = g['width'] * 25.4 / 72
            h_mm = g['height'] * 25.4 / 72
            tag = tr("size_detect_majority") if g['is_majority'] else tr("size_detect_anomaly")
            parts.append(
                f"[{tag}] {g['paper']} {w_mm:.0f}x{h_mm:.0f}mm: {len(g['pages'])} 页")
        self._summary_label.setText("  |  ".join(parts))

    def _populate_table(self):
        self._table.setRowCount(0)
        if not self._result:
            return
        for page_idx, w, h, paper, is_anom in self._result['pages']:
            r = self._table.rowCount()
            self._table.insertRow(r)
            page_item = QTableWidgetItem(f"p{page_idx + 1}")
            page_item.setData(Qt.UserRole, page_idx)
            size_pt_item = QTableWidgetItem(f"{w:.0f} x {h:.0f}")
            w_mm = w * 25.4 / 72
            h_mm = h * 25.4 / 72
            size_mm_item = QTableWidgetItem(f"{w_mm:.0f} x {h_mm:.0f}")
            paper_item = QTableWidgetItem(paper)
            if is_anom:
                status_item = QTableWidgetItem(tr("size_detect_anomaly"))
                color = QColor("#e74c3c")
            else:
                status_item = QTableWidgetItem(tr("size_detect_majority"))
                color = QColor("#27ae60")
            for item in (page_item, size_pt_item, size_mm_item,
                         paper_item, status_item):
                item.setForeground(color)
            # 操作状态列 / Operation status column
            op_item = QTableWidgetItem(tr("size_detect_op_none"))
            op_item.setForeground(QColor("#95a5a6"))
            self._table.setItem(r, 0, page_item)
            self._table.setItem(r, 1, size_pt_item)
            self._table.setItem(r, 2, size_mm_item)
            self._table.setItem(r, 3, paper_item)
            self._table.setItem(r, 4, status_item)
            self._table.setItem(r, 5, op_item)

    def _update_row_op(self, page_idx: int):
        """更新某行的操作状态显示。"""
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.data(Qt.UserRole) == page_idx:
                op_item = self._table.item(r, 5)
                if not op_item:
                    return
                if page_idx in self._pending_deletes:
                    op_item.setText(tr("size_detect_op_delete"))
                    op_item.setForeground(QColor("#e74c3c"))
                elif page_idx in self._pending_crops:
                    op_item.setText(tr("size_detect_op_crop"))
                    op_item.setForeground(QColor("#e67e22"))
                elif page_idx in self._pending_scales:
                    op_item.setText(tr("size_detect_op_scale"))
                    op_item.setForeground(QColor("#9b59b6"))
                else:
                    op_item.setText(tr("size_detect_op_none"))
                    op_item.setForeground(QColor("#95a5a6"))
                return

    def _update_all_ops(self):
        """刷新所有行的操作状态。"""
        if not self._result:
            return
        for page_idx, _, _, _, _ in self._result['pages']:
            self._update_row_op(page_idx)
        self._update_ops_label()

    def _update_ops_label(self):
        n_crop = len(self._pending_crops)
        n_del = len(self._pending_deletes)
        n_scale = len(self._pending_scales)
        total = n_crop + n_del + n_scale
        parts = []
        if n_crop:
            parts.append(f"{tr('size_detect_op_crop')} {n_crop}")
        if n_del:
            parts.append(f"{tr('size_detect_op_delete')} {n_del}")
        if n_scale:
            parts.append(f"{tr('size_detect_op_scale')} {n_scale}")
        if parts:
            self._ops_label.setText(
                f"待导出操作: {' / '.join(parts)} (共 {total} 页)")
        else:
            self._ops_label.setText("")
        self._export_btn.setEnabled(total > 0 and bool(self._src_path))

    # --- 双击裁剪 / Double-click crop ---
    def _on_double_click(self, index):
        """双击异常页 → 弹出裁剪对话框。"""
        if not self._result or not self._result.get('majority_size'):
            return
        row = index.row()
        page_item = self._table.item(row, 0)
        if not page_item:
            return
        page_idx = page_item.data(Qt.UserRole)
        # 仅异常页可裁剪 / Only anomalous pages can be cropped
        if page_idx not in self._result['anomaly_pages']:
            return
        anomaly_pages = self._result['anomaly_pages']
        maj = self._result['majority_size']
        dialog = AnomalyCropDialog(
            self._src_path, anomaly_pages, maj, self._page_sizes,
            existing_crops=self._pending_crops, start_page=page_idx, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        new_rects = dialog.get_crop_rects()
        if new_rects:
            self._pending_crops.update(new_rects)
            # 裁剪的页不再删除/缩放 / Cropped pages no longer delete/scale
            for p in new_rects:
                self._pending_deletes.discard(p)
                self._pending_scales.discard(p)
            self._update_all_ops()
            log_info(f"[SizeDetect] cropped {len(new_rects)} pages: "
                     f"{[p+1 for p in new_rects]}")

    # --- 右键菜单 / Context menu ---
    def _on_context_menu(self, pos):
        if not self._result:
            return
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        page_item = self._table.item(row, 0)
        if not page_item:
            return
        page_idx = page_item.data(Qt.UserRole)
        if page_idx not in self._result['anomaly_pages']:
            return  # 主尺寸页无右键操作 / No context menu for majority pages

        menu = QMenu(self)
        act_crop = menu.addAction(tr("size_detect_ctx_crop"))
        act_scale = menu.addAction(tr("size_detect_ctx_scale"))
        act_delete = menu.addAction(tr("size_detect_ctx_delete"))
        menu.addSeparator()
        act_clear = menu.addAction(tr("size_detect_ctx_clear"))
        action = menu.exec_(self._table.viewport().mapToGlobal(pos))

        if action == act_crop:
            # 触发双击裁剪 / Trigger crop via double-click logic
            self._on_double_click(self._table.model().index(row, 0))
        elif action == act_scale:
            self._pending_scales.add(page_idx)
            self._pending_crops.pop(page_idx, None)
            self._pending_deletes.discard(page_idx)
            self._update_row_op(page_idx)
            self._update_ops_label()
            log_info(f"[SizeDetect] marked p{page_idx+1} for scale")
        elif action == act_delete:
            self._pending_deletes.add(page_idx)
            self._pending_crops.pop(page_idx, None)
            self._pending_scales.discard(page_idx)
            self._update_row_op(page_idx)
            self._update_ops_label()
            log_info(f"[SizeDetect] marked p{page_idx+1} for deletion")
        elif action == act_clear:
            self._pending_crops.pop(page_idx, None)
            self._pending_deletes.discard(page_idx)
            self._pending_scales.discard(page_idx)
            self._update_row_op(page_idx)
            self._update_ops_label()
            log_info(f"[SizeDetect] cleared operation for p{page_idx+1}")

    # --- 重置操作 / Reset operations ---
    def _reset_ops(self):
        if not (self._pending_crops or self._pending_deletes or self._pending_scales):
            return
        reply = QMessageBox.question(
            self, tr("size_detect_reset_ops"),
            tr("size_detect_reset_ops") + "?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self._pending_crops.clear()
        self._pending_deletes.clear()
        self._pending_scales.clear()
        self._update_all_ops()
        log_info("[SizeDetect] all operations reset")

    # --- 导出所有 / Export all ---
    def _export_all(self):
        if not self._result or not self._result.get('majority_size'):
            QMessageBox.warning(self, tr("invalid_input"),
                                tr("size_detect_no_majority"))
            return
        total_ops = (len(self._pending_crops) + len(self._pending_deletes)
                     + len(self._pending_scales))
        if total_ops == 0:
            QMessageBox.information(self, tr("size_detect_summary_title"),
                                    tr("size_detect_no_ops"))
            return
        out_dir = self._out_dir.path()
        if not out_dir:
            QMessageBox.warning(self, tr("invalid_input"), tr("no_output_dir"))
            return

        # 构建摘要 / Build summary
        summary = self._build_summary()
        reply = QMessageBox.question(
            self, tr("size_detect_summary_title"),
            summary,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        name = (os.path.splitext(os.path.basename(self._src_path))[0]
                + "_size_fixed.pdf")
        out_path = os.path.join(out_dir, name)
        if os.path.abspath(out_path) == os.path.abspath(self._src_path):
            QMessageBox.warning(self, tr("invalid_input"), tr("err_same_output"))
            return

        maj = self._result['majority_size']
        log_info(f"[SizeDetect] export: crop={len(self._pending_crops)} "
                 f"delete={len(self._pending_deletes)} "
                 f"scale={len(self._pending_scales)}")
        self._pending_out_path = out_path
        self.start_worker(
            pdf_core.apply_size_operations, self._src_path, out_path,
            self._pending_crops, self._pending_deletes,
            self._pending_scales, maj)

    def _build_summary(self) -> str:
        """构建操作摘要文本。"""
        n_crop = len(self._pending_crops)
        n_del = len(self._pending_deletes)
        n_scale = len(self._pending_scales)
        n_anom = len(self._result['anomaly_pages'])
        n_untreated = n_anom - n_crop - n_del - n_scale
        n_majority = self._total_pages - n_anom
        new_total = self._total_pages - n_del

        lines = [tr("size_detect_summary_text"), ""]
        if n_crop:
            crop_pages = sorted(p + 1 for p in self._pending_crops)
            lines.append(f"  • {tr('size_detect_sum_crop', n=n_crop)}: "
                         f"p{', p'.join(str(p) for p in crop_pages)}")
        if n_del:
            del_pages = sorted(p + 1 for p in self._pending_deletes)
            lines.append(f"  • {tr('size_detect_sum_delete', n=n_del)}: "
                         f"p{', p'.join(str(p) for p in del_pages)}")
        if n_scale:
            scale_pages = sorted(p + 1 for p in self._pending_scales)
            lines.append(f"  • {tr('size_detect_sum_scale', n=n_scale)}: "
                         f"p{', p'.join(str(p) for p in scale_pages)}")
        if n_untreated > 0:
            lines.append(f"  • {tr('size_detect_sum_untreated', n=n_untreated)}")
        lines.append(f"  • {tr('size_detect_sum_majority', n=n_majority)}")
        lines.append("")
        lines.append(f"  {tr('size_detect_sum_total', old=self._total_pages, new=new_total)}")
        return "\n".join(lines)

    # --- 成功回调 / Success callback ---
    def on_success(self, result):
        out_path = getattr(self, "_pending_out_path", "")
        QMessageBox.information(
            self, tr("success"),
            tr("size_detect_export_success", n=result, path=out_path))
        log_info(f"[SizeDetect] export done: {result} pages → {out_path}")

    # --- 翻译 / Translation ---
    def title_key(self):
        return "tab_size_detect"

    def desc_key(self):
        return "size_detect_desc"

    def _do_retranslate(self):
        self._src_label.setText(tr("size_detect_source") + ":")
        self._src_btn.setText(tr("browse"))
        self._settings_btn.setText(tr("size_detect_settings_btn"))
        self._tol_label.setText(tr("size_detect_tolerance"))
        self._maj_label.setText(tr("size_detect_majority_mode") + ":")
        # 更新主尺寸下拉 i18n: auto / Custom
        for i in range(self._maj_combo.count()):
            key = self._maj_combo.itemData(i)
            if key == "auto":
                self._maj_combo.setItemText(i, tr("size_detect_maj_auto"))
            elif key == "Custom":
                self._maj_combo.setItemText(i, tr("size_detect_maj_custom"))
        self._maj_w_label.setText(tr("settings_width"))
        self._maj_h_label.setText(tr("settings_height"))
        self._detect_btn.setText(tr("size_detect_run"))
        self._tip_label.setText(tr("size_detect_tip"))
        self._reset_btn.setText(tr("size_detect_reset_ops"))
        self._export_btn.setText(tr("size_detect_export_all"))
        self._table.setHorizontalHeaderLabels([
            "Page / 页码", "Size (pt) / 尺寸",
            "Size (mm) / 尺寸", "Paper / 纸张",
            "Status / 状态", "Operation / 操作"])
        self._update_maj_widgets()
        self._update_ops_label()
        if self._result:
            self._update_summary()
            self._update_all_ops()


# ===========================================================================
# 11. Settings Dialog / 设置对话框
# ===========================================================================

class SettingsDialog(QDialog):
    """三 Tab 设置: 通用 / 尺寸检测 / 裁剪。持久化到 settings.json。"""

    MAJORITY_MODES = ["auto", "A2", "A3", "A4", "A5", "Letter", "Legal", "Custom"]
    CROP_MODES = ["free", "A5", "A4", "A3", "Letter", "Legal", "Custom"]
    LANGS = [("简体中文", "zh_CN"), ("English", "en_US")]

    def __init__(self, parent=None):
        super().__init__(parent)
        from settings import SettingsManager
        self._s = SettingsManager.instance()
        self._build_ui()
        self._load_from_settings()
        self.retranslate()

    def _build_ui(self):
        self.setWindowTitle(tr("settings_title"))
        self.resize(560, 520)
        lay = QVBoxLayout(self)

        self._tabs = QTabWidget()
        lay.addWidget(self._tabs, 1)

        # --- Tab 1: 通用 / General ---
        t1 = QWidget()
        g = QGridLayout(t1)
        g.setContentsMargins(16, 16, 16, 16)
        g.setVerticalSpacing(10)
        self._lang_label = QLabel()
        self._lang_combo = QComboBox()
        for label, key in self.LANGS:
            self._lang_combo.addItem(label, key)
        self._outdir_label = QLabel()
        self._outdir_edit = QLineEdit()
        self._outdir_btn = QPushButton()
        self._outdir_btn.clicked.connect(self._browse_outdir)
        out_row = QHBoxLayout()
        out_row.addWidget(self._outdir_edit, 1)
        out_row.addWidget(self._outdir_btn)
        g.addWidget(self._lang_label, 0, 0)
        g.addWidget(self._lang_combo, 0, 1)
        g.addWidget(self._outdir_label, 1, 0)
        g.addLayout(out_row, 1, 1)
        g.setRowStretch(10, 1)
        self._tabs.addTab(t1, "")

        # --- Tab 2: 尺寸检测 / Size detection ---
        t2 = QWidget()
        g2 = QGridLayout(t2)
        g2.setContentsMargins(16, 16, 16, 16)
        g2.setVerticalSpacing(10)
        self._tol_label2 = QLabel()
        self._tol_spin2 = QSpinBox()
        self._tol_spin2.setRange(1, 50)
        self._maj_label2 = QLabel()
        self._maj_combo2 = QComboBox()
        for m in self.MAJORITY_MODES:
            self._maj_combo2.addItem(m, m)
        self._maj_combo2.currentIndexChanged.connect(self._on_maj_mode_changed)
        self._maj_hint = QLabel()
        self._maj_hint.setStyleSheet("color:#7f8c8d; font-size:11px;")
        self._maj_hint.setWordWrap(True)
        self._mj_w_label = QLabel()
        self._mj_w_spin = QDoubleSpinBox()
        self._mj_w_spin.setRange(1, 99999)
        self._mj_w_spin.setDecimals(1)
        self._mj_w_spin.setSuffix(" pt")
        self._mj_h_label = QLabel()
        self._mj_h_spin = QDoubleSpinBox()
        self._mj_h_spin.setRange(1, 99999)
        self._mj_h_spin.setDecimals(1)
        self._mj_h_spin.setSuffix(" pt")
        self._mj_mm_label = QLabel()
        self._mj_mm_label.setStyleSheet("color:#7f8c8d; font-size:11px;")
        self._mj_w_spin.valueChanged.connect(self._on_maj_custom_changed)
        self._mj_h_spin.valueChanged.connect(self._on_maj_custom_changed)
        g2.addWidget(self._tol_label2, 0, 0)
        g2.addWidget(self._tol_spin2, 0, 1)
        g2.addWidget(self._maj_label2, 1, 0)
        g2.addWidget(self._maj_combo2, 1, 1)
        g2.addWidget(self._maj_hint, 2, 1)
        g2.addWidget(self._mj_w_label, 3, 0)
        g2.addWidget(self._mj_w_spin, 3, 1)
        g2.addWidget(self._mj_h_label, 4, 0)
        g2.addWidget(self._mj_h_spin, 4, 1)
        g2.addWidget(self._mj_mm_label, 5, 1)
        g2.setRowStretch(10, 1)
        self._tabs.addTab(t2, "")

        # --- Tab 3: 裁剪 / Crop ---
        t3 = QWidget()
        g3 = QGridLayout(t3)
        g3.setContentsMargins(16, 16, 16, 16)
        g3.setVerticalSpacing(10)
        self._crop_mode_label = QLabel()
        self._crop_mode_combo = QComboBox()
        for m in self.CROP_MODES:
            self._crop_mode_combo.addItem(m, m)
        self._crop_mode_combo.currentIndexChanged.connect(self._on_crop_mode_changed)
        self._crop_hint = QLabel()
        self._crop_hint.setStyleSheet("color:#7f8c8d; font-size:11px;")
        self._crop_hint.setWordWrap(True)
        self._cr_w_label = QLabel()
        self._cr_w_spin = QDoubleSpinBox()
        self._cr_w_spin.setRange(1, 99999)
        self._cr_w_spin.setDecimals(1)
        self._cr_w_spin.setSuffix(" pt")
        self._cr_h_label = QLabel()
        self._cr_h_spin = QDoubleSpinBox()
        self._cr_h_spin.setRange(1, 99999)
        self._cr_h_spin.setDecimals(1)
        self._cr_h_spin.setSuffix(" pt")
        self._cr_mm_label = QLabel()
        self._cr_mm_label.setStyleSheet("color:#7f8c8d; font-size:11px;")
        self._cr_w_spin.valueChanged.connect(self._on_crop_custom_changed)
        self._cr_h_spin.valueChanged.connect(self._on_crop_custom_changed)
        g3.addWidget(self._crop_mode_label, 0, 0)
        g3.addWidget(self._crop_mode_combo, 0, 1)
        g3.addWidget(self._crop_hint, 1, 1)
        g3.addWidget(self._cr_w_label, 2, 0)
        g3.addWidget(self._cr_w_spin, 2, 1)
        g3.addWidget(self._cr_h_label, 3, 0)
        g3.addWidget(self._cr_h_spin, 3, 1)
        g3.addWidget(self._cr_mm_label, 4, 1)
        g3.setRowStretch(10, 1)
        self._tabs.addTab(t3, "")

        # --- 底部按钮 / Bottom buttons ---
        btn_row = QHBoxLayout()
        self._reset_btn = QPushButton()
        self._reset_btn.clicked.connect(self._reset_defaults)
        self._cancel_btn = QPushButton()
        self._cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton()
        self._ok_btn.setStyleSheet(
            "QPushButton{background:#27ae60; color:white; border:none;"
            "border-radius:4px; padding:8px 24px; font-weight:bold;}"
            "QPushButton:hover{background:#229954;}")
        self._ok_btn.clicked.connect(self._save_and_accept)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._ok_btn)
        lay.addLayout(btn_row)

    # --- Load / Save ---
    def _load_from_settings(self):
        # Tab1: General
        lang = self._s.get("default_language", "zh_CN")
        idx = self._lang_combo.findData(lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._outdir_edit.setText(self._s.get("default_output_dir", ""))

        # Tab2: Detect
        self._tol_spin2.setValue(int(self._s.get("detect_tolerance_pt", 2)))
        m = self._s.get("detect_majority_mode", "auto")
        idx = self._maj_combo2.findData(m)
        self._maj_combo2.setCurrentIndex(max(0, idx))
        self._mj_w_spin.setValue(float(self._s.get("detect_majority_custom_w", 595)))
        self._mj_h_spin.setValue(float(self._s.get("detect_majority_custom_h", 842)))

        # Tab3: Crop
        cm = self._s.get("crop_default_mode", "free")
        idx = self._crop_mode_combo.findData(cm)
        self._crop_mode_combo.setCurrentIndex(max(0, idx))
        self._cr_w_spin.setValue(float(self._s.get("crop_custom_w", 595)))
        self._cr_h_spin.setValue(float(self._s.get("crop_custom_h", 842)))

        self._on_maj_mode_changed()
        self._on_crop_mode_changed()

    def _save_and_accept(self):
        self._s.set("default_language", self._lang_combo.currentData())
        self._s.set("default_output_dir", self._outdir_edit.text().strip())
        self._s.set("detect_tolerance_pt", int(self._tol_spin2.value()))
        self._s.set("detect_majority_mode", self._maj_combo2.currentData())
        self._s.set("detect_majority_custom_w", float(self._mj_w_spin.value()))
        self._s.set("detect_majority_custom_h", float(self._mj_h_spin.value()))
        self._s.set("crop_default_mode", self._crop_mode_combo.currentData())
        self._s.set("crop_custom_w", float(self._cr_w_spin.value()))
        self._s.set("crop_custom_h", float(self._cr_h_spin.value()))
        self._s.save()
        log_info("[Settings] saved.")
        self.accept()

    def _reset_defaults(self):
        from settings import DEFAULTS
        self._s.update(DEFAULTS)
        self._load_from_settings()

    # --- Handlers ---
    def _browse_outdir(self):
        d = QFileDialog.getExistingDirectory(self, tr("choose_dir"))
        if d:
            self._outdir_edit.setText(d)

    def _on_maj_mode_changed(self, *_):
        custom = (self._maj_combo2.currentData() == "Custom")
        auto = (self._maj_combo2.currentData() == "auto")
        self._mj_w_label.setEnabled(custom)
        self._mj_w_spin.setEnabled(custom)
        self._mj_h_label.setEnabled(custom)
        self._mj_h_spin.setEnabled(custom)
        self._mj_w_label.setVisible(not auto)
        self._mj_w_spin.setVisible(not auto)
        self._mj_h_label.setVisible(not auto)
        self._mj_h_spin.setVisible(not auto)
        self._mj_mm_label.setVisible(not auto)
        self._update_mm(self._mj_w_spin, self._mj_h_spin, self._mj_mm_label)

    def _on_maj_custom_changed(self, *_):
        self._update_mm(self._mj_w_spin, self._mj_h_spin, self._mj_mm_label)

    def _on_crop_mode_changed(self, *_):
        mode = self._crop_mode_combo.currentData()
        custom = (mode == "Custom")
        free = (mode == "free")
        self._cr_w_label.setEnabled(custom)
        self._cr_w_spin.setEnabled(custom)
        self._cr_h_label.setEnabled(custom)
        self._cr_h_spin.setEnabled(custom)
        self._cr_w_label.setVisible(not free)
        self._cr_w_spin.setVisible(not free)
        self._cr_h_label.setVisible(not free)
        self._cr_h_spin.setVisible(not free)
        self._cr_mm_label.setVisible(not free)
        self._update_mm(self._cr_w_spin, self._cr_h_spin, self._cr_mm_label)

    def _on_crop_custom_changed(self, *_):
        self._update_mm(self._cr_w_spin, self._cr_h_spin, self._cr_mm_label)

    @staticmethod
    def _update_mm(ws, hs, label):
        w, h = ws.value(), hs.value()
        label.setText(
            f"  ≈  {w * 25.4 / 72:.1f} × {h * 25.4 / 72:.1f} mm")

    def retranslate(self):
        self.setWindowTitle(tr("settings_title"))
        self._tabs.setTabText(0, tr("settings_tab_general"))
        self._tabs.setTabText(1, tr("settings_tab_detect"))
        self._tabs.setTabText(2, tr("settings_tab_crop"))
        self._lang_label.setText(tr("settings_default_lang"))
        self._outdir_label.setText(tr("settings_default_outdir"))
        self._outdir_btn.setText(tr("settings_browse"))
        self._tol_label2.setText(tr("settings_detect_tol"))
        self._maj_label2.setText(tr("settings_detect_majority"))
        self._maj_hint.setText(tr("settings_detect_majority_hint"))
        self._mj_w_label.setText(tr("settings_width"))
        self._mj_h_label.setText(tr("settings_height"))
        self._crop_mode_label.setText(tr("settings_crop_default_mode"))
        self._crop_hint.setText(tr("settings_crop_mode_hint"))
        self._cr_w_label.setText(tr("settings_width"))
        self._cr_h_label.setText(tr("settings_height"))
        self._reset_btn.setText(tr("settings_reset"))
        self._cancel_btn.setText(tr("cancel"))
        self._ok_btn.setText(tr("ok"))
        # i18n for mode combos
        for i in range(self._maj_combo2.count()):
            key = self._maj_combo2.itemData(i)
            if key == "auto":
                self._maj_combo2.setItemText(i, tr("size_detect_maj_auto"))
            elif key == "Custom":
                self._maj_combo2.setItemText(i, tr("size_detect_maj_custom"))
        for i in range(self._crop_mode_combo.count()):
            key = self._crop_mode_combo.itemData(i)
            if key == "free":
                self._crop_mode_combo.setItemText(i, tr("size_detect_crop_free"))
            elif key == "Custom":
                self._crop_mode_combo.setItemText(i, tr("size_detect_maj_custom"))
        self._on_maj_mode_changed()
        self._on_crop_mode_changed()
