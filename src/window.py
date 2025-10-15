"""主窗口"""

from gi.repository import Adw, Gio, GLib, Gtk  # type: ignore

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

        self._reader_page = ReaderPage()
        self._shelf_page = ShelfPage(self.nav, self._reader_page)

        self.nav.add(self._shelf_page)
        self.nav.add(self._reader_page)

        self._install_actions()
        self.nav.push(self._shelf_page)

    def _install_actions(self):
        act_import = Gio.SimpleAction.new("import-books", None)
        act_import.connect("activate", self.on_import_books)
        self.add_action(act_import)

        act_toggle_sidebar = Gio.SimpleAction.new_stateful(
            "toggle-sidebar",
            None,
            GLib.Variant("b", True),
        )
        act_toggle_sidebar.connect("activate", self.on_toggle_sidebar)
        self.add_action(act_toggle_sidebar)

    def _emit_import_clicked(self, *_args):
        self.lookup_action("import-books").activate(None)

    def on_import_books(self, *_args):
        self._shelf_page.on_import_book()

    def on_toggle_sidebar(self, action, _param):
        current = action.get_state().get_boolean()
        new_state = not current
        action.set_state(GLib.Variant("b", new_state))
        self._reader_page.split.set_show_sidebar(new_state)
