# window.py
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk

from .page_bookshelf import BookshelfPage
from .page_empty import EmptyPage


@Gtk.Template(resource_path="/cool/ldr/heartale/window.ui")
class HeartaleWindow(Adw.ApplicationWindow):
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

    # 关键子控件引用
    flow_books: Gtk.FlowBox | None = None
    nav_list: Gtk.ListBox | None = None
    text_view: Gtk.TextView | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 创建页面实例（每页本身是 Template 子类）

        self.page_empty = EmptyPage(self.nav)
        self.page_bookshelf = BookshelfPage(self.nav)

        # 拿到子控件引用
        self.flow_books = self.page_bookshelf.flow_books

        # FlowBox 选择变化影响删除键
        self.flow_books.connect(
            "selected-children-changed", self._on_flow_selection_changed)

        # 放入导航栈
        self.nav.push(self.page_empty)

        # 顶部按钮行为
        self.btn_back.connect("clicked", self._on_back_clicked)
        self.btn_import.connect(
            "clicked", self.page_bookshelf.on_import_clicked)
        self.btn_delete.connect(
            "clicked", self.page_bookshelf.on_delete_selected_clicked)
        self.btn_play.connect("clicked", self.on_play_clicked)

        # 页可见变化
        self.nav.connect("notify::visible-page", self._on_visible_page_changed)

        # 初始同步
        self._sync_header()


    def _on_back_clicked(self, *_):
        page = self.nav.get_visible_page()
        if page and page.get_can_pop():
            self.nav.pop()

    def _on_visible_page_changed(self, *_):
        self._sync_header()

    # ---------- Header 同步 ----------
    def _sync_header(self):
        page = self.nav.get_visible_page()
        if not page:
            return
        is_root = not page.get_can_pop()
        on_bookshelf0 = page is self.page_empty
        on_bookshelf = page is self.page_bookshelf

        self.btn_back.set_visible(not is_root)
        self.btn_import.set_visible(on_bookshelf0 or on_bookshelf)
        self.btn_delete.set_visible(on_bookshelf)

        # 删除键敏感态
        if on_bookshelf:
            count = len(self.flow_books.get_selected_children())
            self.btn_delete.set_sensitive(count > 0)
        else:
            self.btn_delete.set_sensitive(False)

    def _on_flow_selection_changed(self, flowbox: Gtk.FlowBox):
        self.btn_delete.set_sensitive(len(flowbox.get_selected_children()) > 0)


    def on_delete_selected_clicked(self, _btn):
        print("TODO: Delete selected items")

    def on_play_clicked(self, _btn):
        print("TODO: Play / Read")
