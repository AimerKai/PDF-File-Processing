# -*- coding: utf-8 -*-
"""
log_window.py - 全局日志管理器 + 独立日志窗口

提供 logger 单例，任何模块都可调用 log_info/log_warn/log_error 写日志。
LogWindow 是独立窗口，实时显示日志，支持级别颜色、时间戳、过滤、清空、保存。
"""

from datetime import datetime
from typing import List, Optional

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QTextCursor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
    QComboBox, QCheckBox
)


# 日志级别 / Log levels
INFO = "INFO"
WARN = "WARN"
ERROR = "ERROR"

# 级别颜色 / Level colors
_LEVEL_COLOR = {
    INFO:  QColor("#27ae60"),   # 绿 / green
    WARN:  QColor("#e67e22"),   # 橙 / orange
    ERROR: QColor("#e74c3c"),   # 红 / red
}


class Logger(QObject):
    """
    全局日志管理器 (单例)。
    通过 log_signal 广播每条日志，LogWindow 订阅显示。
    内部保留全部历史，新窗口打开时可回填。
    """
    log_signal = pyqtSignal(str, str)  # (level, message)

    def __init__(self):
        super().__init__()
        self._history: List[tuple] = []  # [(timestamp, level, message), ...]

    def log(self, level: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._history.append((ts, level, message))
        # 历史上限 5000 条，避免内存膨胀 / Cap history
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
        self.log_signal.emit(level, f"[{ts}] {message}")

    def info(self, msg: str):
        self.log(INFO, msg)

    def warn(self, msg: str):
        self.log(WARN, msg)

    def error(self, msg: str):
        self.log(ERROR, msg)

    def history(self) -> List[tuple]:
        return list(self._history)

    def clear(self):
        self._history.clear()


# 全局单例 / Global singleton
logger = Logger()


# 便捷函数 / Convenience functions
def log_info(msg: str):
    logger.info(msg)


def log_warn(msg: str):
    logger.warn(msg)


def log_error(msg: str):
    logger.error(msg)


class LogWindow(QDialog):
    """独立日志窗口。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log / 日志")
        self.resize(760, 520)
        self._build_ui()
        # 订阅日志信号 / Subscribe to logger
        logger.log_signal.connect(self._append_log)
        # 回填历史 / Backfill history
        self._backfill_history()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # 顶部工具栏 / Top toolbar
        top = QHBoxLayout()
        self._filter_label = QLabel("Filter:")
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["ALL", INFO, WARN, ERROR])
        self._filter_combo.currentTextChanged.connect(self._refilter)
        self._autoscroll_cb = QCheckBox("Auto-scroll")
        self._autoscroll_cb.setChecked(True)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear)
        self._save_btn = QPushButton("Save Log...")
        self._save_btn.clicked.connect(self._save_log)
        top.addWidget(self._filter_label)
        top.addWidget(self._filter_combo)
        top.addWidget(self._autoscroll_cb)
        top.addStretch(1)
        top.addWidget(self._clear_btn)
        top.addWidget(self._save_btn)
        v.addLayout(top)

        # 日志文本框 / Log text box
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 9))
        self._text.setStyleSheet(
            "QTextEdit { background: #1e1e1e; color: #d4d4d4; }")
        v.addWidget(self._text, 1)

        # 状态栏 / Status bar
        self._count_label = QLabel("0 lines")
        v.addWidget(self._count_label)

    def _append_log(self, level: str, message: str):
        """实时追加一条日志 (带颜色)。"""
        # 若当前过滤不匹配则跳过显示 (但仍记录) / Skip if filtered
        cur_filter = self._filter_combo.currentText()
        if cur_filter != "ALL" and level != cur_filter:
            self._update_count()
            return

        color = _LEVEL_COLOR.get(level, QColor("#d4d4d4"))
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message + "\n", fmt)
        self._text.setTextCursor(cursor)

        if self._autoscroll_cb.isChecked():
            self._text.ensureCursorVisible()
        self._update_count()

    def _backfill_history(self):
        """打开时回填全部历史日志。"""
        cur_filter = self._filter_combo.currentText()
        cursor = self._text.textCursor()
        for ts, level, msg in logger.history():
            if cur_filter != "ALL" and level != cur_filter:
                continue
            color = _LEVEL_COLOR.get(level, QColor("#d4d4d4"))
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(f"[{ts}] {msg}\n", fmt)
        self._text.setTextCursor(cursor)
        if self._autoscroll_cb.isChecked():
            self._text.ensureCursorVisible()
        self._update_count()

    def _refilter(self):
        """切换过滤级别时重建视图。"""
        self._text.clear()
        self._backfill_history()

    def _clear(self):
        self._text.clear()
        self._update_count()

    def _save_log(self):
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "pdf_toolkit.log", "Log Files (*.log *.txt);;All (*.*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for ts, level, msg in logger.history():
                    f.write(f"[{ts}] [{level}] {msg}\n")
            logger.info(f"Log saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save log: {e}")

    def _update_count(self):
        total = len(logger.history())
        self._count_label.setText(f"{total} lines")

    def keyPressEvent(self, e):
        # ESC 不关闭，避免误关 / Don't close on ESC
        if e.key() != Qt.Key_Escape:
            super().keyPressEvent(e)
