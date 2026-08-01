# -*- coding: utf-8 -*-
"""
i18n.py - 中英双语文本国际化模块
Bilingual (Chinese/English) text registry.
"""

from PyQt5.QtCore import QObject, pyqtSignal


# 双语文本字典 - 所有界面字符串集中管理
# Bilingual text dictionary - all UI strings centralized
_STRINGS = {
    # ===== 应用通用 / App General =====
    "app_title":           ("PDF 工具箱", "PDF Toolkit"),
    "language_menu":       ("语言", "Language"),
    "tools_menu":          ("工具", "Tools"),
    "chinese":             ("中文", "Chinese"),
    "english":             ("英文", "English"),
    "file_menu":           ("文件", "File"),
    "help_menu":           ("帮助", "Help"),
    "exit":                ("退出", "Exit"),
    "about":               ("关于", "About"),
    "about_text":          ("PDF 工具箱 - 离线版\n基于 PyQt5 与 PyMuPDF\n完全本地处理，无需联网",
                            "PDF Toolkit - Offline\nPowered by PyQt5 & PyMuPDF\nFully local processing, no internet required"),

    # ===== 通用按钮 / Common Buttons =====
    "add_files":           ("添加文件", "Add Files"),
    "add_pdf":             ("添加 PDF", "Add PDF"),
    "remove":              ("移除", "Remove"),
    "remove_all":          ("清空", "Clear All"),
    "move_up":             ("上移", "Move Up"),
    "move_down":           ("下移", "Move Down"),
    "browse":              ("浏览...", "Browse..."),
    "execute":             ("执行", "Execute"),
    "run":                 ("开始处理", "Start"),
    "cancel":              ("取消", "Cancel"),
    "ok":                  ("确定", "OK"),
    "save_as":             ("另存为...", "Save As..."),
    "open_output":         ("打开输出目录", "Open Output Folder"),
    "select_output":       ("选择输出目录", "Select Output Folder"),
    "select_pdf":          ("选择 PDF 文件", "Select PDF File"),
    "select_pdfs":         ("选择 PDF 文件", "Select PDF Files"),

    # ===== 状态 / Status =====
    "ready":               ("就绪", "Ready"),
    "processing":          ("处理中...", "Processing..."),
    "done":                ("完成", "Done"),
    "success":             ("成功", "Success"),
    "failed":              ("失败", "Failed"),
    "canceled":            ("已取消", "Canceled"),
    "no_files":            ("请先添加文件", "Please add files first"),
    "no_output_dir":       ("请选择输出目录", "Please select an output directory"),
    "invalid_input":       ("输入无效", "Invalid input"),

    # ===== 标签页 / Tabs =====
    "tab_merge":           ("合并 PDF", "Merge PDF"),
    "tab_split":           ("拆分 PDF", "Split PDF"),
    "tab_compress":        ("压缩 PDF", "Compress PDF"),
    "tab_rotate":          ("旋转 PDF", "Rotate PDF"),
    "tab_organize":        ("页面管理", "Organize Pages"),
    "tab_extract":         ("提取页面", "Extract Pages"),

    # ===== 合并 / Merge =====
    "merge_desc":          ("按列表顺序将多个 PDF 合并为一个文件",
                            "Combine multiple PDFs into one file in list order"),
    "merge_files":         ("待合并文件 (按顺序)", "Files to Merge (in order)"),
    "merge_output_name":   ("输出文件名", "Output Filename"),
    "merge_success":       ("成功合并 {n} 个文件", "Successfully merged {n} files"),

    # ===== 拆分 / Split =====
    "split_desc":          ("将一个 PDF 拆分为多个文件",
                            "Split one PDF into multiple files"),
    "split_mode":          ("拆分模式", "Split Mode"),
    "split_each_page":     ("每页一个文件", "One file per page"),
    "split_by_range":      ("按页码范围", "By page ranges"),
    "split_ranges_hint":   ("页码范围，用逗号分隔，例如 1-3,5,7-9",
                            "Page ranges separated by commas, e.g. 1-3,5,7-9"),
    "split_prefix":        ("输出文件名前缀", "Output Filename Prefix"),
    "split_success":       ("成功拆分为 {n} 个文件", "Successfully split into {n} files"),

    # ===== 压缩 / Compress =====
    "compress_desc":       ("通过降低图像质量与采样率来减小 PDF 体积",
                            "Reduce PDF size by lowering image quality and sampling"),
    "compress_quality":    ("图像质量 (1-100)", "Image Quality (1-100)"),
    "compress_dpi":        ("图像 DPI", "Image DPI"),
    "compress_source":     ("源文件", "Source File"),
    "compress_original":   ("原始大小", "Original Size"),
    "compress_compressed": ("压缩后", "Compressed"),
    "compress_ratio":      ("压缩率", "Ratio"),
    "compress_success":    ("压缩完成: {old} -> {new}", "Compression done: {old} -> {new}"),

    # ===== 旋转 / Rotate =====
    "rotate_desc":         ("旋转 PDF 的全部或部分页面",
                            "Rotate all or part of PDF pages"),
    "rotate_angle":        ("旋转角度", "Rotation Angle"),
    "rotate_90":           ("顺时针 90°", "90° Clockwise"),
    "rotate_180":          ("180°", "180°"),
    "rotate_270":          ("逆时针 90°", "90° Counter-clockwise"),
    "rotate_pages":        ("应用页面 (留空=全部，例: 1-3,5)",
                            "Pages (empty=all, e.g. 1-3,5)"),
    "rotate_success":      ("旋转完成", "Rotation complete"),

    # ===== 页面管理 / Organize =====
    "organize_desc":       ("拖拽缩略图重排页面，右键删除或旋转单页",
                            "Drag thumbnails to reorder, right-click to delete or rotate"),
    "organize_load":       ("加载 PDF", "Load PDF"),
    "organize_save":       ("保存为新 PDF", "Save as New PDF"),
    "organize_rotate_page":("旋转此页", "Rotate This Page"),
    "organize_delete_page":("删除此页", "Delete This Page"),
    "organize_extract_page":("提取此页", "Extract This Page"),
    "organize_loaded":     ("已加载: {name} ({n} 页)", "Loaded: {name} ({n} pages)"),
    "organize_success":    ("页面管理完成", "Page organization complete"),

    # ===== 提取 / Extract =====
    "extract_desc":        ("从 PDF 中提取指定页面为单独文件",
                            "Extract specified pages from PDF as a separate file"),
    "extract_source":      ("源文件", "Source File"),
    "extract_pages":       ("要提取的页面 (例: 1-3,5,7-9)",
                            "Pages to extract (e.g. 1-3,5,7-9)"),
    "extract_output":      ("输出文件名", "Output Filename"),
    "extract_success":     ("成功提取 {n} 页", "Successfully extracted {n} pages"),

    # ===== 错误 / Errors =====
    "err_open_pdf":        ("无法打开 PDF: {msg}", "Failed to open PDF: {msg}"),
    "err_save_pdf":        ("无法保存 PDF: {msg}", "Failed to save PDF: {msg}"),
    "err_no_pdf":          ("未选择 PDF 文件", "No PDF file selected"),
    "err_invalid_range":   ("页码范围格式错误: {rng}", "Invalid page range: {rng}"),
    "err_page_out":        ("页码超出范围: {p} (共 {n} 页)",
                            "Page out of range: {p} (of {n} pages)"),
    "err_same_output":     ("输出文件不能与源文件相同", "Output cannot be the same as source"),
    "err_compress":        ("压缩失败: {msg}", "Compression failed: {msg}"),

    # ===== 页面检测 / Page Detection =====
    "tab_detect":          ("页面检测", "Page Detection"),
    "detect_desc":         ("扫描 PDF 中的空白页与重复页，标记可疑页面并可一键删除",
                            "Scan PDF for blank and duplicate pages, mark suspicious ones, delete in batch"),
    "detect_source":       ("源文件", "Source File"),
    "detect_blank_thr":    ("白度阈值 (%)", "Whiteness Threshold (%)"),
    "detect_blank_tip":    ("页面白色像素占比≥此值判为空白；扫描噪点空白页(标准差<5)自动识别",
                            "Page with white%≥this is blank; uniform-noise blank pages (std<5) auto-detected"),
    "detect_dup_thr":      ("重复相似度阈值 (汉明距离)", "Duplicate Threshold (Hamming)"),
    "detect_run_blank":    ("检测空白页", "Detect Blank Pages"),
    "detect_run_dup":      ("检测重复页", "Detect Duplicates"),
    "detect_run_all":      ("全部检测", "Detect All"),
    "detect_results":      ("检测结果", "Results"),
    "detect_blank_found":  ("发现 {n} 个空白页", "Found {n} blank pages"),
    "detect_blank_none":   ("未发现空白页", "No blank pages found"),
    "detect_dup_found":    ("发现 {n} 组重复页", "Found {n} duplicate groups"),
    "detect_dup_none":     ("未发现重复页", "No duplicate pages found"),
    "detect_dup_group":    ("第 {g} 组 (共 {n} 页)", "Group {g} ({n} pages)"),
    "detect_no_result":    ("尚无检测结果，请先执行检测", "No results yet, run detection first"),
    "detect_select_all_blank": ("全选空白页", "Select All Blank"),
    "detect_select_all_dup":   ("全选重复页(每组留首页)", "Select All Dup (keep first)"),
    "detect_select_none":  ("取消选择", "Select None"),
    "detect_delete_sel":   ("删除已选页面", "Delete Selected Pages"),
    "detect_marked_pages": ("已标记 {n} 页待删除", "{n} pages marked for deletion"),
    "detect_export":       ("导出报告", "Export Report"),
    "detect_delete_success": ("已删除 {n} 页，输出 {m} 页",
                              "Deleted {n} pages, output has {m} pages"),
    "detect_scanning":     ("扫描中...", "Scanning..."),
    "detect_blank_tag":    ("空白页", "Blank page"),
    "detect_dup_tag":      ("重复页", "Duplicate page"),

    # ===== 页面预览 / Page Preview =====
    "preview_title":       ("页面预览", "Page Preview"),
    "preview_hint":        ("点击结果表格中的任意一行查看该页", "Click any row in the results table to preview that page"),
    "preview_loading":     ("正在加载预览...", "Loading preview..."),
    "preview_page":        ("第 {n} 页 / 共 {t} 页", "Page {n} / {t}"),
    "preview_whiteness":   ("白度", "Whiteness"),
    "preview_mean":        ("平均亮度", "Mean Brightness"),
    "preview_std":         ("标准差", "Std Dev"),
    "preview_status":      ("判定", "Status"),
    "preview_blank":       ("空白页", "Blank"),
    "preview_normal":      ("正常页", "Normal"),
    "preview_prev":        ("上一页", "Prev Page"),
    "preview_next":        ("下一页", "Next Page"),

    # ===== 裁剪 PDF / Crop PDF =====
    "tab_crop":            ("裁剪 PDF", "Crop PDF"),
    "crop_desc":           ("在页面上拖拽框选裁剪区域，可应用到所有相同尺寸页或自定义页码范围",
                            "Drag to select crop area on page, apply to all same-size pages or custom page range"),
    "crop_source":         ("源文件", "Source File"),
    "crop_ref_page":       ("参考页", "Reference Page"),
    "crop_load":           ("加载预览", "Load Preview"),
    "crop_hint":           ("在预览图上按住鼠标拖拽，框选要保留的裁剪区域",
                            "Drag mouse on the preview to select the crop area to keep"),
    "crop_region":         ("裁剪区域", "Crop Region"),
    "crop_apply_to":       ("应用到", "Apply To"),
    "crop_same_size":      ("所有相同尺寸页", "All same-size pages"),
    "crop_custom":         ("自定义页码", "Custom pages"),
    "crop_custom_hint":    ("页码如 1-3,5,7-9 (留空=全部)", "e.g. 1-3,5,7-9 (empty=all)"),
    "crop_reset":          ("重置选区", "Reset Selection"),
    "crop_no_selection":   ("请先在预览图上拖拽选择裁剪区域", "Please drag to select a crop area on the preview first"),
    "crop_no_preview":     ("请先加载预览图", "Please load the preview first"),
    "crop_success":        ("已裁剪 {n} 页，共 {m} 页", "Cropped {n} pages of {m} total"),
    "crop_same_size_info": ("相同尺寸页: {n} 页", "Same-size pages: {n}"),
    "crop_width":          ("宽", "Width"),
    "crop_height":         ("高", "Height"),
    "crop_too_small":      ("裁剪区域太小，请重新框选", "Crop area too small, please re-select"),

    # ===== 批量删除 / Batch Delete =====
    "batch_select":        ("多选模式", "Multi-select"),
    "batch_select_hint":   ("多选模式下点击缩略图可选中/取消 (单选模式下可拖拽排序)",
                            "In multi-select mode, click to toggle selection (in single mode, drag to reorder)"),
    "batch_delete":        ("批量删除选中", "Batch Delete Selected"),
    "batch_selected":      ("已选 {n} 页", "{n} pages selected"),
    "batch_confirm":       ("确定删除选中的 {n} 页？", "Delete {n} selected pages?"),

    # ===== 尺寸检测 / Size Detection =====
    "tab_size_detect":     ("尺寸检测", "Size Detection"),
    "size_detect_desc":    ("扫描 PDF 中所有页面尺寸，自动识别主尺寸并标记异常尺寸页 (如 A4 文档中混入 A3)",
                            "Scan all page sizes in PDF, auto-identify majority size and flag anomalous pages (e.g. A3 in A4 doc)"),
    "size_detect_source":  ("源文件", "Source File"),
    "size_detect_run":     ("检测尺寸", "Detect Sizes"),
    "size_detect_tolerance": ("分组容差 (pt)", "Group Tolerance (pt)"),
    "size_detect_summary": ("尺寸汇总", "Size Summary"),
    "size_detect_majority":("主尺寸", "Majority"),
    "size_detect_anomaly": ("异常", "Anomaly"),
    "size_detect_no_anomaly": ("所有页面尺寸一致，未发现异常", "All pages have the same size, no anomalies found"),
    "size_detect_found":   ("发现 {n} 个异常尺寸页面", "Found {n} anomalous pages"),
    "size_detect_marked":  ("已选 {n} 页", "{n} pages selected"),
    "size_detect_sel_anom":("全选异常页", "Select All Anomalies"),
    "size_detect_sel_none":("取消选择", "Select None"),
    "size_detect_crop":    ("裁剪到主尺寸", "Crop to Majority"),
    "size_detect_scale":   ("缩放到主尺寸", "Scale to Majority"),
    "size_detect_delete":  ("删除选中页", "Delete Selected"),
    "size_detect_extract": ("提取选中页", "Extract Selected"),
    "size_detect_export":  ("导出报告", "Export Report"),
    "size_detect_crop_success": ("已裁剪 {n} 页到主尺寸，共 {m} 页",
                                 "Cropped {n} pages to majority size, {m} total"),
    "size_detect_scale_success": ("已缩放 {n} 页到主尺寸，共 {m} 页",
                                  "Scaled {n} pages to majority size, {m} total"),
    "size_detect_no_majority": ("无法确定主尺寸 (页面尺寸过于分散)", "Cannot determine majority size (sizes too scattered)"),
    "size_detect_no_selection": ("请先在表格中勾选要处理的页面", "Please check pages in the table first"),
    "size_detect_tip":     ("提示: 双击异常页可打开裁剪对话框；右键可标记删除/缩放；全部处理完后点击「导出所有」",
                            "Tip: Double-click anomalous page to crop; right-click to mark delete/scale; click Export All when done"),
    "size_detect_majority_mode": ("主尺寸模式", "Majority Mode"),
    "size_detect_maj_auto":   ("自动(多数页)", "Auto (Majority)"),
    "size_detect_maj_custom": ("自定义", "Custom"),
    "size_detect_settings_btn": ("全局设置", "Settings"),
    "size_detect_crop_mode": ("裁剪尺寸模式", "Crop Size Mode"),
    "size_detect_crop_free":  ("自由尺寸", "Free"),
    "size_detect_crop_locked":("锁定宽高", "Locked"),
    "size_detect_crop_orientation": ("裁剪方向", "Orientation"),
    "size_detect_crop_portrait": ("竖向(Portrait)", "Portrait"),
    "size_detect_crop_landscape": ("横向(Landscape)", "Landscape"),
    "size_detect_crop_size_mm": ("裁剪尺寸(mm)", "Crop Size (mm)"),
    "size_detect_export_all": ("导出所有", "Export All"),
    "size_detect_reset_ops":  ("重置操作", "Reset Operations"),
    "size_detect_op_none":    ("未处理", "Pending"),
    "size_detect_op_crop":    ("已裁剪", "Cropped"),
    "size_detect_op_delete":  ("待删除", "To Delete"),
    "size_detect_op_scale":   ("已缩放", "Scaled"),
    "size_detect_no_ops":     ("没有任何待导出的操作，请先双击异常页进行裁剪或右键标记操作",
                               "No operations to export. Please double-click anomalous pages to crop or right-click to mark operations"),
    "size_detect_summary_title": ("操作摘要确认", "Operation Summary"),
    "size_detect_summary_text":  ("请确认以下操作后点击「是」导出:", "Please review the following operations and click Yes to export:"),
    "size_detect_sum_crop":      ("裁剪: {n} 页", "Crop: {n} pages"),
    "size_detect_sum_delete":    ("删除: {n} 页", "Delete: {n} pages"),
    "size_detect_sum_scale":     ("缩放: {n} 页", "Scale: {n} pages"),
    "size_detect_sum_untreated": ("未处理异常页: {n} 页 (保持原样)", "Untreated anomalous: {n} pages (kept as-is)"),
    "size_detect_sum_majority":  ("主尺寸页: {n} 页 (未修改)", "Majority pages: {n} pages (unmodified)"),
    "size_detect_sum_total":     ("总页数: {old} → {new}", "Total pages: {old} → {new}"),
    "size_detect_export_success": ("导出成功！共 {n} 页，已保存到:\n{path}",
                                   "Export success! {n} pages, saved to:\n{path}"),
    "size_detect_ctx_crop":      ("裁剪此页...", "Crop This Page..."),
    "size_detect_ctx_scale":     ("缩放到主尺寸", "Scale to Majority"),
    "size_detect_ctx_delete":    ("标记删除", "Mark for Deletion"),
    "size_detect_ctx_clear":     ("取消操作", "Clear Operation"),

    # ===== 尺寸裁剪对话框 / Size Crop Dialog =====
    "size_crop_dialog_title": ("裁剪异常尺寸页面", "Crop Anomalous Pages"),
    "size_crop_target":    ("目标尺寸 (主尺寸)", "Target Size (Majority)"),
    "size_crop_page_info": ("第 {cur} / {total} 页 (p{page}, {paper} {w}x{h}mm)",
                            "Page {cur} / {total} (p{page}, {paper} {w}x{h}mm)"),
    "size_crop_apply_same":("将此裁剪应用到所有相同尺寸页", "Apply this crop to all same-size pages"),
    "size_crop_skip":      ("跳过此页", "Skip This Page"),
    "size_crop_warn_small": ("此页面小于目标尺寸，裁剪区域已自动限制在页面范围内",
                             "Page is smaller than target, crop area auto-limited to page bounds"),
    "size_crop_confirm":   ("确定裁剪", "Confirm Crop"),
    "size_crop_no_rect":   ("请先在预览图上拖拽或调整裁剪区域", "Please drag to select a crop area on the preview first"),
    "size_crop_apply_n":   ("此裁剪将应用到 {n} 页", "This crop will be applied to {n} pages"),

    # ===== 设置对话框 / Settings Dialog =====
    "settings_title":        ("全局设置", "Global Settings"),
    "settings_saved":        ("设置已保存", "Settings saved"),
    "settings_tab_general":  ("通用", "General"),
    "settings_tab_detect":   ("尺寸检测", "Size Detection"),
    "settings_tab_crop":     ("裁剪", "Crop"),
    "settings_default_lang": ("默认语言", "Default Language"),
    "settings_default_outdir": ("默认输出目录", "Default Output Dir"),
    "settings_detect_tol":   ("默认容差 (pt)", "Default Tolerance (pt)"),
    "settings_detect_majority": ("默认主尺寸模式", "Default Majority Mode"),
    "settings_detect_custom_size": ("自定义主尺寸 (pt)", "Custom Majority Size (pt)"),
    "settings_detect_majority_hint": (
        "「A3 扫描件偏多被误判为主尺寸」时可强制为 A4",
        "Force A4 when A3 scans exceed A4 pages"),
    "settings_crop_default_mode": ("默认裁剪模式", "Default Crop Mode"),
    "settings_crop_custom_size": ("自定义裁剪尺寸 (pt)", "Custom Crop Size (pt)"),
    "settings_crop_mode_hint": (
        "「自由」可任意框选；「固定尺寸」框体大小锁定，只能拖动",
        "Free = any box; Fixed = box size locked, only draggable"),
    "settings_width":  ("宽", "W"),
    "settings_height": ("高", "H"),
    "settings_reset":  ("恢复默认", "Reset Defaults"),
    "settings_browse": ("浏览...", "Browse..."),

    # ===== 日志窗口 / Log Window =====
    "log_menu":            ("视图", "View"),
    "open_log_window":     ("打开日志窗口", "Open Log Window"),
    "log_window_title":    ("日志 / Log", "Log"),
    "log_filter":          ("过滤", "Filter"),
    "log_autoscroll":      ("自动滚动", "Auto-scroll"),
    "log_clear":           ("清空", "Clear"),
    "log_save":            ("保存日志...", "Save Log..."),
    "log_lines":           ("{n} 条", "{n} lines"),
}


class Translator(QObject):
    """翻译器，全局单例，语言切换时发信号"""
    language_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._lang = "zh"  # 默认中文 / default Chinese

    def set_language(self, lang: str):
        """lang: 'zh' 或 'en'"""
        if lang in ("zh", "en") and lang != self._lang:
            self._lang = lang
            self.language_changed.emit()

    @property
    def lang(self) -> str:
        return self._lang

    def t(self, key: str, **kwargs) -> str:
        """翻译键值，支持 {占位符} 格式化"""
        entry = _STRINGS.get(key)
        if entry is None:
            return key
        text = entry[0] if self._lang == "zh" else entry[1]
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return text


# 全局翻译器实例 / Global translator instance
translator = Translator()


def tr(key: str, **kwargs) -> str:
    """快捷函数，外部直接 from i18n import tr"""
    return translator.t(key, **kwargs)
