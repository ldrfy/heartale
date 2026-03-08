"""阅读页设置相关逻辑。"""

from gi.repository import Adw, Gtk  # type: ignore

from ..entity import LibraryDB
from ..utils.debug import get_logger

READER_CONFIG_KEY = "reader_page"
READER_DEFAULT_CONFIG = {
    "font_size": 14,
    "line_space": 8,
    "paragraph_space": 24,
}


class ReaderSettingsMixin:
    """封装阅读页设置的加载、应用与保存逻辑。"""

    def load_reader_settings(self) -> None:
        """加载并应用阅读设置。"""
        self._load_reader_settings()

    def apply_default_reader_settings(self) -> None:
        """恢复默认阅读设置。"""
        self._apply_reader_settings(READER_DEFAULT_CONFIG, persist=True)

    def handle_fontsize_changed(self, widget, persist: bool = True) -> None:
        """调整字体大小。

        Args:
            widget (Adw.SpinRow | int | float): 控件对象或目标值
            persist (bool, optional): 是否持久化保存. Defaults to True.
        """
        value = self._extract_spin_value(widget, self.ga_f)
        self.ptc.set_font_size_pt(value)
        if persist and not self._suspend_reader_config_save:
            self._save_reader_setting("font_size", value)

    def handle_paragraph_space_changed(self, widget, persist: bool = True) -> None:
        """调整段间距。

        Args:
            widget (Adw.SpinRow | int | float): 控件对象或目标值
            persist (bool, optional): 是否持久化保存. Defaults to True.
        """
        value = self._extract_spin_value(widget, self.ga_p)
        self.ptc.set_paragraph_spacing(0, value)
        if persist and not self._suspend_reader_config_save:
            self._save_reader_setting("paragraph_space", value)

    def handle_line_space_changed(self, widget, persist: bool = True) -> None:
        """调整行间距。

        Args:
            widget (Adw.SpinRow | int | float): 控件对象或目标值
            persist (bool, optional): 是否持久化保存. Defaults to True.
        """
        value = self._extract_spin_value(widget, self.ga_l)
        self.ptc.set_line_spacing(value)
        if persist and not self._suspend_reader_config_save:
            self._save_reader_setting("line_space", value)

    def handle_set_default(self, *_args) -> None:
        """恢复默认阅读设置。"""
        self.apply_default_reader_settings()

    def _extract_spin_value(self, widget, adjustment: Gtk.Adjustment) -> int:
        """从设置控件或原始值中提取合法整数值。

        Args:
            widget (Adw.SpinRow | int | float): 控件对象或目标值
            adjustment (Gtk.Adjustment): 对应的取值范围对象

        Returns:
            int: 规范化后的设置值
        """
        raw_value = widget.get_value() if isinstance(widget, Adw.SpinRow) else widget
        return self._clamp_setting(raw_value, adjustment)

    def _clamp_setting(self, value, adjustment: Gtk.Adjustment) -> int:
        """将设置值限制到允许范围内。

        Args:
            value (object): 原始设置值
            adjustment (Gtk.Adjustment): 对应的取值范围对象

        Returns:
            int: 限制后的设置值
        """
        try:
            current = int(round(float(value)))
        except (TypeError, ValueError):
            current = int(round(float(adjustment.get_value())))
        lower = int(round(adjustment.get_lower()))
        upper = int(round(adjustment.get_upper()))
        return max(lower, min(upper, current))

    def _normalize_reader_settings(self, raw_config) -> dict:
        """规范化阅读设置字典。

        Args:
            raw_config (object): 原始设置对象

        Returns:
            dict: 规范化后的设置字典
        """
        config = dict(READER_DEFAULT_CONFIG)
        if isinstance(raw_config, dict):
            config.update(raw_config)
        config["font_size"] = self._clamp_setting(
            config["font_size"], self.ga_f)
        config["line_space"] = self._clamp_setting(
            config["line_space"], self.ga_l)
        config["paragraph_space"] = self._clamp_setting(
            config["paragraph_space"],
            self.ga_p,
        )
        return config

    def _load_reader_settings(self) -> None:
        """从数据库加载阅读设置。"""
        config = dict(READER_DEFAULT_CONFIG)
        try:
            db = LibraryDB()
            config = self._normalize_reader_settings(
                db.get_config(READER_CONFIG_KEY, READER_DEFAULT_CONFIG)
            )
            db.close()
        except Exception as exc:  # pylint: disable=broad-except
            get_logger().warning("Failed to load reader settings: %s", exc)
            config = self._normalize_reader_settings(READER_DEFAULT_CONFIG)
        self._apply_reader_settings(config, persist=False)

    def _apply_reader_settings(self, config: dict, persist: bool) -> None:
        """应用阅读设置到界面控件。

        Args:
            config (dict): 待读取的设置字典
            persist (bool): 是否持久化保存
        """
        normalized = self._normalize_reader_settings(config)
        self._suspend_reader_config_save = True
        try:
            self.ga_f.set_value(normalized["font_size"])
            self.ga_l.set_value(normalized["line_space"])
            self.ga_p.set_value(normalized["paragraph_space"])
            self.handle_fontsize_changed(
                normalized["font_size"], persist=False)
            self.handle_line_space_changed(
                normalized["line_space"], persist=False)
            self.handle_paragraph_space_changed(
                normalized["paragraph_space"],
                persist=False,
            )
        finally:
            self._suspend_reader_config_save = False
        self._reader_config = dict(normalized)
        if persist:
            self._save_reader_settings()

    def _save_reader_setting(self, key: str, value: int) -> None:
        """保存单个阅读设置项。

        Args:
            key (str): 设置项名称
            value (int): 设置项值
        """
        if self._reader_config.get(key) == value:
            return
        self._reader_config[key] = value
        self._save_reader_settings()

    def _save_reader_settings(self) -> None:
        """持久化全部阅读设置。"""
        try:
            db = LibraryDB()
            db.set_config(READER_CONFIG_KEY, self._reader_config)
            db.close()
        except Exception as exc:  # pylint: disable=broad-except
            get_logger().warning("Failed to save reader settings: %s", exc)
