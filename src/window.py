"""Main application window."""

from gi.repository import Adw, Gtk  # type: ignore

from .pages.reader_page import ReaderPage
from .pages.shelf_page import ShelfPage


@Gtk.Template(resource_path="/cool/ldr/heartale/window.ui")
class HeartaleWindow(Adw.ApplicationWindow):
    """Main application window class."""
    __gtype_name__ = "HeartaleWindow"

    nav: Adw.NavigationView = Gtk.Template.Child()
    toasts: Adw.ToastOverlay = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._reader_page = ReaderPage(self.nav)
        self._shelf_page = ShelfPage(self.nav, self._reader_page)

        self.nav.push(self._shelf_page)

    @Gtk.Template.Callback()
    def on_visible_page_changed(self, *_):
        """Load bookshelf data when the visible page changes."""
        page = self.nav.get_visible_page()
        if not page:
            return

        if isinstance(page, ShelfPage):
            self._shelf_page.reload_bookshel()
            self._reader_page.clear_data()

    def toast_msg(self, toast_msg):
        """Show a toast in the main window."""
        # Work around repeated calls during initialisation
        toast = Adw.Toast.new("")
        toast.set_timeout(2)
        toast.dismiss()
        toast.set_title(toast_msg)
        self.toasts.add_toast(toast)
