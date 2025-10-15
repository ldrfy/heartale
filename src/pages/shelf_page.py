# -*- coding: utf-8 -*-

import gi
from gi.repository import Adw, Gio, Gtk

from ..entity import LibraryDB
from ..entity.book import BookObject

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


@Gtk.Template(resource_path="/cool/ldr/heartale/shelf_page.ui")
class ShelfPage(Adw.NavigationPage):
    __gtype_name__ = "ShelfPage"

    list: Gtk.ListView = Gtk.Template.Child()
    stack: Gtk.Stack = Gtk.Template.Child()
    scroller: Gtk.ScrolledWindow = Gtk.Template.Child()
    empty: Adw.StatusPage = Gtk.Template.Child()
    btn_import: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._factory = self._build_factory()

    def set_model(self, liststore):
        # liststore 应为 Gio.ListStore(BookObject)
        selection = Gtk.SingleSelection.new(liststore)
        self.list.set_model(selection)
        self.list.set_factory(self._factory)
        if liststore.get_n_items() > 0:
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
