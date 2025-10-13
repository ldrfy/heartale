# page_bookshelf.py
import json
from pathlib import Path

from gi.repository import Adw, GLib, Gtk

from .book_tile import BookTile
from .page_reader import ReaderPage

DATA_DIR = Path.home() / ".config" / "heartale"

BOOKS_FILE = DATA_DIR / "books.json"

@Gtk.Template(resource_path="/cool/ldr/heartale/page_bookshelf.ui")
class BookshelfPage(Adw.NavigationPage):
    __gtype_name__ = "BookshelfPage"

    shelf_root: Gtk.Box = Gtk.Template.Child("shelf_root")
    flow_books: Gtk.FlowBox = Gtk.Template.Child("flow_books")


    def __init__(self, nav, **kwargs):
        super().__init__(**kwargs)

        self._widget_to_book = {}  # widget -> book 映射，便于删除
        BOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)

        self.books = self.load_books(default=[])
        self.nav = nav
        print(self.books)
        print(self.flow_books)

        self.refresh_shelf()

    # ------------ 数据 I/O ------------
    def load_books(self, default=None):
        print(BOOKS_FILE)
        try:
            with BOOKS_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default if default is not None else []
        except json.JSONDecodeError:
            return default if default is not None else []

    def save_books(self, data):
        tmp = BOOKS_FILE.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(BOOKS_FILE)

    # ------------ 列表渲染 ------------
    def refresh_shelf(self):
        # 清空
        self._widget_to_book.clear()
        child = self.flow_books.get_first_child()
        while child:
            self.flow_books.remove(child)
            child = self.flow_books.get_first_child()
        # 追加

        for book in self.books:

            tile = BookTile(book)
            self.flow_books.append(tile)

    # ------------ 交互逻辑 ------------

    def open_book_page(self, book: dict):
        # 你的页面跳转逻辑
        print("open:", book)

        self.nav.push(ReaderPage(self.nav, book))

    def on_import_clicked(self, _btn):
        dlg = Gtk.FileDialog.new()
        dlg.set_title("选择要导入的书籍")
        ff = Gtk.FileFilter()
        ff.set_name("文档与电子书")
        for suf in ("pdf", "epub", "djvu"):
            ff.add_suffix(suf)
        dlg.set_default_filter(ff)

        def _done(d, res):
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error:
                return
            added = 0
            for f in files:
                path = f.get_path()
                if not path:
                    continue
                self.books.append({"path": path, "title": Path(path).stem})
                added += 1
            if added:
                self.save_books(self.books)
                self.refresh_shelf()

        dlg.open_multiple(self, None, _done)

    def on_delete_selected_clicked(self, button: Gtk.Button):
        selected = list(self.flow_books.get_selected_children())
        if not selected:
            return
        dlg = Adw.MessageDialog.new(self, "删除所选书籍？", f"将删除 {len(selected)} 项")
        dlg.add_response("cancel", "取消")
        dlg.add_response("delete", "删除")
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")
        dlg.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def _resp(d, resp):
            if resp != "delete":
                return
            # 收集被选中的书并从数据中删除
            ids = set()
            for ch in selected:
                tile = ch.get_child()
                book = getattr(tile, "book", None)
                if book is not None:
                    ids.add(id(book))
            self.books = [b for b in self.books if id(b) not in ids]
            self.save_books(self.books)
            self.refresh_shelf()

        dlg.connect("response", _resp)
        dlg.present()

    @Gtk.Template.Callback()
    def on_flow_child_activated(self, flow: Gtk.FlowBox, child: Gtk.FlowBoxChild):
        tile = child.get_child()
        book = getattr(tile, "book", None)
        if book is not None:
            self.open_book_page(book)

