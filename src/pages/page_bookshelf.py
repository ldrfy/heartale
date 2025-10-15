"""书架"""
import threading
from pathlib import Path

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity import Book, LibraryDB
from ..entity.utils import parse_chap_names
from ..widgets.book_tile import BookTile
from .page_empty import EmptyPage
from .page_reader import ReaderPage

DATA_DIR = Path.home() / ".config" / "heartale"

BOOKS_FILE = DATA_DIR / "books.json"


@Gtk.Template(resource_path="/cool/ldr/heartale/page_bookshelf.ui")
class BookshelfPage(Adw.NavigationPage):
    """_summary_

    Args:
        Adw (_type_): _description_

    Returns:
        _type_: _description_
    """
    __gtype_name__ = "BookshelfPage"

    flow_books: Gtk.FlowBox = Gtk.Template.Child("flow_books")

    def __init__(self, nav, **kwargs):
        super().__init__(**kwargs)

        self._widget_to_book = {}  # widget -> book 映射，便于删除
        BOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)

        self.nav = nav

        db = LibraryDB()
        if len(list(db.iter_books())) == 0:
            self.page_empty = EmptyPage(self)
            self.nav.push(self.page_empty)
        else:
            self.refresh_shelf()
        db.close()

    def refresh_shelf(self):
        """_summary_
        """
        self._widget_to_book.clear()
        child = self.flow_books.get_first_child()
        while child:
            self.flow_books.remove(child)
            child = self.flow_books.get_first_child()
        # 追加
        db = LibraryDB()
        for book in list(db.iter_books()):
            self.flow_books.append(BookTile(book))
        db.close()

    # ------------ 交互逻辑 ------------

    def open_book_page(self, book: Book, sp_book_loading):
        """异步先解析章节名，再打开阅读页

        Args:
            book (dict): _description_
        """
        sp_book_loading.start()

        def _init_data_worker():
            try:
                with open(book.path, "r", encoding=book.encoding) as f:
                    text = f.read()
                chap_names, chaps_ps = parse_chap_names(text)
            except Exception as e:  # pylint: disable=broad-except
                # 回到主线程显示错误
                print(e)
                return
            # 回到主线程更新 UI（非常重要：GTK 只能主线程改）
            GLib.idle_add(_init_data_ready, chap_names, chaps_ps)

        def _init_data_ready(chap_names, chaps_ps):

            self.nav.push(ReaderPage(self.nav, book, chap_names, chaps_ps))
            sp_book_loading.stop()
            sp_book_loading.set_visible(False)
            return False

        threading.Thread(target=_init_data_worker, daemon=True).start()

    def on_delete_selected_clicked(self, _button: Gtk.Button):
        """_summary_

        Args:
            _button (Gtk.Button): _description_
        """
        selected = list(self.flow_books.get_selected_children())

        if not selected:
            return
        dlg = Adw.MessageDialog.new(
            self.get_root(), "删除所选书籍？", f"将删除 {len(selected)} 项")
        dlg.add_response("cancel", "取消")
        dlg.add_response("delete", "删除")
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")
        dlg.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def _resp(_d, resp):
            if resp != "delete":
                return
            # 收集被选中的书并从数据中删除
            db = LibraryDB()
            for ch in selected:
                tile = ch.get_child()
                book = getattr(tile, "book", None)
                if book:
                    db.delete_book_by_md5(book.md5)
            db.close()
            self.refresh_shelf()

        dlg.connect("response", _resp)
        dlg.present()

    @Gtk.Template.Callback()
    def on_flow_child_activated(self, _flow: Gtk.FlowBox, child: Gtk.FlowBoxChild):
        """_summary_

        Args:
            _flow (Gtk.FlowBox): _description_
            child (Gtk.FlowBoxChild): _description_
        """

        book = getattr(child.get_child(), "book", None)
        if book is not None:
            self.open_book_page(book, child.get_child().sp_book_loading)
