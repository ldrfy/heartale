"""窗口"""

from pathlib import Path

from gi.repository import Adw, GLib, Gtk  # type: ignore

from .entity import LibraryDB
from .entity.utils import path2book
from .pages.page_bookshelf import BookshelfPage
from .pages.page_empty import EmptyPage
from .pages.page_reader import ReaderPage


@Gtk.Template(resource_path="/cool/ldr/heartale/window.ui")
class HeartaleWindow(Adw.ApplicationWindow):
    """_summary_

    Args:
        Adw (_type_): _description_
    """
    __gtype_name__ = "HeartaleWindow"

    # 全局导航与头部按钮
    nav: Adw.NavigationView = Gtk.Template.Child("nav")
    btn_back: Gtk.Button = Gtk.Template.Child("btn_back")
    btn_import: Gtk.Button = Gtk.Template.Child("btn_import")
    btn_delete: Gtk.Button = Gtk.Template.Child("btn_delete")
    btn_play: Gtk.Button = Gtk.Template.Child("btn_play")

    # 页面实例
    page_empty = None
    page_bookshelf: BookshelfPage = None
    page_reader = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.page_bookshelf = BookshelfPage(self.nav)
        self.nav.push(self.page_bookshelf)
        self._sync_header()

    # ---------- Header 同步 ----------
    def _sync_header(self):
        page = self.nav.get_visible_page()
        if not page:
            return

        on_page_empty = isinstance(page, EmptyPage)
        on_page_bookshelf = isinstance(page, BookshelfPage)
        on_page_reader = isinstance(page, ReaderPage)

        self.btn_back.set_visible(on_page_reader)
        self.btn_play.set_visible(on_page_reader)
        self.btn_import.set_visible(on_page_bookshelf)
        self.btn_delete.set_visible(on_page_bookshelf)

    @Gtk.Template.Callback()
    def on_visible_page_changed(self, *_):
        self._sync_header()

    @Gtk.Template.Callback()
    def on_back(self, *_):
        page = self.nav.get_visible_page()
        if page and page.get_can_pop():
            self.nav.pop()

    @Gtk.Template.Callback()
    def on_play_book(self, _btn):
        print("TODO: Play / Read")

    @Gtk.Template.Callback()
    def on_delete_books(self, _btn):
        self.page_bookshelf.on_delete_selected_clicked(_btn)

    @Gtk.Template.Callback()
    def on_import_book(self, _btn):
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
                db.close()
                self.page_bookshelf.refresh_shelf()
            if s_error:
                edlg = Adw.MessageDialog.new(
                    self.get_root(), "导入部分失败", s_error)
                edlg.add_response("ok", "确定")
                edlg.set_default_response("ok")
                edlg.set_close_response("ok")
                edlg.present()

        dlg.open_multiple(self, None, _done)
