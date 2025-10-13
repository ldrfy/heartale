"""窗口"""

from pathlib import Path

from gi.repository import Adw, GLib, Gtk  # type: ignore

from .page_bookshelf import BookshelfPage
from .page_empty import EmptyPage
from .page_reader import ReaderPage


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
    page_bookshelf = None
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

        print(page, self.page_bookshelf)
        print(on_page_reader, on_page_empty, on_page_bookshelf)

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
            added = 0
            for f in files:
                path = f.get_path()
                if not path:
                    continue
                self.page_bookshelf.books.append(
                    {"path": path, "title": Path(path).stem})
                added += 1
            if added:
                self.page_bookshelf.save_books(self.page_bookshelf.books)
                self.page_bookshelf.refresh_shelf()

        dlg.open_multiple(self, None, _done)
