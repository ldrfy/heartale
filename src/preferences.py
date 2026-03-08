"""Preferences dialog."""

from gettext import gettext as _

from gi.repository import Adw, Gtk  # type: ignore

from .servers.legado import (get_legado_sync_book_n, get_legado_sync_url,
                             set_legado_sync_book_n, set_legado_sync_url)
from .tts.backends import create_active_tts_backend


@Gtk.Template(resource_path="/cool/ldr/heartale/preference.ui")
class PreferencesDialog(Adw.PreferencesDialog):
    """Application preferences dialog."""

    __gtype_name__ = "PreferencesDialog"

    tts_url_base: Adw.EntryRow = Gtk.Template.Child()
    tts_engine: Adw.EntryRow = Gtk.Template.Child()
    tts_rate: Adw.SpinRow = Gtk.Template.Child()
    tts_pitch: Adw.SpinRow = Gtk.Template.Child()
    legado_sync_url: Adw.EntryRow = Gtk.Template.Child()
    legado_sync_book_n: Adw.SpinRow = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tts = create_active_tts_backend()
        self.reload_settings()
        self.tts_rate.get_adjustment().connect(
            "value-changed", self._on_tts_numeric_changed
        )
        self.tts_pitch.get_adjustment().connect(
            "value-changed", self._on_tts_numeric_changed
        )
        self.legado_sync_book_n.get_adjustment().connect(
            "value-changed", self._on_legado_sync_book_n_changed
        )

    def reload_settings(self) -> None:
        """重新加载偏好设置内容。"""
        self._load_tts_config()
        self._load_legado_config()
        self._load_sync_config()

    def reset_tts_settings(self) -> None:
        """重置 Android TTS 设置并刷新界面。"""
        self.tts.set_config(self.tts.default_config)
        self._load_tts_config()

    def _load_tts_config(self):
        cfg = self.tts.get_config()
        self.tts_url_base.set_text(str(cfg.get("url_base", "")))
        self.tts_engine.set_text(str(cfg.get("engine", "")))
        self.tts_rate.set_value(float(cfg.get("rate", 50)))
        self.tts_pitch.set_value(float(cfg.get("pitch", 100)))

    def _save_tts_config(self):
        cfg = self.tts.update_config(
            url_base=self.tts_url_base.get_text().strip(),
            engine=self.tts_engine.get_text().strip(),
            rate=int(self.tts_rate.get_value()),
            pitch=int(self.tts_pitch.get_value()),
        )
        return cfg

    def _save_tts_numeric(self):
        self.tts.update_config(
            rate=int(self.tts_rate.get_value()),
            pitch=int(self.tts_pitch.get_value()),
        )

    def _load_legado_config(self):
        self.legado_sync_url.set_text(get_legado_sync_url())

    def _load_sync_config(self):
        self.legado_sync_book_n.set_value(float(get_legado_sync_book_n()))

    def _toast(self, msg: str):
        self.add_toast(Adw.Toast.new(msg))

    @Gtk.Template.Callback()
    def _on_apply_tts(self, _row):
        try:
            self._save_tts_config()
            self._toast(_("TTS settings saved"))
        except Exception as exc:  # pylint: disable=broad-except
            self._toast(str(exc))

    def _on_tts_numeric_changed(self, _adj):
        try:
            self._save_tts_numeric()
        except Exception as exc:  # pylint: disable=broad-except
            self._toast(str(exc))

    @Gtk.Template.Callback()
    def _on_reset_tts(self, _btn):
        self.reset_tts_settings()
        self._toast(_("TTS settings reset to defaults"))

    @Gtk.Template.Callback()
    def _on_apply_legado(self, _row):
        try:
            url = set_legado_sync_url(self.legado_sync_url.get_text())
            self.legado_sync_url.set_text(url)
            self._toast(_("Legado sync URL saved"))
        except Exception as exc:  # pylint: disable=broad-except
            self._toast(str(exc))

    def _on_legado_sync_book_n_changed(self, _adj):
        try:
            n = set_legado_sync_book_n(
                int(self.legado_sync_book_n.get_value()))
            self.legado_sync_book_n.set_value(float(n))
        except Exception as exc:  # pylint: disable=broad-except
            self._toast(str(exc))
