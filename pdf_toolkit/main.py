# -*- coding: utf-8 -*-
"""
main.py - PDF 工具箱主程序入口
离线 PDF 处理工具，基于 PyQt5 + PyMuPDF。
"""

import sys
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QAction, QStatusBar, QMessageBox,
    QMenuBar, QMenu, QDialog
)

from i18n import translator, tr
from panels import (
    MergePanel, SplitPanel, CompressPanel, RotatePanel,
    ExtractPanel, OrganizePanel, DetectPanel, CropPanel,
    SizeDetectPanel, SettingsDialog
)
from log_window import LogWindow, log_info


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app_title"))
        self.resize(1000, 720)
        self.setMinimumSize(820, 600)
        self._log_window = None  # 延迟创建 / Lazy create

        # 启动时加载全局设置
        from settings import SettingsManager
        self._settings = SettingsManager.instance()
        # 默认语言
        lang_code = self._settings.get("default_language", "zh_CN")
        if lang_code.startswith("zh"):
            translator.set_language("zh")
        else:
            translator.set_language("en")

        self._build_tabs()
        self._build_menu()
        self._build_status()

        # 语言切换时全局刷新 / Refresh all on language change
        translator.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()
        log_info("[App] PDF Toolkit started")

    def _build_tabs(self):
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        # 按功能顺序添加面板 / Add panels in functional order
        self._panels = {
            "merge":    MergePanel(),
            "split":    SplitPanel(),
            "compress": CompressPanel(),
            "rotate":   RotatePanel(),
            "crop":     CropPanel(),
            "organize": OrganizePanel(),
            "detect":   DetectPanel(),
            "size_detect": SizeDetectPanel(),
            "extract":  ExtractPanel(),
        }
        for key in ("merge", "split", "compress", "rotate",
                    "crop", "organize", "detect", "size_detect", "extract"):
            self._tabs.addTab(self._panels[key], "")
        self.setCentralWidget(self._tabs)

    def _build_menu(self):
        mb = self.menuBar()

        # 文件菜单 / File menu
        self._file_menu = mb.addMenu("")
        self._exit_act = QAction("", self)
        self._exit_act.setShortcut("Ctrl+Q")
        self._exit_act.triggered.connect(self.close)
        self._file_menu.addAction(self._exit_act)

        # 视图菜单 (日志窗口) / View menu (log window)
        self._view_menu = mb.addMenu("")
        self._log_act = QAction("", self)
        self._log_act.setShortcut("Ctrl+L")
        self._log_act.triggered.connect(self._open_log_window)
        self._view_menu.addAction(self._log_act)

        # 工具菜单 (设置) / Tools menu (settings)
        self._tools_menu = mb.addMenu("")
        self._settings_act = QAction("", self)
        self._settings_act.setShortcut("Ctrl+,")
        self._settings_act.triggered.connect(self._open_settings)
        self._tools_menu.addAction(self._settings_act)

        # 语言菜单 / Language menu
        self._lang_menu = mb.addMenu("")
        self._zh_act = QAction("", self, checkable=True)
        self._zh_act.setChecked(True)
        self._zh_act.triggered.connect(lambda: self._switch_lang("zh"))
        self._en_act = QAction("", self, checkable=True)
        self._en_act.triggered.connect(lambda: self._switch_lang("en"))
        self._lang_menu.addAction(self._zh_act)
        self._lang_menu.addAction(self._en_act)

        # 帮助菜单 / Help menu
        self._help_menu = mb.addMenu("")
        self._about_act = QAction("", self)
        self._about_act.triggered.connect(self._show_about)
        self._help_menu.addAction(self._about_act)

    def _build_status(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = tr("ready")
        self._status.showMessage(self._status_label)

    def _switch_lang(self, lang: str):
        translator.set_language(lang)
        self._zh_act.setChecked(lang == "zh")
        self._en_act.setChecked(lang == "en")
        # 保存到全局设置
        code = "zh_CN" if lang == "zh" else "en_US"
        self._settings.set("default_language", code)
        self._settings.save()

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            # 如果默认语言有变化，立即切换
            code = self._settings.get("default_language", "zh_CN")
            targ = "zh" if code.startswith("zh") else "en"
            if targ != translator._lang:
                self._switch_lang(targ)
            # 刷新面板 (主尺寸/输出目录默认值等)
            for p in self._panels.values():
                if hasattr(p, "retranslate"):
                    p.retranslate()
                if hasattr(p, "_load_defaults"):
                    p._load_defaults()
            log_info("[App] settings applied")

    def _open_log_window(self):
        if self._log_window is None:
            self._log_window = LogWindow(self)
        self._log_window.show()
        self._log_window.raise_()
        self._log_window.activateWindow()

    def _show_about(self):
        QMessageBox.about(self, tr("about"), tr("about_text"))

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        # 菜单 / Menus
        self._file_menu.setTitle(tr("file_menu"))
        self._view_menu.setTitle(tr("log_menu"))
        self._tools_menu.setTitle(tr("tools_menu"))
        self._lang_menu.setTitle(tr("language_menu"))
        self._help_menu.setTitle(tr("help_menu"))
        self._exit_act.setText(tr("exit"))
        self._log_act.setText(tr("open_log_window"))
        self._settings_act.setText(tr("settings_title"))
        self._zh_act.setText(tr("chinese"))
        self._en_act.setText(tr("english"))
        self._about_act.setText(tr("about"))
        # 标签页 / Tabs (顺序须与 _build_tabs 一致)
        tab_keys = ["tab_merge", "tab_split", "tab_compress",
                    "tab_rotate", "tab_crop", "tab_organize",
                    "tab_detect", "tab_size_detect", "tab_extract"]
        for i, key in enumerate(tab_keys):
            self._tabs.setTabText(i, tr(key))
            self._tabs.setTabToolTip(i, tr(key))
        # 面板 / Panels
        for p in self._panels.values():
            p.retranslate()
        # 状态栏 / Status bar
        self._status.showMessage(tr("ready"))


def main():
    # 高 DPI 支持 / High DPI support
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(tr("app_title"))

    # 设置默认字体 / Set default font
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    # 全局样式 / Global stylesheet
    app.setStyleSheet("""
        QMainWindow { background: #ecf0f1; }
        QTabWidget::pane { border: 1px solid #bdc3c7; top: -1px; }
        QTabBar::tab {
            background: #bdc3c7; color: #2c3e50;
            padding: 8px 20px; margin-right: 2px;
            border-top-left-radius: 4px; border-top-right-radius: 4px;
        }
        QTabBar::tab:selected { background: #ffffff; font-weight: bold; }
        QTabBar::tab:hover { background: #d5dbdb; }
        QGroupBox {
            border: 1px solid #bdc3c7; border-radius: 4px;
            margin-top: 10px; padding-top: 8px;
            font-weight: bold; color: #34495e;
        }
        QGroupBox::title {
            subcontrol-origin: margin; left: 10px; padding: 0 4px;
        }
        QPushButton {
            background: #ffffff; border: 1px solid #bdc3c7;
            border-radius: 4px; padding: 6px 14px; color: #2c3e50;
        }
        QPushButton:hover { background: #ecf0f1; border-color: #3498db; }
        QPushButton:pressed { background: #d5dbdb; }
        QPushButton:disabled { color: #bdc3c7; }
        QLineEdit {
            border: 1px solid #bdc3c7; border-radius: 3px;
            padding: 5px 8px; background: #ffffff;
        }
        QLineEdit:focus { border-color: #3498db; }
        QListWidget {
            border: 1px solid #bdc3c7; border-radius: 3px;
            background: #ffffff; padding: 4px;
        }
        QProgressBar {
            border: 1px solid #bdc3c7; border-radius: 3px;
            background: #ffffff; text-align: center; height: 18px;
        }
        QProgressBar::chunk { background: #3498db; border-radius: 2px; }
        QScrollArea { border: 1px solid #bdc3c7; background: #ffffff; }
        QRadioButton, QCheckBox { color: #2c3e50; }
        QLabel { color: #2c3e50; }
        QStatusBar { background: #34495e; color: #ecf0f1; }
        QStatusBar::item { border: none; }
        QMenuBar { background: #2c3e50; color: #ecf0f1; }
        QMenuBar::item:selected { background: #34495e; }
        QMenu { background: #ffffff; color: #2c3e50; border: 1px solid #bdc3c7; }
        QMenu::item:selected { background: #3498db; color: #ffffff; }
    """)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
