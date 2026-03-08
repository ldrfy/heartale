"""书籍属性侧栏。"""
import threading
from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity import LibraryDB, _format_words_compact
from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from ..entity.time_read import TIME_READ_WAY_LISTEN, TIME_READ_WAY_READ
from ..utils import get_file_size, get_time
from ..utils.gui import open_folder, open_url


@Gtk.Template(resource_path="/cool/ldr/heartale/properties_view.ui")
class HPropertiesView(Adw.Bin):
    """显示当前书籍的属性与阅读统计。"""

    __gtype_name__ = "HPropertiesView"
    aar_book_uri: Adw.ActionRow = Gtk.Template.Child()
    aar_book_txt_all: Adw.ActionRow = Gtk.Template.Child()
    aar_book_words: Adw.ActionRow = Gtk.Template.Child()
    aar_book_fmt: Adw.ActionRow = Gtk.Template.Child()
    aar_file_size: Adw.ActionRow = Gtk.Template.Child()
    file_created: Adw.ActionRow = Gtk.Template.Child()
    file_modified: Adw.ActionRow = Gtk.Template.Child()
    aar_folder: Adw.ActionRow = Gtk.Template.Child()
    folder_button: Gtk.Button = Gtk.Template.Child()

    read_time_year: Adw.ActionRow = Gtk.Template.Child()
    read_time_last_year: Adw.ActionRow = Gtk.Template.Child()
    read_time_month: Adw.ActionRow = Gtk.Template.Child()
    read_time_last_month: Adw.ActionRow = Gtk.Template.Child()
    read_time_week: Adw.ActionRow = Gtk.Template.Child()
    read_time_last_week: Adw.ActionRow = Gtk.Template.Child()
    read_time_day: Adw.ActionRow = Gtk.Template.Child()
    read_time_yesterday: Adw.ActionRow = Gtk.Template.Child()
    read_time_all: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self, **kwargs):
        self.book: Book = None
        super().__init__(**kwargs)

    def set_data(self, book: Book):
        """使用书籍数据刷新属性侧栏。

        Args:
            book (Book): 书籍信息
        """
        self.book = book

        def worker():
            book_md5 = self.book.md5
            db = LibraryDB()

            read_time_stats = {
                "year": self._merge_read_and_listen(
                    db.get_td_year(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_year(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "last_year": self._merge_read_and_listen(
                    db.get_td_last_year(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_last_year(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "month": self._merge_read_and_listen(
                    db.get_td_month(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_month(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "last_month": self._merge_read_and_listen(
                    db.get_td_last_month(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_last_month(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "week": self._merge_read_and_listen(
                    db.get_td_week(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_week(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "last_week": self._merge_read_and_listen(
                    db.get_td_last_week(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_last_week(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "day": self._merge_read_and_listen(
                    db.get_td_day(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_day(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "yesterday": self._merge_read_and_listen(
                    db.get_td_yesterday(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_yesterday(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
                "all": self._merge_read_and_listen(
                    db.get_td_all(book_md5, way=TIME_READ_WAY_READ),
                    db.get_td_all(book_md5, way=TIME_READ_WAY_LISTEN),
                ),
            }
            ps = {
                "name": f"{book.name}",
                "path": f"{book.get_path()}",
                "read_time_stats": read_time_stats,
                "chapters": str(max(0, int(book.chap_all))),
                "word_count": _format_words_compact(max(0, int(book.txt_all))),
                "fmt": self._get_fmt(),
                "file_size": self._get_file_size(),
                "created_at": get_time(book.create_date),
                "updated_at": get_time(book.update_date),
                "is_legado": book.fmt == BOOK_FMT_LEGADO,
            }

            db.close()
            GLib.idle_add(update_ui, ps,
                          priority=GLib.PRIORITY_DEFAULT)

        def update_ui(ps):
            self.aar_folder.set_subtitle(ps["name"])
            self.aar_book_uri.set_subtitle(ps["path"])
            self._update_open_button(ps["is_legado"])

            stats = ps["read_time_stats"]
            self.read_time_year.set_subtitle(stats["year"])
            self.read_time_last_year.set_subtitle(stats["last_year"])
            self.read_time_month.set_subtitle(stats["month"])
            self.read_time_last_month.set_subtitle(stats["last_month"])
            self.read_time_week.set_subtitle(stats["week"])
            self.read_time_last_week.set_subtitle(stats["last_week"])
            self.read_time_day.set_subtitle(stats["day"])
            self.read_time_yesterday.set_subtitle(stats["yesterday"])
            self.read_time_all.set_subtitle(stats["all"])

            self.aar_book_txt_all.set_subtitle(ps["chapters"])
            self.aar_book_words.set_subtitle(ps["word_count"])
            self.aar_book_fmt.set_subtitle(ps["fmt"])
            self.aar_file_size.set_subtitle(ps["file_size"])

            self.file_created.set_subtitle(ps["created_at"])
            self.file_modified.set_subtitle(ps["updated_at"])

        threading.Thread(target=worker, daemon=True).start()

    def _get_file_size(self):
        """返回当前书籍文件大小文本。

        Returns:
            str: 文件大小文本
        """
        if self.book.fmt == BOOK_FMT_LEGADO:
            return _("Unknown size")
        return get_file_size(self.book.path)

    def _get_fmt(self):
        """返回当前书籍格式文本。

        Returns:
            str: 书籍格式说明
        """
        if self.book.fmt == BOOK_FMT_LEGADO:
            return "Legado"

        if self.book.fmt == BOOK_FMT_TXT:
            return _("Plain text (encoding {encoding})").format(encoding=self.book.encoding)

        return _("Unknown format")

    def _merge_read_and_listen(self, read_stat: str, listen_stat: str) -> str:
        """合并阅读与朗读统计文本。

        Args:
            read_stat (str): 阅读统计
            listen_stat (str): 朗读统计

        Returns:
            str: 合并后的统计文本
        """
        return _("Read: {read}\nListen: {listen}").format(
            read=read_stat, listen=listen_stat
        )

    def _update_open_button(self, is_legado: bool) -> None:
        """按书籍类型更新打开按钮的图标与文案。

        Args:
            is_legado (bool): 是否为 Legado 书籍
        """
        if is_legado:
            self.aar_folder.set_title(_("Link"))
            self.folder_button.set_icon_name("folder-remote-symbolic")
            self.folder_button.set_tooltip_text(_("Open Link"))
            return

        self.aar_folder.set_title(_("Folder"))
        self.folder_button.set_icon_name("folder-open-symbolic")
        self.folder_button.set_tooltip_text(_("Open Containing Folder"))

    def open_current_resource(self) -> None:
        """打开当前书籍对应的链接或所在文件夹。"""
        if not self.book:
            return
        if self.book.fmt == BOOK_FMT_LEGADO:
            open_url(self.book.path)
            return
        open_folder(self.book.path)

    @Gtk.Template.Callback()
    def _on_open_file(self, *_):
        """响应按钮点击并打开当前书籍资源。"""
        self.open_current_resource()
