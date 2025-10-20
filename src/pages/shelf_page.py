"""书架页面"""

import threading
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk  # type: ignore

from ..entity import LibraryDB
from ..entity.book import BookObject
from ..servers.legado import sync_legado_books
from ..servers.txt import path2book
from ..utils.debug import get_logger
from ..widgets.dialog_input import InputDialog
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
    gb_bookshelf: Gtk.Box = Gtk.Template.Child()
    empty: Adw.StatusPage = Gtk.Template.Child()
    search_empty: Adw.StatusPage = Gtk.Template.Child()
    btn_import: Gtk.Button = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, reader_page: ReaderPage, **kwargs):
        super().__init__(**kwargs)

        self.url_legado_sync = "http://"
        self._nav: Adw.NavigationView = nav
        self._reader_page: ReaderPage = reader_page
        self._reader_page_opened = False
        self._build_factory()

        self._search_debounce_id = 0

        self._install_shortcuts()

        # 拖拽导入书籍
        drop_controller = Gtk.DropTarget.new(
            type=GObject.TYPE_NONE, actions=Gdk.DragAction.COPY
        )
        drop_controller.set_gtypes([Gdk.FileList])
        drop_controller.connect("drop", self._on_drop)
        self.add_controller(drop_controller)

    def _on_drop(self, _drop, value, _x, _y):
        """
        value 通常是一个包含 URI 列表的字符串。
        返回 True 表示处理完成。
        """
        if not value:
            return False
        self._add_book(value)
        return True

    def reload_bookshel(self):
        """重新加载书架数据
        """
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
                get_logger().error("文件获取失败：%s", e)
                s_error += f"{e}\n"
                self.get_root().toast_msg("文件获取失败")
                return

            self._add_book(files)

        dlg.open_multiple(self.get_root(), None, _done)

    def _add_book(self, files):
        """根据路径保存书籍并刷新

        Args:
            paths (_type_): _description_
        """
        paths = []
        for f in files:
            paths.append(f.get_path())
        books = []
        s_error = ""
        for path in paths:
            try:
                book = path2book(path)
            except (FileNotFoundError, ValueError) as e:
                get_logger().error("书籍导入失败：%s", e)
                s_error += f"{Path(path).name}: {e}\n"
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
            return

        self.get_root().toast_msg("书籍导入完成")

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

    @Gtk.Template.Callback()
    def _on_search_stop(self, *_):
        # Esc 或点叉关闭搜索
        self.search.set_text("")
        self.rev_search.set_reveal_child(False)
        self.btn_search.set_active(False)
        self._apply_search()  # 触发一次“显示全部”

    @Gtk.Template.Callback()
    def _on_import_book_legado(self, *_):

        def update_ui(sync_ok, s_error):
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

        def worker(url):
            # 耗时操作放线程
            sync_ok, s_error = sync_legado_books(url_base=url)
            self.url_legado_sync = url
            GLib.idle_add(update_ui, sync_ok, s_error,
                          priority=GLib.PRIORITY_DEFAULT)

        def runner(d, r):
            if r != "ok":
                return
            url = d.entry.get_text().strip()

            if url == "" or not url.startswith("http"):
                self.get_root().toast_msg("请输入Legado“web服务”打开以后的内网地址")
                return

            self.btn_sync.set_visible(False)
            self.spinner_sync.set_visible(True)
            self.spinner_sync.start()
            threading.Thread(target=worker, args=(url,),
                             daemon=True).start()

        dlg = InputDialog(self.get_root(), title="Legado书籍同步",
                          subtitle="1. 只同步软件中前5本"
                          "\n2. 在Legado中 “我的” 页面打开 “web服务”"
                          "\n3.请输入打开以后看到的内网地址，如：\nhttp://192.168.1.2:1122")
        dlg.set_input_text(self.url_legado_sync)
        dlg.connect("response", runner)
        dlg.present()
