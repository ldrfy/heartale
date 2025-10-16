"""书架页面"""

from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk  # type: ignore

from ..entity import LibraryDB
from ..entity.book import BookObject
from ..entity.utils import path2book
from ..widgets.shelf_row import ShelfRow
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
        self._build_factory()
        self.build_bookshel()

    def build_bookshel(self):
        """_summary_
        """
        books: Gio.ListStore = Gio.ListStore.new(BookObject)
        db = LibraryDB()
        for b in db.iter_books():
            books.append(BookObject.from_dataclass(b))
        db.close()
        if books.get_n_items() == 0:
            self.show_empty()
            return
        # liststore 应为 Gio.ListStore(BookObject)
        self.list.set_model(Gtk.SingleSelection.new(books))
        self.stack.set_visible_child(self.scroller)

    def show_empty(self):
        """没有书时显示空状态页
        """
        self.stack.set_visible_child(self.empty)

    def _build_factory(self):
        """初始化模型，仅一次
        """
        factory = Gtk.SignalListItemFactory()

        def setup(_f, li: Gtk.ListItem):
            row = ShelfRow()
            # 连接一次行内的删除信号，回调里调用页面的方法删除数据
            row.connect("delete-request", lambda _row,
                        bobj: self._on_row_delete(bobj))
            li.set_child(row)

        def bind(_f, li: Gtk.ListItem):
            row: ShelfRow = li.get_child()
            row.update(li.get_item())

        factory.connect("setup", setup)
        factory.connect("bind", bind)

        self.list.set_factory(factory)

    def _on_row_delete(self, bobj: BookObject):
        """从 ListStore 删除对应对象，并维护选中项与空态。

        Args:
            bobj (BookObject): _description_

        Returns:
            _type_: _description_
        """
        sel: Gtk.SingleSelection = self.list.get_model()
        store: Gio.ListStore = sel.get_model()

        # 找索引
        idx = -1
        for i in range(store.get_n_items()):
            if store.get_item(i) is bobj:
                idx = i
                break
        if idx < 0:
            return  # 不在模型中

        # （可选）先同步数据库
        try:
            db = LibraryDB()
            db.delete_book_by_md5(bobj.md5)  # 按你的接口调整
            db.close()
        except Exception as e:  # pylint: disable=broad-except
            print("删除数据库记录失败：", e)

        # 真正从模型移除
        store.remove(idx)

        # 空态 or 恢复选中
        if store.get_n_items() == 0:
            self.show_empty()

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
            s_error = ""
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error as e:
                s_error += f"{e}\n"
                return

            books = []
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
                db.close()
                self.build_bookshel()

            if s_error:
                edlg = Adw.MessageDialog.new(self.get_root(),
                                             "导入部分失败", s_error)
                edlg.add_response("ok", "确定")
                edlg.set_default_response("ok")
                edlg.set_close_response("ok")
                edlg.present()

        dlg.open_multiple(self.get_root(), None, _done)

    @Gtk.Template.Callback()
    def _on_shelf_activate(self, listview: Gtk.ListView, position: int):
        self._nav.push(self._reader_page)

        selection: Gtk.SingleSelection = listview.get_model()
        bobj: BookObject = selection.get_item(position)
        self._reader_page.set_data(bobj.to_dataclass())
