"""属性"""
import threading

from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk

from ..entity import LibraryDB
from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from ..utils import get_file_size, get_time, open_folder


@Gtk.Template(resource_path="/cool/ldr/heartale/properties_view.ui")
class HPropertiesView(Adw.Bin):
    """_summary_

    Args:
        Adw (_type_): _description_
    """
    __gtype_name__ = "HPropertiesView"
    aar_book_uri: Adw.ActionRow = Gtk.Template.Child()
    aar_book_txt_all: Adw.ActionRow = Gtk.Template.Child()
    aar_book_fmt: Adw.ActionRow = Gtk.Template.Child()
    aar_file_size: Adw.ActionRow = Gtk.Template.Child()
    file_created: Adw.ActionRow = Gtk.Template.Child()
    file_modified: Adw.ActionRow = Gtk.Template.Child()
    aar_folder: Adw.ActionRow = Gtk.Template.Child()

    read_time_year: Adw.ActionRow = Gtk.Template.Child()
    read_time_month: Adw.ActionRow = Gtk.Template.Child()
    read_time_week: Adw.ActionRow = Gtk.Template.Child()
    read_time_day: Adw.ActionRow = Gtk.Template.Child()
    read_time_all: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self, **kwargs):
        self.book: Book = None
        super().__init__(**kwargs)

        # Template 的子控件可用 Gtk.Template.Child() 绑定

    def set_data(self, book: Book):
        """Populate the view with information about ``book``."""
        self.book = book

        def worker():
            book_md5 = self.book.md5
            db = LibraryDB()

            ps = (
                f"{book.name}",
                f"{book.get_path()}",

                db.get_td_year(book_md5),
                db.get_td_month(book_md5),
                db.get_td_week(book_md5),
                db.get_td_day(book_md5),
                db.get_td_all(book_md5),

                _("{count} characters").format(count=book.txt_all),
                self._get_fmt(),
                self._get_file_size(),

                get_time(book.create_date),
                get_time(book.update_date),
            )

            db.close()
            GLib.idle_add(update_ui, ps,
                          priority=GLib.PRIORITY_DEFAULT)

        def update_ui(ps):
            name, path, y, m, w, d, a, ws, fmt, fs, dc, du = ps
            self.aar_folder.set_subtitle(name)
            self.aar_book_uri.set_subtitle(path)

            self.read_time_year.set_subtitle(y)
            self.read_time_month.set_subtitle(m)
            self.read_time_week.set_subtitle(w)
            self.read_time_day.set_subtitle(d)
            self.read_time_all.set_subtitle(a)

            self.aar_book_txt_all.set_subtitle(ws)
            self.aar_book_fmt.set_subtitle(fmt)
            self.aar_file_size.set_subtitle(fs)

            self.file_created.set_subtitle(dc)
            self.file_modified.set_subtitle(du)

        threading.Thread(target=worker, daemon=True).start()

    def _get_file_size(self):
        if self.book.fmt == BOOK_FMT_LEGADO:
            return _("Unknown size")
        return get_file_size(self.book.path)

    def _get_fmt(self):
        if self.book.fmt == BOOK_FMT_LEGADO:
            return _("Legado format")

        if self.book.fmt == BOOK_FMT_TXT:
            return _("Plain text format (encoding {encoding})").format(encoding=self.book.encoding)

        return _("Unknown format")

    @Gtk.Template.Callback()
    def _on_open_file(self, *_):
        if not self.book:
            return
        if self.book.fmt == BOOK_FMT_LEGADO:
            return
        open_folder(self.book.path)
