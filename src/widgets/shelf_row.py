"""Shelf row component."""

from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk  # type: ignore

from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book, BookObject


@Gtk.Template(resource_path="/cool/ldr/heartale/shelf_row.ui")
class ShelfRow(Gtk.Box):
    """List row that displays a single book entry."""
    __gtype_name__ = "ShelfRow"
    __gsignals__ = {
        "delete-request": (GObject.SignalFlags.RUN_FIRST, None,
                           (GObject.TYPE_PYOBJECT,)),
        "top-request": (GObject.SignalFlags.RUN_FIRST, None,
                        (GObject.TYPE_PYOBJECT,)),
    }

    lbl_title: Gtk.Label = Gtk.Template.Child()
    lbl_sub: Gtk.Label = Gtk.Template.Child()
    btn_top: Gtk.Button = Gtk.Template.Child()  # Toggle pin button

    def __init__(self, **kw):
        super().__init__(**kw)
        self.book = None

    @Gtk.Template.Callback()
    def _on_book_del(self, *_):
        self.emit("delete-request", self.book)

    @Gtk.Template.Callback()
    def _on_book_top(self, *_):
        self.emit("top-request", self.book)

    def update(self, bobj: BookObject):
        """Refresh the row with data from ``bobj``."""
        book: Book = bobj.to_dataclass()
        self.book = book
        name = book.name or _("(Untitled)")

        if book.fmt == BOOK_FMT_LEGADO:
            name += " [Legado]"
        elif book.fmt == BOOK_FMT_TXT:
            name += " [TXT]"

        self.lbl_title.set_text(name)

        self.lbl_sub.set_text(book.get_jd_str())

        context = self.btn_top.get_style_context()

        if book.sort > 0:
            context.add_class("top")
            self.btn_top.set_icon_name("go-bottom-symbolic")
            self.btn_top.set_tooltip_text(_("Unpin this book"))
        else:
            context.remove_class("top")
            self.btn_top.set_icon_name("go-top-symbolic")
            self.btn_top.set_tooltip_text(_("Pin this book"))
