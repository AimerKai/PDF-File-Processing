# PDF_for_everyone 工具箱 / PDF Toolkit

离线 PDF 处理工具，对标 ilovepdf 核心功能，**完全本地运行，无需联网**。
基于 PyQt5 + PyMuPDF 构建，桌面 GUI 应用，支持中英双语切换。

An offline PDF processing toolkit mimicking ilovepdf core features. **Fully local, no internet required.**
Built with PyQt5 + PyMuPDF, desktop GUI, bilingual (Chinese/English).

---

## 功能一览 / Features

| 标签页 Tab | 功能 Function |
|-----------|---------------|
| 合并 PDF / Merge | 多文件按顺序合并为一个 PDF，支持上下移动、拖拽排序 |
| 拆分 PDF / Split | 每页一文件 或 按页码范围拆分（如 `1-3,5,7-9`） |
| 压缩 PDF / Compress | 可调图像质量(1-100)与 DPI，栅格化重压，实测可达 5% 体积 |
| 旋转 PDF / Rotate | 90°/180°/270°，可选全部或指定页面 |
| 裁剪 PDF / Crop | **可视化拖拽框选裁剪区域，自动应用到所有相同尺寸页或自定义页码** |
| 页面管理 / Organize | 缩略图网格，拖拽重排，右键旋转/删除/提取，**多选批量删除** |
| 页面检测 / Detect | 扫描空白页与重复页，标记可疑页面，一键批量删除，导出报告 |
| **尺寸检测 / Size Detect** ✨ | **扫描每页尺寸，识别异常尺寸页（如扫描夹杂 A3/A4 混合），支持手动指定主尺寸；双击异常页进入可视化裁剪（支持 A3/A4/Letter 等固定尺寸框选）；批量裁剪/缩放/删除，导出前弹窗摘要确认** |
| 提取页面 / Extract | 按页码范围抽取为新 PDF |

---

## 尺寸异常检测工作流（新功能详解） / Size Detection Workflow

> **典型场景**：扫描 100 页文档，其中 2 页不小心被扫成了 A3，想把这 2 页裁剪为 A4。

### 第 1 步：检测

1. 选源 PDF
2. **容差**：默认 2 pt（尺寸在容差内视为同组）
3. **主尺寸模式**（关键）：
   - **自动（多数页）**：页数最多的尺寸组作主尺寸，其余为异常页
   - **A2 / A3 / A4 / A5 / Letter / Legal**：强制主尺寸为指定纸张，不论页数多少，所有不符的都判为异常页
   - **自定义**：手动填入宽高（pt，实时换算 mm）
4. 点 **「开始检测」**
5. 结果表格列出每页：页码、宽高(pt)、宽高(mm)、纸张名称、状态（主尺寸 / 异常）、操作（未处理 / 裁剪 / 缩放 / 删除）

> **提示**：当扫描出大量 A3 却其实 A4 才是"主尺寸"时，把"主尺寸模式"改成 **A4** 再检测就对了。

### 第 2 步：处理异常页

#### 方式 A：可视化裁剪（推荐）
- **双击表格中的任意一行** → 打开「异常裁剪对话框」
- **左侧**：缩略图列表（只列出该尺寸组的页），点击切换预览
- **中间大预览**：
  - 鼠标点一下空白 → 落下裁剪框
  - 点框内 → 拖动整个裁剪框
  - 点框的 8 个角/边 → 调整大小（**固定尺寸模式下无法调整大小**）
  - 蓝框内保留，框外半透明遮罩
  - 右下角实时显示当前框的 **pt / mm 尺寸**
- **顶部工具栏**：
  - **裁剪尺寸模式**：自由 / A5 / A4 / A3 / Letter / Legal / 自定义
  - **方向**：竖向 / 横向（非自由模式启用）
  - **自定义宽高**：仅自定义模式启用（pt，实时换算 mm）
  - **上一页 / 下一页**：逐页调整
  - **清除**：取消当前页裁剪
- 确定 → 回到尺寸检测面板，操作列显示「裁剪 N 页」

#### 方式 B：快速处理（右键菜单）
右键选中的页面可批量：
- 「设为裁剪」→ 默认居中裁剪到主尺寸
- 「设为缩放」→ 按比例缩放到主尺寸
- 「设为删除」→ 标记为要删除
- 「设为未处理」→ 取消标记
- 「裁剪所有异常页 (N)」→ 一键居中裁剪所有异常页

### 第 3 步：导出与摘要确认

点 **「导出所有」** → 弹出**操作摘要确认对话框**：
- 源文件路径、总页数
- 待删除页数（列出页码）
- 待裁剪页数（列出页码+框坐标）
- 待缩放学页数（列出页码+目标尺寸）
- 输出文件路径 + 预计输出页数

确认后输出新 PDF，所有操作一次应用。

---

## 全局设置 / Global Settings

**入口**：
1. 顶部菜单「工具 → 全局设置」，快捷键 `Ctrl+,`
2. 尺寸检测面板右上角「⚙ 全局设置」按钮

三个标签页：

| Tab | 设置项 |
|-----|-------|
| **通用** | 默认语言（简体中文 / English）、默认输出目录 |
| **尺寸检测** | 默认容差 pt、默认主尺寸模式（auto/A2~A5/Letter/Legal/自定义+宽高） |
| **裁剪** | 默认裁剪尺寸模式（自由/A5~A3/Letter/Legal/自定义+宽高） |

保存到 `%APPDATA%\pdf_toolkit\settings.json`，下次启动自动加载。

---

### 检测功能说明 / Detection Details (空白页/重复页)

- **空白页检测**：渲染每页为灰度图，统计非白像素占比，低于阈值(可调 0-100%)判定为空白页。
  对扫描件兼容，能识别近似空白页（带轻微噪点）。
- **重复页检测**：对每页计算感知哈希(aHash)，用汉明距离判定相似度（阈值可调 0-64），
  并查集分组，自动找出视觉重复的页面组。
- **批量删除**：检测结果以表格列出，每行带勾选框。可一键「全选空白页」「全选重复页(每组留首页)」，
  勾选后批量删除，输出清理后的新 PDF。
- **导出报告**：将检测结果导出为 txt 文本报告。

### 日志窗口 / Log Window

- 菜单「视图 → 打开日志窗口」或快捷键 `Ctrl+L` 打开。
- 实时显示所有操作日志，带时间戳与级别颜色（绿=INFO / 橙=WARN / 红=ERROR）。
- 可疑信息（发现的空白页、重复页、异常尺寸）会以 WARN 级别高亮提示。
- 支持按级别过滤、自动滚动、清空、保存为 .log 文件。
- 窗口关闭后再打开会回填全部历史日志。

---

## 快速开始 / Quick Start

### 方式 A：直接运行独立版（免安装，推荐）

将 `PDF_for_everyone\` 整个文件夹拷贝到任意 Windows 电脑，双击 `PDF_for_everyone.exe` 即可运行，**无需安装 Python 或任何依赖**。

> 采用 onedir 结构（单文件夹多文件），总大小约 55 MB，已内置 Python 运行时 + PyQt5 + PyMuPDF + Pillow。
> 首次启动需 2-3 秒。文件夹必须整体一起移动，不能只移动 exe。

### 方式 B：从源码运行

#### 1. 环境要求 / Requirements

- Python 3.8+（推荐 3.10+）
- 依赖：PyQt5、PyMuPDF、Pillow

#### 2. 安装依赖 / Install Dependencies

```powershell
cd c:\Users\KaiChen\Desktop\a\pdf_toolkit
python -m pip install -r requirements.txt
```

#### 3. 启动 / Launch

双击 `启动.bat`（自动查找装好依赖的 Python），或命令行：

```powershell
python main.py
```

> `启动.bat` 内置自动查找逻辑，优先用装了依赖的 Python 解释器。

## 输出文件命名 / Output Naming

选择源文件后，输出名会自动填充为 **原文件名 + 操作后缀**：

| 功能 | 输出示例（源: `刘善英.pdf`） |
|------|------------------------------|
| 合并 | `刘善英_merged.pdf` |
| 拆分 | `刘善英_split_001.pdf`、`刘善英_split_002.pdf`... |
| 压缩 | `刘善英_compressed.pdf` |
| 旋转 | `刘善英_rotated.pdf` |
| 裁剪 | `刘善英_cropped.pdf` |
| 页面管理 | `刘善英_organized.pdf` |
| 提取 | `刘善英_extracted.pdf` |
| 页面检测(空白/重复) | `刘善英_cleaned.pdf` |
| **尺寸检测** | `刘善英_resized.pdf` |

可在执行前手动修改输出名，不影响自动填充。

---

## 使用指南 / Usage Guide

### 合并 PDF / Merge
1. 点「添加文件」选择多个 PDF
2. 用「上移/下移」或直接拖拽调整顺序
3. 填输出文件名，选输出目录
4. 点「开始处理」

### 拆分 PDF / Split
1. 选源 PDF
2. 选模式：每页一文件 / 按页码范围
3. 范围模式填入如 `1-3,5,7-9`，每组生成一个文件
4. 选输出目录，点「开始处理」

### 压缩 PDF / Compress
- **图像质量**：1-100，越低体积越小但越模糊，建议 50-70
- **DPI**：36-600，越低体积越小，建议 72-150
- 选源文件后会显示原始大小，压缩完成显示压缩前后大小与压缩率

### 旋转 PDF / Rotate
1. 选源 PDF
2. 选角度 90/180/270
3. 页面范围留空=全部，或填 `1-3,5`
4. 选输出目录与文件名，点「开始处理」

### 裁剪 PDF / Crop
> 适用场景：扫描仪把 A4 扫成 A3、页面带黑边、只需保留局部内容等。
1. 选源 PDF，选「参考页」(默认第 1 页)，点「加载预览」
2. 在预览图上**按住鼠标拖拽框选**要保留的区域（蓝框内保留，框外暗化）
   - 框选时实时显示尺寸（pt / mm）
   - 可点「重置选区」重新框选
3. 选择「应用到」：
   - **所有相同尺寸页**：自动应用到与参考页尺寸相同的所有页（默认，对标 ilovepdf）
   - **自定义页码**：填入如 `1-3,5,7-9`，留空=全部页
4. 选输出目录，点「开始处理」

> 裁剪后页面尺寸真正变小（用 show_pdf_page 重建页面），不是仅设 CropBox。
>
> 注意：如果需要**逐页可视化裁剪**（而非一次性统一裁剪），请使用 **「尺寸检测」** 面板。

### 页面管理 / Organize
1. 点「加载 PDF」加载缩略图网格
2. **单选模式**：拖拽缩略图重排页面顺序；右键单页可旋转/删除/提取
3. **多选模式**：勾选顶部「多选模式」，点击缩略图选中（红框标记），
   可多选后点「批量删除选中(N)」一次性删除
4. 点「保存为新 PDF」输出

### 页面检测 / Detect (空白页/重复页)
1. 选源 PDF
2. 调整阈值：
   - 空白阈值(%)：非白像素占比低于此值判为空白页（默认 0%，可调高以更宽松）
   - 重复相似度(汉明距离)：越小越严格（默认 5，0-64）
3. 点「全部检测」或单独点「检测空白页」「检测重复页」
4. 结果表格中勾选要删除的页（可用「全选空白页」「全选重复页(每组留首页)」快捷勾选）
5. 选输出目录，点「删除已选页面」输出清理后的 PDF
6. 可点「导出报告」保存检测结果为 txt

### 提取页面 / Extract
1. 选源 PDF
2. 填要提取的页码，如 `1-3,5,7-9`
3. 填输出文件名，选输出目录，点「开始处理」

---

## 项目结构 / Project Structure

```
pdf_toolkit/
├── main.py            # 主窗口：标签页、菜单栏、状态栏、全局样式、日志窗口集成
├── panels.py          # 9 个功能面板 + 后台工作线程 PDFWorker
│                      # 含 CropPreviewWidget（可视化裁剪框）、
│                      # SizeDetectPanel（尺寸检测+摘要确认）、
│                      # SettingsDialog（全局设置三标签页）
├── pdf_core.py        # PDF 核心操作：
│                      # 合并/拆分/压缩/旋转/裁剪/页面管理/检测/删除/
│                      # detect_page_sizes(force_majority=...) + apply_size_operations
├── settings.py        # SettingsManager 单例：JSON 持久化设置（%APPDATA%\pdf_toolkit\）
├── log_window.py      # 全局日志管理器 + 独立日志窗口
├── i18n.py            # 中英双语翻译系统（新增裁剪尺寸模式/主尺寸/设置面板等）
├── requirements.txt   # 依赖清单
├── 启动.bat           # Windows 双击启动器（源码运行）
├── PDF_for_everyone.spec  # PyInstaller 规格文件
├── dist/
│   └── PDF_for_everyone/    # onedir 打包产物
│       ├── PDF_for_everyone.exe
│       └── _internal/       # 运行时依赖（整体文件夹一起移动）
└── README.md          # 本文档
```

---

## 打包成独立版 / Build Standalone Distribution

使用 `--onedir`（单文件夹结构），相比 `--onefile` 启动更快：

```powershell
cd c:\Users\KaiChen\Desktop\a\pdf_toolkit
python -m pip install pyinstaller
python -m PyInstaller --onedir --windowed --noconfirm --clean --name "PDF_for_everyone" `
    --exclude-module torch --exclude-module matplotlib --exclude-module sympy `
    --exclude-module numpy --exclude-module scipy --exclude-module pandas `
    --exclude-module IPython --exclude-module notebook --exclude-module tkinter `
    --exclude-module pytest --exclude-module django --exclude-module flask main.py
```

产物在 `dist\PDF_for_everyone\`，整体拷贝即可分发。
`--exclude-module` 排除不必要的大依赖以缩小体积（约 55 MB）。

---

## 技术要点 / Technical Notes

- **后台线程**：所有 PDF 操作在 `QThread` 中执行，UI 不卡顿，带进度条。
- **进度回调**：核心函数支持 `progress_cb(current, total, message)` 回调。
- **感知哈希**：重复页检测使用 aHash(8x8) + 汉明距离 + 并查集分组。
- **尺寸归一化**：`detect_page_sizes` 将短边放在前面统一分组，容差内视为同尺寸。
- **强制主尺寸**：`force_majority=(w,h)` 参数绕过"多数页判定"，直接把指定尺寸作主尺寸。
- **固定裁剪框**：`CropPreviewWidget.set_fixed_crop_size()` 锁定裁剪框宽高，只允许移动位置。
- **操作摘要确认**：`apply_size_operations` 一次性批量应用裁剪+缩放+删除，先弹窗让用户确认摘要。
- **设置持久化**：`SettingsManager` 单例读写 JSON 到 `%APPDATA%\pdf_toolkit\settings.json`，支持默认容差/主尺寸/裁剪模式/输出目录/语言。
- **统一错误处理**：`PDFError` 异常通过消息框提示并写入日志。
- **高 DPI**：启用 `AA_EnableHighDpiScaling`，高分屏下清晰。
- **离线**：所有处理本地完成，无任何网络请求。

---

## 常见问题 / FAQ

**Q: 报 `No module named 'PyQt5'`？**
A: 你用的 Python 没装依赖。请双击 `启动.bat`（自动找装好依赖的 Python），
   或对该 Python 执行 `pip install -r requirements.txt`。

**Q: 压缩后体积反而变大？**
A: 文字型 PDF 经栅格化压缩可能变大。压缩最适合扫描件（图像为主）。
   可调高图像质量或 DPI。

**Q: 重复页检测把不同页判为重复？**
A: 调小「重复相似度(汉明距离)」阈值（如改为 2-3），判定更严格。

**Q: 空白页没被检测到？**
A: 调高「空白阈值(%)」（如改为 1-2%），可识别更多近似空白页。

**Q: 检测到很多 A3 页，却把 A3 当成主尺寸（实际主尺寸应该是 A4）？**
A: 在「尺寸检测」面板，把「主尺寸模式」从「自动（多数页）」改为 **A4** 再检测。
   也可以到「全局设置 → 尺寸检测」把默认主尺寸设为 A4，以后自动用 A4 作主尺寸。

**Q: 裁剪对话框里，裁剪框大小拉不动？**
A: 你选了固定尺寸模式（A4/A3 等）。切换到「自由」尺寸即可自由调整大小。
   固定尺寸模式下裁剪框大小已锁定，只能移动位置，这是故意设计的。

**Q: 想整体移动 `PDF_for_everyone.exe`，启动报错找不到 dll？**
A: onedir 结构必须**整个文件夹一起移动**（exe 与 `_internal` 目录保持同级），不能只复制单个 exe。
