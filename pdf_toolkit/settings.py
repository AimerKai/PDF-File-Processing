"""
全局设置管理: JSON 持久化, 保存到用户 AppData 目录下的 pdf_toolkit 子目录。
支持:
  - 检测容差 (pt)
  - 检测主尺寸模式:  auto / A4 / A3 / A2 / A5 / Letter / Custom
  - 检测主尺寸自定义宽高 (pt)
  - 裁剪默认模式: free / A4 / A3 / A5 / Letter / Custom
  - 裁剪自定义宽高 (pt)
  - 默认输出目录
  - 默认语言: zh_CN / en_US
"""

import json
import os
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 默认值 / Defaults
# ---------------------------------------------------------------------------

DEFAULTS: Dict[str, Any] = {
    # 尺寸检测 / Size detection
    "detect_tolerance_pt": 2.0,
    "detect_majority_mode": "auto",          # auto / A4 / A3 / A2 / A5 / Letter / Custom
    "detect_majority_custom_w": 595.0,       # A4 pt 当模式为 Custom 时
    "detect_majority_custom_h": 842.0,

    # 裁剪框模式 / Crop box mode
    "crop_default_mode": "free",             # free / A4 / A3 / A5 / Letter / Custom
    "crop_custom_w": 595.0,
    "crop_custom_h": 842.0,

    # 其他 / Others
    "default_output_dir": "",
    "default_language": "zh_CN",             # zh_CN / en_US
}

# 标准纸张尺寸 (w, h) 短边×长边 PDF 点 / Standard paper sizes (short edge x long edge in pt)
STANDARD_PAPER_PT: Dict[str, tuple] = {
    "A2":     (1191.0, 1684.0),
    "A3":      (842.0, 1191.0),
    "A4":      (595.0,  842.0),
    "A5":      (420.0,  595.0),
    "A6":      (297.0,  420.0),
    "Letter":  (612.0,  792.0),
    "Legal":   (612.0, 1008.0),
}


def _settings_path() -> str:
    """返回设置文件路径: %APPDATA%/pdf_toolkit/settings.json"""
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(appdata, "pdf_toolkit")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


class SettingsManager:
    """单例式设置管理器，加载/保存到 JSON。"""

    _instance = None

    def __init__(self):
        self._path = _settings_path()
        self._data: Dict[str, Any] = dict(DEFAULTS)
        self.load()

    @classmethod
    def instance(cls) -> "SettingsManager":
        if cls._instance is None:
            cls._instance = SettingsManager()
        return cls._instance

    # ------------------------------------------------------------------
    # 基础存取 / Basic access
    # ------------------------------------------------------------------
    def get(self, key: str, default=None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def all(self) -> Dict[str, Any]:
        return dict(self._data)

    def update(self, data: Dict[str, Any]) -> None:
        self._data.update(data)

    # ------------------------------------------------------------------
    # 持久化 / Persistence
    # ------------------------------------------------------------------
    def load(self) -> bool:
        if not os.path.isfile(self._path):
            return False
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged = dict(DEFAULTS)
                merged.update(data)
                self._data = merged
                return True
        except Exception:
            pass
        return False

    def save(self) -> bool:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 便利函数 / Convenience helpers
    # ------------------------------------------------------------------
    def get_detect_majority_size(self) -> tuple:
        """
        返回用户设定的强制主尺寸 (w, h) PDF 点，
        若模式为 auto 则返回 None。
        """
        mode = self.get("detect_majority_mode", "auto")
        if mode == "auto":
            return None
        if mode in STANDARD_PAPER_PT:
            return STANDARD_PAPER_PT[mode]
        if mode == "Custom":
            return (float(self.get("detect_majority_custom_w", 595)),
                    float(self.get("detect_majority_custom_h", 842)))
        return None

    def get_crop_fixed_size(self) -> tuple:
        """
        返回裁剪固定尺寸 (w, h) PDF 点；自由模式返回 None。
        """
        mode = self.get("crop_default_mode", "free")
        if mode == "free":
            return None
        if mode in STANDARD_PAPER_PT:
            return STANDARD_PAPER_PT[mode]
        if mode == "Custom":
            return (float(self.get("crop_custom_w", 595)),
                    float(self.get("crop_custom_h", 842)))
        return None


# 全局快捷访问 / Global convenience shortcut
def gset(key: str, default=None):
    return SettingsManager.instance().get(key, default)


def gset_set(key: str, value: Any):
    SettingsManager.instance().set(key, value)


def gset_save():
    return SettingsManager.instance().save()
