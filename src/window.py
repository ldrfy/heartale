"""主窗口"""

from gi.repository import Adw, Gtk  # type: ignore

from .pages.reader_page import ReaderPage
from .pages.shelf_page import ShelfPage


@Gtk.Template(resource_path="/cool/ldr/heartale/window.ui")
class HeartaleWindow(Adw.ApplicationWindow):
    """主窗口

    Args:
        Adw (_type_): _description_
    """
    __gtype_name__ = "HeartaleWindow"

    nav: Adw.NavigationView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._reader_page = ReaderPage(self.nav)
        self._shelf_page = ShelfPage(self.nav, self._reader_page)

        self.nav.push(self._shelf_page)
