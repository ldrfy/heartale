# -*- coding: utf-8 -*-

from pathlib import Path

import gi
from gi.repository import Adw, Gio, GLib, Gtk

from .entity import LibraryDB
from .entity.book import BookObject
from .entity.utils import path2book
from .pages.reader_page import ReaderPage
from .pages.shelf_page import ShelfPage

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


@Gtk.Template(resource_path="/cool/ldr/heartale/window.ui")
class HeartaleWindow(Adw.ApplicationWindow):
    __gtype_name__ = "HeartaleWindow"

    nav: Adw.NavigationView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._books: Gio.ListStore = Gio.ListStore.new(BookObject)
        self._reader_page = ReaderPage()
        self._shelf_page = ShelfPage()

        self.nav.add(self._shelf_page)
        self.nav.add(self._reader_page)

        self._install_actions()
        self._wire_events()
        self._bootstrap_route()

    def _install_actions(self):
        act_import = Gio.SimpleAction.new("import-books", None)
        act_import.connect("activate", self.on_import_books)
        self.add_action(act_import)

        act_toggle_sidebar = Gio.SimpleAction.new_stateful(
            "toggle-sidebar",
            None,
            GLib.Variant("b", True),
        )
        act_toggle_sidebar.connect("activate", self.on_toggle_sidebar)
        self.add_action(act_toggle_sidebar)

        act_read_aloud = Gio.SimpleAction.new("read-aloud", None)
        act_read_aloud.connect("activate", self.on_read_aloud)
        self.add_action(act_read_aloud)

    def _wire_events(self):

        db = LibraryDB()
        for b in db.iter_books():
            self._books.append(BookObject.from_dataclass(b))
        db.close()
        self._shelf_page.set_model(self._books)
        self._shelf_page.list.connect("activate", self.on_shelf_activate)
        self._shelf_page.btn_import.connect(
            "clicked", self._emit_import_clicked)

    def _bootstrap_route(self):
        self.nav.push(self._shelf_page)

    def _emit_import_clicked(self, *_args):
        self.lookup_action("import-books").activate(None)

    def on_import_books(self, _action, _param):

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
                self._shelf_page.show_list()

            if s_error:
                edlg = Adw.MessageDialog.new(
                    self.get_root(), "导入部分失败", s_error)
                edlg.add_response("ok", "确定")
                edlg.set_default_response("ok")
                edlg.set_close_response("ok")
                edlg.present()

        dlg.open_multiple(self, None, _done)

    def on_toggle_sidebar(self, action, _param):
        current = action.get_state().get_boolean()
        new_state = not current
        action.set_state(GLib.Variant("b", new_state))
        self._reader_page.split.set_show_sidebar(new_state)

    def on_read_aloud(self, _action, _param):
        text = self._reader_page.get_current_text(selection_only=True)
        if not text:
            text = self._reader_page.get_current_text(selection_only=False)
        # 这里先打印，后续可替换为实际 TTS
        print("[TTS] 朗读内容：")
        # 为避免控制台刷屏，演示时截断
        print(text[:400])

    def on_shelf_activate(self, listview: Gtk.ListView, position: int):

        selection: Gtk.SingleSelection = listview.get_model()
        bobj: BookObject = selection.get_item(position)

        # 标题与正文
        self._reader_page.title.set_title(bobj.name)
        self._reader_page.title.set_subtitle("第 1 章 · 绪论")

        buf = self._reader_page.text.get_buffer()
        progress = 0 if bobj.txt_all == 0 else int(
            bobj.txt_pos * 100 / bobj.txt_all)
        buf.set_text(
            f"{bobj.name}\n\n"
            f"路径：{bobj.path}\n"
            f"章节数：{bobj.chap_n}\n"
            f"进度：{progress}%（{bobj.txt_pos}/{bobj.txt_all}）\n"
            "这是示例正文……\n"
        )

        toc = Gtk.StringList.new([f"第 {i} 章" for i in range(1, 6)])
        self._reader_page.bind_toc(toc)

        self.nav.push(self._reader_page)
