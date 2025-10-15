"""书架页面"""

from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk  # type: ignore

from ..entity import LibraryDB
from ..entity.book import BookObject
from ..entity.utils import path2book
from .reader_page import ReaderPage


@Gtk.Template(resource_path="/cool/ldr/heartale/shelf_page.ui")
class ShelfPage(Adw.NavigationPage):
    """书架

    Args:
        Adw (_type_): _description_

    Returns:
        _type_: _description_
    """
    __gtype_name__ = "ShelfPage"

    list: Gtk.ListView = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    scroller: Gtk.ScrolledWindow = Gtk.Template.Child()
    empty: Adw.StatusPage = Gtk.Template.Child()
    btn_import: Gtk.Button = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, reader_page: ReaderPage, **kwargs):
        super().__init__(**kwargs)
        self._nav: Adw.NavigationView = nav
        self._reader_page: ReaderPage = reader_page
        self._books: Gio.ListStore = Gio.ListStore.new(BookObject)
        self._factory = self._build_factory()
        self.set_model()

    def set_model(self):
        db = LibraryDB()
        for b in db.iter_books():
            self._books.append(BookObject.from_dataclass(b))
        db.close()
        # liststore 应为 Gio.ListStore(BookObject)
        selection = Gtk.SingleSelection.new(self._books)
        self.list.set_model(selection)
        self.list.set_factory(self._factory)
        if self._books.get_n_items() > 0:
            self.show_list()
        else:
            self.show_empty()

    def show_list(self):
        self.stack.set_visible_child(self.scroller)

    def show_empty(self):
        self.stack.set_visible_child(self.empty)

    def _build_factory(self):
        factory = Gtk.SignalListItemFactory()

        def setup(_f, li: Gtk.ListItem):
            row = Adw.ActionRow()
            row.set_activatable(True)

            # 行末删除按钮（只在 setup 里创建一次，避免重复绑定）
            btn_del = Gtk.Button(
                icon_name="user-trash-symbolic",
                valign=Gtk.Align.CENTER,
                tooltip_text="删除此书",
            )
            # 用闭包拿到当前 ListItem，点击时读取“当下”的位置
            btn_del.connect("clicked", lambda _b,
                            _li=li: self._on_row_delete(_li))
            row.add_suffix(btn_del)

            li.set_child(row)

        def bind(_f, li: Gtk.ListItem):
            # 绑定 BookObject 到行
            row: Adw.ActionRow = li.get_child()
            bobj: BookObject = li.get_item()
            row.set_title(bobj.name)
            pct = 0 if bobj.txt_all == 0 else int(
                bobj.txt_pos * 100 / bobj.txt_all)
            row.set_subtitle(f"进度 {pct}% · 编码 {bobj.encoding}")

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

    # ========== 删除逻辑 ==========
    def _on_row_delete(self, list_item: Gtk.ListItem):
        # 通过 ListItem 的当前位置删除
        pos = list_item.get_position()
        selection: Gtk.SingleSelection = self.list.get_model()
        store = selection.get_model()  # Gio.ListStore(BookObject)
        if 0 <= pos < store.get_n_items():
            store.remove(pos)
        # 若空，则显示空状态页
        if store.get_n_items() == 0:
            self.show_empty()

        db = LibraryDB()
        db.delete_book_by_md5(list_item.get_item().md5)
        db.close()

    def on_import_book(self):
        self._on_import_book()

    @Gtk.Template.Callback()
    def _on_import_book(self, *_args):
        dlg = Gtk.FileDialog.new()
        dlg.set_title("选择要导入的书籍")
        ff = Gtk.FileFilter()
        ff.set_name("文档与电子书")
        for suf in ("pdf", "epub", "djvu", "txt", "md", "mobi", "azw3"):
            ff.add_suffix(suf)
        dlg.set_default_filter(ff)

        def _done(d, res):
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error:
                return
            books = []
            s_error = ""
            for f in files:
                try:
                    book = path2book(f.get_path())
                except (FileNotFoundError, ValueError) as e:
                    print("Import error:", e)
                    s_error += f"{Path(f.get_path()).name}: {e}\n"
                    continue
                books.append(book)
            if len(books) > 0:
                db = LibraryDB()
                for b in books:
                    db.save_book(b)

                self._books.remove_all()
                for b in db.iter_books():
                    self._books.append(BookObject.from_dataclass(b))
                db.close()
                self.show_list()

            if s_error:
                edlg = Adw.MessageDialog.new(
                    self.get_root(), "导入部分失败", s_error)
                edlg.add_response("ok", "确定")
                edlg.set_default_response("ok")
                edlg.set_close_response("ok")
                edlg.present()

        dlg.open_multiple(self.get_root(), None, _done)

    @Gtk.Template.Callback()
    def _on_shelf_activate(self, listview: Gtk.ListView, position: int):

        selection: Gtk.SingleSelection = listview.get_model()
        bobj: BookObject = selection.get_item(position)
        self._reader_page.set_data(bobj.to_dataclass())

        self._nav.push(self._reader_page)
