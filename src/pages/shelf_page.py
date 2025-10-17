"""书架页面"""

import threading
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk  # type: ignore

from ..entity import LibraryDB
from ..entity.book import BookObject
from ..servers.legado import sync_legado_books
from ..servers.txt import path2book
from ..utils.debug import get_logger
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

    search: Gtk.SearchEntry = Gtk.Template.Child()
    btn_search: Gtk.ToggleButton = Gtk.Template.Child()
    rev_search: Gtk.Revealer = Gtk.Template.Child()
    btn_sync: Gtk.Button = Gtk.Template.Child()
    spinner_sync: Gtk.Spinner = Gtk.Template.Child()

    list: Gtk.ListView = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    scroller: Gtk.ScrolledWindow = Gtk.Template.Child()
    empty: Adw.StatusPage = Gtk.Template.Child()
    search_empty: Adw.StatusPage = Gtk.Template.Child()
    btn_import: Gtk.Button = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, reader_page: ReaderPage, **kwargs):
        super().__init__(**kwargs)
        self._nav: Adw.NavigationView = nav
        self._reader_page: ReaderPage = reader_page
        self._reader_page_opened = False
        self._build_factory()

        self._search_debounce_id = 0

        self._install_shortcuts()

    def reload_bookshel(self):
        """重新加载书架数据
        """
        print("重新加载书架数据")
        db = LibraryDB()
        books = list(db.iter_books())
        db.close()
        self.build_bookshel(books)

    def build_bookshel(self, books, is_search=False):
        """构建书架
        """
        if len(books) == 0:
            if is_search:
                self.stack.set_visible_child(self.search_empty)  # 空列表但非空态
                return
            self.stack.set_visible_child(self.empty)
            return

        gls: Gio.ListStore = Gio.ListStore.new(BookObject)
        for b in books:
            gls.append(BookObject.from_dataclass(b))
        # liststore 应为 Gio.ListStore(BookObject)
        self.list.set_model(Gtk.SingleSelection.new(gls))
        self.stack.set_visible_child(self.scroller)

    def _install_shortcuts(self):
        sc = Gtk.ShortcutController()
        sc.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>F"),
            Gtk.CallbackAction.new(lambda *_: (self.btn_search.set_active(True),
                                               self.search.grab_focus(), True))
        ))
        self.add_controller(sc)

    def _build_factory(self):
        """初始化模型，仅一次
        """
        factory = Gtk.SignalListItemFactory()

        def setup(_f, li: Gtk.ListItem):
            row = ShelfRow()
            # 连接一次行内的删除信号，回调里调用页面的方法删除数据
            row.connect("delete-request", lambda _row,
                        bobj: self._present_delete_confirm_adw(bobj))
            row.connect("top-request", lambda _row,
                        bobj: self._on_shelfrow_top(bobj))
            li.set_child(row)

        def bind(_f, li: Gtk.ListItem):
            row: ShelfRow = li.get_child()
            row.update(li.get_item())

        factory.connect("setup", setup)
        factory.connect("bind", bind)

        self.list.set_factory(factory)

    def _on_shelfrow_top(self, bobj: BookObject):
        db = LibraryDB()

        book = bobj.to_dataclass()

        if book.sort > 0:
            # 已置顶，取消置顶
            book.sort = 0.0
        else:
            book.sort = 1

        db.save_book(book)

        books_ = list(db.iter_books())
        db.close()
        self.build_bookshel(books_)

    def _do_delete_row(self, bobj: BookObject):
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
            get_logger().error("删除数据库记录失败：%s", e)

        # 真正从模型移除
        store.remove(idx)

        # 空态 or 恢复选中
        if store.get_n_items() == 0:
            self.stack.set_visible_child(self.empty)

    def _present_delete_confirm_adw(self, bobj):
        """删除确认

        Args:
            bobj (_type_): _description_
        """
        dlg = Adw.MessageDialog(
            transient_for=self.get_root(),
            modal=True,
            heading="确认删除？",
            body=f"将从书库移除《{getattr(bobj, 'name', '未命名')}》。\n此操作不可撤销。",
        )
        dlg.add_response("cancel", "取消")
        dlg.add_response("delete", "删除")
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")
        dlg.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def _on_resp(_d, resp):
            if resp == "delete":
                self._do_delete_row(bobj)
        dlg.connect("response", _on_resp)
        dlg.present()

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
                get_logger().error("书架导入失败：%s", e)
                s_error += f"{e}\n"
                return

            books = []
            for f in files:
                try:
                    book = path2book(f.get_path())
                except (FileNotFoundError, ValueError) as e:
                    get_logger().error("书籍导入失败：%s", e)
                    s_error += f"{Path(f.get_path()).name}: {e}\n"
                    continue
                books.append(book)

            if len(books) > 0:
                db = LibraryDB()
                for b in books:
                    db.save_book(b)
                books_ = list(db.iter_books())
                db.close()
                self.build_bookshel(books_)

            if s_error:
                edlg = Adw.MessageDialog.new(self.get_root(),
                                             "导入部分失败", s_error)
                edlg.add_response("ok", "确定")
                edlg.set_default_response("ok")
                edlg.set_close_response("ok")
                edlg.present()

        dlg.open_multiple(self.get_root(), None, _done)

    def _apply_search(self, *_args):
        self._search_debounce_id = 0
        kw = self.search.get_text().strip()
        # 支持空串 = 全部；转义 %/_，避免被当通配符
        esc = kw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pat = "%" if not kw else f"%{esc}%"

        db = LibraryDB()
        books = list(db.search_books_by_name(pat, limit=1000))
        db.close()
        self.build_bookshel(books, True)
        return False

    @Gtk.Template.Callback()
    def _on_shelf_activate(self, listview: Gtk.ListView, position: int):
        self._reader_page_opened = True
        self._nav.push(self._reader_page)

        selection: Gtk.SingleSelection = listview.get_model()
        bobj: BookObject = selection.get_item(position)
        self._reader_page.set_data(bobj.to_dataclass())

    @Gtk.Template.Callback()
    def _on_search_changed(self, entry: Gtk.SearchEntry):
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
        self._search_debounce_id = GLib.timeout_add(200, self._apply_search,
                                                    entry.get_text().strip())
        print(self._search_debounce_id)

    @Gtk.Template.Callback()
    def _on_clear_search(self, *_):
        self.search.set_text("")
        self._apply_search()  # 你的检索函数

    @Gtk.Template.Callback()
    def _on_search_toggle(self, btn: Gtk.ToggleButton):
        active = btn.get_active()
        self.rev_search.set_reveal_child(active)
        if active:
            GLib.idle_add(self.search.grab_focus)
        else:
            # 可选：收起时清空搜索
            # self.search.set_text("")
            pass

    @Gtk.Template.Callback()
    def _on_search_stop(self, *_):
        # Esc 或点叉关闭搜索
        self.search.set_text("")
        self.rev_search.set_reveal_child(False)
        self.btn_search.set_active(False)
        self._apply_search()  # 触发一次“显示全部”

    @Gtk.Template.Callback()
    def _on_import_book_legado(self, *_):

        self.btn_sync.set_visible(False)
        self.spinner_sync.set_visible(True)
        self.spinner_sync.start()

        def uodate_ui(sync_ok, s_error):
            """更新
            """
            self.reload_bookshel()

            self.btn_sync.set_visible(True)
            self.spinner_sync.stop()
            self.spinner_sync.set_visible(False)

            if sync_ok:
                self.get_root().toast_msg("Legado书籍同步完成")
                return

            edlg = Adw.MessageDialog.new(self.get_root(),
                                         "Legado书籍同步部分失败", s_error)
            edlg.add_response("ok", "确定")
            edlg.set_default_response("ok")
            edlg.set_close_response("ok")
            edlg.present()

        def worker():
            # 耗时操作放线程
            sync_ok, s_error = sync_legado_books()
            GLib.idle_add(uodate_ui, sync_ok,
                          s_error, priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=worker, daemon=True).start()
