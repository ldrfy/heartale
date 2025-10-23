"""属性"""
from gi.repository import Adw, Gtk

from ..entity import LibraryDB
from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book, BookObject
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
        self.db = LibraryDB()
        super().__init__(**kwargs)
        # Template 的子控件可用 Gtk.Template.Child() 绑定

    def set_data(self, book: Book):
        """_summary_

        Args:
            book_obj (_type_): _description_
        """
        self.book = book

        self.aar_folder.set_subtitle(f"{book.name}")
        self.aar_book_uri.set_subtitle(f"{book.get_path()}")

        self.aar_book_txt_all.set_subtitle(f"{book.txt_all} 字")
        self.aar_book_fmt.set_subtitle(self._get_fmt())
        self.aar_file_size.set_subtitle(self._get_file_size())

        self.file_created.set_subtitle(get_time(book.create_date))
        self.file_modified.set_subtitle(get_time(book.update_date))

        book_md5 = self.book.md5

        self.read_time_year.set_subtitle(self.db.get_td_year(book_md5))
        self.read_time_month.set_subtitle(self.db.get_td_month(book_md5))
        self.read_time_week.set_subtitle(self.db.get_td_week(book_md5))
        self.read_time_day.set_subtitle(self.db.get_td_day(book_md5))

    def _get_file_size(self):
        if self.book.fmt == BOOK_FMT_LEGADO:
            return "未知大小"
        return get_file_size(self.book.path)

    def _get_fmt(self):
        if self.book.fmt == BOOK_FMT_LEGADO:
            return "Legado 格式"

        if self.book.fmt == BOOK_FMT_TXT:
            return "纯文本格式" + f"（编码 {self.book.encoding}）"

        return "未知格式"

    @Gtk.Template.Callback()
    def _on_open_file(self, *_):
        if not self.book:
            return
        if self.book.fmt == BOOK_FMT_LEGADO:
            return
        open_folder(self.book.path)
