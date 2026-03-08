"""Main application window."""

from gi.repository import Adw, GLib, Gtk  # type: ignore

from .pages.reader_page import ReaderPage
from .pages.shelf_page import ShelfPage


@Gtk.Template(resource_path="/cool/ldr/heartale/window.ui")
class HeartaleWindow(Adw.ApplicationWindow):
    """Main application window class."""
    __gtype_name__ = "HeartaleWindow"

    nav: Adw.NavigationView = Gtk.Template.Child()
    toasts: Adw.ToastOverlay = Gtk.Template.Child()
    btn_global_tts_stop: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._reader_page = ReaderPage(self.nav)
        self._shelf_page = ShelfPage(self.nav, self._reader_page)
        self._reader_page.set_tts_state_changed_callback(
            self._on_tts_state_changed
        )

        self.nav.push(self._shelf_page)

    @Gtk.Template.Callback()
    def on_visible_page_changed(self, *_):
        """Load bookshelf data when the visible page changes."""
        page = self.nav.get_visible_page()
        if not page:
            return

        if isinstance(page, ShelfPage):
            self._shelf_page.refresh_header_subtitle()
            self._shelf_page.reload_bookshel()
            if not self._reader_page.is_read_aloud_active():
                self._reader_page.clear_data()
            return

        if isinstance(page, ReaderPage):
            self._reader_page.refresh_current_read_position()
            self._shelf_page.refresh_header_subtitle()

    def toast_msg(self, toast_msg):
        """Show a toast in the main window."""
        # Work around repeated calls during initialisation
        toast = Adw.Toast.new("")
        toast.set_timeout(2)
        toast.dismiss()
        toast.set_title(GLib.markup_escape_text(str(toast_msg)))
        self.toasts.add_toast(toast)

    def _on_tts_state_changed(self, is_playing: bool, status_text: str):
        """同步全局朗读停止按钮的显示状态和提示文本。"""
        self.btn_global_tts_stop.set_visible(bool(is_playing))
        self.btn_global_tts_stop.set_tooltip_text(status_text)
        self._shelf_page.refresh_header_subtitle()

    @Gtk.Template.Callback()
    def on_global_tts_stop_clicked(self, *_):
        """响应全局停止朗读按钮点击事件。"""
        self._reader_page.stop_read_aloud()
