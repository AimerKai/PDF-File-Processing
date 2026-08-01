# -*- coding: utf-8 -*-
"""
pdf_core.py - PDF 核心操作模块
基于 PyMuPDF (fitz) 实现合并/拆分/压缩/旋转/提取/页面管理。

所有函数均支持可选的 progress_callback(current, total, message) 回调，
便于 UI 层显示进度。函数在失败时抛出 PDFError 异常。
"""

import os
import re
import io
from typing import List, Tuple, Optional, Callable, Iterable

try:
    import fitz  # PyMuPDF
except ImportError as e:
    raise ImportError("请安装 PyMuPDF: pip install PyMuPDF") from e

from PIL import Image


ProgressCB = Optional[Callable[[int, int, str], None]]


class PDFError(Exception):
    """PDF 处理异常"""
    pass


# ---------------------------------------------------------------------------
# 工具函数 / Utilities
# ---------------------------------------------------------------------------

def parse_page_ranges(spec: str, total_pages: int) -> List[int]:
    """
    解析页码范围字符串为 0-based 页码列表。
    支持格式: "1-3,5,7-9" (1-based 输入，0-based 输出)
    空字符串 -> 全部页面
    """
    spec = spec.strip()
    if not spec:
        return list(range(total_pages))

    pages: List[int] = []
    seen = set()
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
            if not m:
                raise PDFError(f"Invalid page range: {part}")
            start, end = int(m.group(1)), int(m.group(2))
            if start < 1 or end < 1 or start > end:
                raise PDFError(f"Invalid page range: {part}")
            if end > total_pages:
                raise PDFError(f"Page out of range: {end} (of {total_pages} pages)")
            for p in range(start, end + 1):
                idx = p - 1
                if idx not in seen:
                    seen.add(idx)
                    pages.append(idx)
        else:
            if not part.isdigit():
                raise PDFError(f"Invalid page number: {part}")
            p = int(part)
            if p < 1 or p > total_pages:
                raise PDFError(f"Page out of range: {p} (of {total_pages} pages)")
            idx = p - 1
            if idx not in seen:
                seen.add(idx)
                pages.append(idx)
    return pages


def file_size_str(path: str) -> str:
    """返回人类可读的文件大小字符串"""
    size = os.path.getsize(path)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ---------------------------------------------------------------------------
# 合并 / Merge
# ---------------------------------------------------------------------------

def merge_pdfs(file_paths: List[str], output_path: str,
               progress_cb: ProgressCB = None) -> int:
    """
    按列表顺序合并多个 PDF 为一个文件。
    返回合并的总页数。
    """
    if not file_paths:
        raise PDFError("No files to merge")
    if os.path.exists(output_path) and os.path.abspath(output_path) in \
            [os.path.abspath(f) for f in file_paths]:
        raise PDFError("Output cannot be the same as source")

    out_doc = fitz.open()
    total = len(file_paths)
    try:
        for i, path in enumerate(file_paths):
            if progress_cb:
                progress_cb(i, total, f"Merging: {os.path.basename(path)}")
            try:
                src = fitz.open(path)
            except Exception as e:
                raise PDFError(f"Failed to open PDF: {path} - {e}")
            out_doc.insert_pdf(src)
            src.close()
        if progress_cb:
            progress_cb(total, total, "Saving merged file")
        out_doc.save(output_path, garbage=4, deflate=True)
        return len(out_doc)
    finally:
        out_doc.close()


# ---------------------------------------------------------------------------
# 拆分 / Split
# ---------------------------------------------------------------------------

def split_pdf(src_path: str, output_dir: str, mode: str,
              ranges_spec: str = "", prefix: str = "page",
              progress_cb: ProgressCB = None) -> List[str]:
    """
    拆分 PDF。
    mode: 'each' - 每页一个文件; 'ranges' - 按范围拆分(每组一个文件)
    ranges_spec: mode='ranges' 时使用，例如 "1-3,5,7-9"
    返回生成的文件路径列表。
    """
    src = fitz.open(src_path)
    total_pages = len(src)
    if total_pages == 0:
        src.close()
        raise PDFError("Empty PDF")

    base = os.path.splitext(os.path.basename(src_path))[0]
    if not prefix:
        prefix = base

    out_files: List[str] = []
    try:
        if mode == "each":
            total = total_pages
            for i in range(total_pages):
                if progress_cb:
                    progress_cb(i, total, f"Splitting page {i+1}/{total}")
                new_doc = fitz.open()
                new_doc.insert_pdf(src, from_page=i, to_page=i)
                out_path = os.path.join(output_dir, f"{prefix}_{i+1:03d}.pdf")
                new_doc.save(out_path, garbage=4, deflate=True)
                new_doc.close()
                out_files.append(out_path)
        elif mode == "ranges":
            groups = [g.strip() for g in ranges_spec.split(",") if g.strip()]
            total = len(groups)
            for gi, group in enumerate(groups):
                if progress_cb:
                    progress_cb(gi, total, f"Splitting range {gi+1}/{total}")
                pages = parse_page_ranges(group, total_pages)
                new_doc = fitz.open()
                # insert_pdf 接受连续范围，所以逐页插入更安全
                for p in pages:
                    new_doc.insert_pdf(src, from_page=p, to_page=p)
                safe_group = re.sub(r"[^\w\-]", "_", group)
                out_path = os.path.join(output_dir, f"{prefix}_{safe_group}.pdf")
                new_doc.save(out_path, garbage=4, deflate=True)
                new_doc.close()
                out_files.append(out_path)
        else:
            raise PDFError(f"Unknown split mode: {mode}")
        if progress_cb:
            progress_cb(total, total, "Split complete")
        return out_files
    finally:
        src.close()


# ---------------------------------------------------------------------------
# 压缩 / Compress
# ---------------------------------------------------------------------------

def compress_pdf(src_path: str, output_path: str,
                 quality: int = 72, dpi: int = 96,
                 progress_cb: ProgressCB = None) -> Tuple[int, int]:
    """
    压缩 PDF：对每页重新栅格化为图像再合成新 PDF。
    quality: JPEG 质量 (1-100)
    dpi: 渲染 DPI
    返回 (原始大小, 压缩后大小) 字节数。
    """
    if quality < 1 or quality > 100:
        raise PDFError("Quality must be 1-100")
    if dpi < 36 or dpi > 600:
        raise PDFError("DPI must be 36-600")

    src = fitz.open(src_path)
    total_pages = len(src)
    if total_pages == 0:
        src.close()
        raise PDFError("Empty PDF")

    orig_size = os.path.getsize(src_path)
    new_doc = fitz.open()
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    try:
        for i in range(total_pages):
            if progress_cb:
                progress_cb(i, total_pages, f"Compressing page {i+1}/{total_pages}")
            page = src[i]
            # 渲染页面为像素图 / Render page to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            # 转为 JPEG 字节流 / Convert to JPEG bytes
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            img_bytes = buf.getvalue()

            # 新建相同尺寸页面，插入图像 / New page with same size, insert image
            rect = page.rect
            new_page = new_doc.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=img_bytes)

        if progress_cb:
            progress_cb(total_pages, total_pages, "Saving compressed file")
        new_doc.save(output_path, garbage=4, deflate=True)
        new_size = os.path.getsize(output_path)
        return (orig_size, new_size)
    except Exception as e:
        raise PDFError(f"Compression failed: {e}")
    finally:
        new_doc.close()
        src.close()


# ---------------------------------------------------------------------------
# 旋转 / Rotate
# ---------------------------------------------------------------------------

def rotate_pdf(src_path: str, output_path: str, angle: int,
               pages_spec: str = "", progress_cb: ProgressCB = None) -> int:
    """
    旋转指定页面。
    angle: 90, 180, 270
    pages_spec: 留空表示全部页面，否则 "1-3,5"
    返回旋转的页数。
    """
    if angle not in (90, 180, 270):
        raise PDFError("Angle must be 90, 180, or 270")

    doc = fitz.open(src_path)
    total_pages = len(doc)
    if total_pages == 0:
        doc.close()
        raise PDFError("Empty PDF")

    try:
        pages = parse_page_ranges(pages_spec, total_pages)
        total = len(pages)
        for i, p in enumerate(pages):
            if progress_cb:
                progress_cb(i, total, f"Rotating page {p+1}/{total_pages}")
            page = doc[p]
            # PyMuPDF 的 set_rotation 是绝对设置 / set_rotation is absolute
            # 累加旋转角度 / Accumulate rotation
            current = page.rotation
            new_rot = (current + angle) % 360
            page.set_rotation(new_rot)

        if progress_cb:
            progress_cb(total, total, "Saving rotated file")
        doc.save(output_path, garbage=4, deflate=True)
        return total
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# 提取 / Extract
# ---------------------------------------------------------------------------

def extract_pages(src_path: str, output_path: str, pages_spec: str,
                  progress_cb: ProgressCB = None) -> int:
    """
    提取指定页面为新 PDF。
    pages_spec: "1-3,5,7-9" 或留空(全部)
    返回提取的页数。
    """
    src = fitz.open(src_path)
    total_pages = len(src)
    if total_pages == 0:
        src.close()
        raise PDFError("Empty PDF")

    try:
        pages = parse_page_ranges(pages_spec, total_pages)
        if not pages:
            raise PDFError("No pages selected")

        total = len(pages)
        new_doc = fitz.open()
        for i, p in enumerate(pages):
            if progress_cb:
                progress_cb(i, total, f"Extracting page {p+1}")
            new_doc.insert_pdf(src, from_page=p, to_page=p)

        if progress_cb:
            progress_cb(total, total, "Saving extracted file")
        new_doc.save(output_path, garbage=4, deflate=True)
        new_doc.close()
        return total
    finally:
        src.close()


# ---------------------------------------------------------------------------
# 页面管理 / Organize
# ---------------------------------------------------------------------------

def generate_thumbnail(src_path: str, page_idx: int,
                       max_size: int = 160) -> bytes:
    """
    生成指定页的 PNG 缩略图字节流，用于 UI 显示。
    """
    doc = fitz.open(src_path)
    try:
        page = doc[page_idx]
        # 按比例缩放到 max_size / Scale proportionally to max_size
        rect = page.rect
        scale = min(max_size / rect.width, max_size / rect.height)
        if scale > 1.0:
            scale = 1.0
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def reorganize_pdf(src_path: str, output_path: str,
                   page_order: List[int],
                   rotations: dict = None,
                   progress_cb: ProgressCB = None) -> int:
    """
    按指定顺序重建 PDF。
    page_order: 新顺序的 0-based 页码列表 (来自原 PDF)
    rotations: 可选 {page_idx_in_new_doc: angle} 旋转角度
    返回新 PDF 的页数。
    """
    rotations = rotations or {}
    src = fitz.open(src_path)
    new_doc = fitz.open()
    try:
        if len(src) == 0:
            raise PDFError("Empty PDF")

        total = len(page_order)
        for i, p in enumerate(page_order):
            if progress_cb:
                progress_cb(i, total, f"Building page {i+1}/{total}")
            new_doc.insert_pdf(src, from_page=p, to_page=p)

        # 应用旋转 / Apply rotations
        for new_idx, angle in rotations.items():
            if 0 <= new_idx < len(new_doc):
                new_doc[new_idx].set_rotation(angle % 360)

        if progress_cb:
            progress_cb(total, total, "Saving reorganized file")
        new_doc.save(output_path, garbage=4, deflate=True)
        return total
    finally:
        new_doc.close()
        src.close()


def get_pdf_info(src_path: str) -> dict:
    """返回 PDF 基本信息: pages, metadata, page_size"""
    doc = fitz.open(src_path)
    try:
        if len(doc) > 0:
            rect = doc[0].rect
            page_size = (rect.width, rect.height)
        else:
            page_size = (0, 0)
        return {
            "pages": len(doc),
            "metadata": doc.metadata or {},
            "page_size": page_size,
        }
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# 页面检测 / Page Detection (空白页 + 重复页)
# ---------------------------------------------------------------------------

def _render_page_gray(doc, page_idx: int, scale: float = 0.5) -> Image.Image:
    """渲染指定页为灰度 PIL 图像 (低分辨率用于检测)。"""
    page = doc[page_idx]
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img.convert("L")


def _ahash(img: Image.Image, hash_size: int = 8) -> int:
    """
    计算图像的 average hash (aHash)，返回整数。
    缩放到 hash_size x hash_size，按均值二值化。
    """
    img = img.resize((hash_size, hash_size), Image.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits


def _hamming(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def detect_blank_pages(src_path: str, threshold: float = 99.0,
                       progress_cb: ProgressCB = None) -> List[int]:
    """
    检测空白页 (含近似空白)。
    判定逻辑 (满足任一即视为空白页):
      1) 白度: 白色像素(灰度>=250)占比 >= threshold%   —— 适合纯白页
      2) 均匀浅色: 像素标准差 < 5                       —— 适合扫描件的均匀灰噪点空白页
    threshold: 白度阈值百分比 (0-100)，默认 99。
               调低可更宽松地判定(捕获更多页)。
    返回空白页的 0-based 索引列表。
    """
    doc = fitz.open(src_path)
    total = len(doc)
    blanks: List[int] = []
    try:
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Checking page {i+1}/{total}")
            gray = _render_page_gray(doc, i, scale=0.5)
            pixels = list(gray.getdata())
            if not pixels:
                blanks.append(i)
                continue
            n = len(pixels)
            white = sum(1 for p in pixels if p >= 250)
            white_ratio = white / n * 100
            mean = sum(pixels) / n
            var = sum((p - mean) ** 2 for p in pixels) / n
            std = var ** 0.5
            # 纯白为主 或 均匀浅色(扫描空白)
            if white_ratio >= threshold or std < 5:
                blanks.append(i)
        if progress_cb:
            progress_cb(total, total, "Blank detection done")
        return blanks
    finally:
        doc.close()


def page_stats(src_path: str, page_idx: int) -> dict:
    """
    返回单页统计信息，用于预览面板展示。
    {white_ratio, mean, std, is_blank}
    """
    doc = fitz.open(src_path)
    try:
        gray = _render_page_gray(doc, page_idx, scale=0.5)
        pixels = list(gray.getdata())
        n = len(pixels)
        if n == 0:
            return {"white_ratio": 0.0, "mean": 0.0, "std": 0.0, "is_blank": True}
        white = sum(1 for p in pixels if p >= 250)
        mean = sum(pixels) / n
        var = sum((p - mean) ** 2 for p in pixels) / n
        std = var ** 0.5
        return {
            "white_ratio": white / n * 100,
            "mean": mean,
            "std": std,
            "is_blank": (white / n * 100) >= 99.0 or std < 5,
        }
    finally:
        doc.close()


def render_page_image(src_path: str, page_idx: int,
                      max_size: int = 700) -> bytes:
    """
    渲染指定页为 PNG 字节流 (用于预览，比缩略图更大更清晰)。
    允许适度放大 (最多 2x) 以便小页面也能看清。
    """
    doc = fitz.open(src_path)
    try:
        page = doc[page_idx]
        rect = page.rect
        scale = min(max_size / rect.width, max_size / rect.height)
        if scale > 2.0:
            scale = 2.0
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def detect_duplicate_pages(src_path: str, hamming_threshold: int = 5,
                           progress_cb: ProgressCB = None
                           ) -> List[List[int]]:
    """
    检测重复页 (视觉相似)。
    使用 aHash + Hamming 距离判定，距离 <= hamming_threshold 视为重复。
    返回重复页组列表，每组为 0-based 页码列表 (如 [[0,5],[2,7,9]])。
    只返回 >=2 页的组。
    """
    doc = fitz.open(src_path)
    total = len(doc)
    try:
        hashes: List[int] = []
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Hashing page {i+1}/{total}")
            gray = _render_page_gray(doc, i, scale=1.0)
            hashes.append(_ahash(gray))

        # 并查集分组 / Union-Find grouping
        parent = list(range(total))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(total):
            for j in range(i + 1, total):
                if _hamming(hashes[i], hashes[j]) <= hamming_threshold:
                    union(i, j)

        groups: dict = {}
        for i in range(total):
            root = find(i)
            groups.setdefault(root, []).append(i)

        # 只保留 >=2 页的组，按首页排序 / Keep groups with >=2 pages
        result = [sorted(g) for g in groups.values() if len(g) >= 2]
        result.sort(key=lambda g: g[0])
        if progress_cb:
            progress_cb(total, total, "Duplicate detection done")
        return result
    finally:
        doc.close()


def delete_pages(src_path: str, output_path: str,
                 pages_to_delete: List[int],
                 progress_cb: ProgressCB = None) -> int:
    """
    删除指定页面，输出新 PDF。
    pages_to_delete: 要删除的 0-based 页码列表
    返回新 PDF 的页数。
    """
    del_set = set(pages_to_delete)
    src = fitz.open(src_path)
    new_doc = fitz.open()
    try:
        total_pages = len(src)
        if total_pages == 0:
            raise PDFError("Empty PDF")
        keep = [p for p in range(total_pages) if p not in del_set]
        total = len(keep)
        for i, p in enumerate(keep):
            if progress_cb:
                progress_cb(i, total, f"Keeping page {p+1}")
            new_doc.insert_pdf(src, from_page=p, to_page=p)
        if progress_cb:
            progress_cb(total, total, "Saving")
        new_doc.save(output_path, garbage=4, deflate=True)
        return total
    finally:
        new_doc.close()
        src.close()


# ---------------------------------------------------------------------------
# 裁剪 / Crop
# ---------------------------------------------------------------------------

def get_page_size(src_path: str, page_idx: int) -> tuple:
    """返回指定页尺寸 (width, height)，单位 PDF 点。"""
    doc = fitz.open(src_path)
    try:
        rect = doc[page_idx].rect
        return (rect.width, rect.height)
    finally:
        doc.close()


def find_same_size_pages(src_path: str, ref_page_idx: int,
                         tolerance: float = 1.0) -> List[int]:
    """返回与参考页尺寸相同(±tolerance 点)的所有页 0-based 索引。"""
    doc = fitz.open(src_path)
    try:
        ref = doc[ref_page_idx].rect
        rw, rh = ref.width, ref.height
        result = []
        for i in range(len(doc)):
            r = doc[i].rect
            if abs(r.width - rw) <= tolerance and abs(r.height - rh) <= tolerance:
                result.append(i)
        return result
    finally:
        doc.close()


def crop_pages(src_path: str, output_path: str,
               page_indices: List[int], crop_rect: tuple,
               progress_cb: ProgressCB = None) -> int:
    """
    裁剪指定页面。用 show_pdf_page 创建新页面，真正改变页面尺寸。
    crop_rect: (x0, y0, x1, y1) PDF 点，源页面坐标
    page_indices: 要裁剪的 0-based 页码列表；其余页原样保留。
    返回新 PDF 总页数。
    """
    x0, y0, x1, y1 = crop_rect
    # 确保坐标有序 / Normalize
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    cw, ch = x1 - x0, y1 - y0
    if cw <= 1 or ch <= 1:
        raise PDFError("Crop region too small")

    crop_set = set(page_indices)
    clip = fitz.Rect(x0, y0, x1, y1)
    src = fitz.open(src_path)
    new_doc = fitz.open()
    try:
        total = len(src)
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Page {i+1}/{total}")
            if i in crop_set:
                new_page = new_doc.new_page(width=cw, height=ch)
                new_page.show_pdf_page(new_page.rect, src, i, clip=clip)
            else:
                new_doc.insert_pdf(src, from_page=i, to_page=i)
        if progress_cb:
            progress_cb(total, total, "Saving")
        new_doc.save(output_path, garbage=4, deflate=True)
        return total
    finally:
        new_doc.close()
        src.close()


# ---------------------------------------------------------------------------
# 页面尺寸检测 / Page Size Detection
# ---------------------------------------------------------------------------

# 标准纸张尺寸 (短边, 长边)，单位 PDF 点 (1mm = 72/25.4 pt)
_PAPER_SIZES_PT = [
    ("A0",  2384.0, 3370.0),
    ("A1",  1684.0, 2384.0),
    ("A2",  1191.0, 1684.0),
    ("A3",   842.0, 1191.0),
    ("A4",   595.0,  842.0),
    ("A5",   420.0,  595.0),
    ("A6",   297.0,  420.0),
    ("Letter", 612.0,  792.0),
    ("Legal",  612.0, 1008.0),
]


def classify_page_size(width_pt: float, height_pt: float,
                       tolerance_pt: float = 5.0) -> str:
    """
    将页面尺寸归类为标准纸张名称。
    自动处理横竖方向 (比较短边/长边)。
    无法匹配时返回 "Custom"。
    """
    w, h = min(width_pt, height_pt), max(width_pt, height_pt)
    for name, sw, sh in _PAPER_SIZES_PT:
        if abs(w - sw) <= tolerance_pt and abs(h - sh) <= tolerance_pt:
            return name
    return "Custom"


def detect_page_sizes(src_path: str, tolerance: float = 2.0,
                      progress_cb: ProgressCB = None,
                      force_majority: tuple = None) -> dict:
    """
    扫描所有页面尺寸，按尺寸分组，识别主尺寸与异常尺寸页。
    tolerance:      尺寸分组容差 (PDF 点)
    force_majority: (w, h) PDF 点；提供时用此尺寸作为主尺寸
                    (自动匹配横竖方向，按短边/长边比较)，
                    否则仍按「页数最多的尺寸组」作为主尺寸。
    返回:
      {
        'pages': [(page_idx, width, height, paper_name, is_anomaly), ...],
        'groups': [
          {'size_key': 'A4 595x842', 'width': 595, 'height': 842,
           'paper': 'A4', 'pages': [0,1,2,...], 'is_majority': True},
          ...
        ],
        'majority_size': (width, height) or None,
        'anomaly_pages': [page_idx, ...],
        'total_pages': N,
        'majority_forced': bool,
      }
    """
    doc = fitz.open(src_path)
    total = len(doc)
    forced = force_majority is not None
    try:
        # 收集每页尺寸 / Collect per-page sizes
        page_sizes: List[Tuple[float, float]] = []
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Measuring page {i+1}/{total}")
            rect = doc[i].rect
            page_sizes.append((rect.width, rect.height))

        # 按尺寸分组 (容差内视为同组) / Group by size within tolerance
        groups: List[dict] = []
        assigned = [False] * total

        for i in range(total):
            if assigned[i]:
                continue
            w, h = page_sizes[i]
            paper = classify_page_size(w, h)
            nw, nh = min(w, h), max(w, h)
            members = [i]
            assigned[i] = True
            for j in range(i + 1, total):
                if assigned[j]:
                    continue
                w2, h2 = page_sizes[j]
                nw2, nh2 = min(w2, h2), max(w2, h2)
                if abs(nw - nw2) <= tolerance and abs(nh - nh2) <= tolerance:
                    members.append(j)
                    assigned[j] = True
            size_key = f"{paper} {w:.0f}x{h:.0f}"
            groups.append({
                'size_key': size_key,
                'width': w,
                'height': h,
                'paper': paper,
                'pages': members,
                'is_majority': False,
            })

        # 确定主尺寸组 / Find majority group
        maj_size = None
        if groups:
            if forced:
                # 强制指定: 匹配方向一致的尺寸组
                fw, fh = force_majority
                fnw, fnh = min(fw, fh), max(fw, fh)
                match = None
                for g in groups:
                    gw, gh = min(g['width'], g['height']), max(g['width'], g['height'])
                    if abs(gw - fnw) <= tolerance and abs(gh - fnh) <= tolerance:
                        match = g
                        break
                if match:
                    match['is_majority'] = True
                    # 保持目标原方向 (w, h) 作为 majority_size
                    maj_size = (fw, fh)
                else:
                    # PDF 中没有该尺寸组，但把强制尺寸作为目标
                    # 此时把第一个组作为 majority 展示（仅用于 UI）
                    groups[0]['is_majority'] = True
                    maj_size = (fw, fh)
            else:
                majority = max(groups, key=lambda g: len(g['pages']))
                majority['is_majority'] = True
                maj_size = (majority['width'], majority['height'])

        # 标记异常页 / Mark anomaly pages
        anomaly_pages = []
        pages_info = []
        # 强制模式: anomaly = 尺寸不匹配 (以 maj_size 为基准)
        # 自动模式: anomaly = 非 majority 组
        if forced and maj_size:
            mw, mh = min(maj_size), max(maj_size)
            for g in groups:
                gw, gh = min(g['width'], g['height']), max(g['width'], g['height'])
                is_anom = not (abs(gw - mw) <= tolerance and abs(gh - mh) <= tolerance)
                for p in g['pages']:
                    pages_info.append(
                        (p, g['width'], g['height'], g['paper'], is_anom))
                    if is_anom:
                        anomaly_pages.append(p)
        else:
            for g in groups:
                is_anom = not g['is_majority']
                for p in g['pages']:
                    pages_info.append(
                        (p, g['width'], g['height'], g['paper'], is_anom))
                    if is_anom:
                        anomaly_pages.append(p)

        if progress_cb:
            progress_cb(total, total, "Size detection done")

        return {
            'pages': pages_info,
            'groups': groups,
            'majority_size': maj_size,
            'anomaly_pages': anomaly_pages,
            'total_pages': total,
            'majority_forced': forced,
        }
    finally:
        doc.close()


def resize_pages(src_path: str, output_path: str,
                 page_indices: List[int], target_size: tuple,
                 progress_cb: ProgressCB = None) -> int:
    """
    将指定页面缩放到目标尺寸 (保持内容填满，可能改变宽高比)。
    target_size: (width, height) PDF 点
    其余页原样保留。返回新 PDF 总页数。
    """
    tw, th = target_size
    if tw <= 0 or th <= 0:
        raise PDFError("Invalid target size")
    resize_set = set(page_indices)
    src = fitz.open(src_path)
    new_doc = fitz.open()
    try:
        total = len(src)
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Page {i+1}/{total}")
            if i in resize_set:
                new_page = new_doc.new_page(width=tw, height=th)
                new_page.show_pdf_page(new_page.rect, src, i)
            else:
                new_doc.insert_pdf(src, from_page=i, to_page=i)
        if progress_cb:
            progress_cb(total, total, "Saving")
        new_doc.save(output_path, garbage=4, deflate=True)
        return total
    finally:
        new_doc.close()
        src.close()


def crop_pages_individual(src_path: str, output_path: str,
                          crop_rects: dict,
                          progress_cb: ProgressCB = None) -> int:
    """
    对不同页面应用不同的裁剪区域。
    crop_rects: {page_idx: (x0, y0, x1, y1)} PDF 点坐标
    未在 dict 中的页面原样保留。返回新 PDF 总页数。
    """
    src = fitz.open(src_path)
    new_doc = fitz.open()
    try:
        total = len(src)
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Page {i+1}/{total}")
            if i in crop_rects:
                x0, y0, x1, y1 = crop_rects[i]
                if x0 > x1:
                    x0, x1 = x1, x0
                if y0 > y1:
                    y0, y1 = y1, y0
                cw, ch = x1 - x0, y1 - y0
                if cw > 1 and ch > 1:
                    clip = fitz.Rect(x0, y0, x1, y1)
                    new_page = new_doc.new_page(width=cw, height=ch)
                    new_page.show_pdf_page(new_page.rect, src, i, clip=clip)
                else:
                    new_doc.insert_pdf(src, from_page=i, to_page=i)
            else:
                new_doc.insert_pdf(src, from_page=i, to_page=i)
        if progress_cb:
            progress_cb(total, total, "Saving")
        new_doc.save(output_path, garbage=4, deflate=True)
        return total
    finally:
        new_doc.close()
        src.close()


def apply_size_operations(src_path: str, output_path: str,
                          crop_rects: dict, delete_pages: set,
                          scale_pages: set, target_size: tuple,
                          progress_cb: ProgressCB = None) -> int:
    """
    一次性应用裁剪、缩放、删除操作，输出单个 PDF。
    crop_rects: {page_idx: (x0, y0, x1, y1)} 裁剪区域
    delete_pages: set of page_idx 要删除的页
    scale_pages: set of page_idx 要缩放的页
    target_size: (w, h) 缩放目标尺寸 (PDF 点)
    优先级: 删除 > 裁剪 > 缩放
    返回输出 PDF 总页数。
    """
    delete_set = set(delete_pages)
    scale_set = set(scale_pages) - delete_set
    crop_dict = {k: v for k, v in crop_rects.items() if k not in delete_set}

    src = fitz.open(src_path)
    new_doc = fitz.open()
    try:
        total = len(src)
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Page {i+1}/{total}")
            if i in delete_set:
                continue  # 跳过删除页 / Skip deleted
            elif i in crop_dict:
                x0, y0, x1, y1 = crop_dict[i]
                if x0 > x1:
                    x0, x1 = x1, x0
                if y0 > y1:
                    y0, y1 = y1, y0
                cw, ch = x1 - x0, y1 - y0
                if cw > 1 and ch > 1:
                    clip = fitz.Rect(x0, y0, x1, y1)
                    new_page = new_doc.new_page(width=cw, height=ch)
                    new_page.show_pdf_page(new_page.rect, src, i, clip=clip)
                else:
                    new_doc.insert_pdf(src, from_page=i, to_page=i)
            elif i in scale_set and target_size:
                tw, th = target_size
                new_page = new_doc.new_page(width=tw, height=th)
                new_page.show_pdf_page(new_page.rect, src, i)
            else:
                new_doc.insert_pdf(src, from_page=i, to_page=i)
        if progress_cb:
            progress_cb(total, total, "Saving")
        new_doc.save(output_path, garbage=4, deflate=True)
        return len(new_doc)
    finally:
        new_doc.close()
        src.close()


def crop_to_target_size(src_path: str, output_path: str,
                        page_indices: List[int], target_size: tuple,
                        progress_cb: ProgressCB = None) -> int:
    """
    将指定页面居中裁剪到目标尺寸 (仅裁剪，不缩放)。
    若页面小于目标尺寸则跳过 (保持原样)。
    target_size: (width, height) PDF 点
    返回新 PDF 总页数。
    """
    tw, th = target_size
    if tw <= 0 or th <= 0:
        raise PDFError("Invalid target size")
    crop_set = set(page_indices)
    src = fitz.open(src_path)
    new_doc = fitz.open()
    try:
        total = len(src)
        for i in range(total):
            if progress_cb:
                progress_cb(i, total, f"Page {i+1}/{total}")
            if i in crop_set:
                page = src[i]
                pw, ph = page.rect.width, page.rect.height
                # 仅当页面大于目标时裁剪 / Only crop if page is larger
                if pw >= tw and ph >= th:
                    cx, cy = pw / 2, ph / 2
                    clip = fitz.Rect(cx - tw / 2, cy - th / 2,
                                     cx + tw / 2, cy + th / 2)
                    new_page = new_doc.new_page(width=tw, height=th)
                    new_page.show_pdf_page(new_page.rect, src, i, clip=clip)
                elif pw >= th and ph >= tw:
                    # 横向页面: 裁剪为竖向目标 / Landscape page
                    cx, cy = pw / 2, ph / 2
                    clip = fitz.Rect(cx - tw / 2, cy - th / 2,
                                     cx + tw / 2, cy + th / 2)
                    new_page = new_doc.new_page(width=tw, height=th)
                    new_page.show_pdf_page(new_page.rect, src, i, clip=clip)
                else:
                    # 页面太小，直接保留 / Page too small, keep as-is
                    new_doc.insert_pdf(src, from_page=i, to_page=i)
            else:
                new_doc.insert_pdf(src, from_page=i, to_page=i)
        if progress_cb:
            progress_cb(total, total, "Saving")
        new_doc.save(output_path, garbage=4, deflate=True)
        return total
    finally:
        new_doc.close()
        src.close()
