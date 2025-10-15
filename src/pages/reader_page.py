# -*- coding: utf-8 -*-

import logging

import gi
from gi.repository import Adw, Gtk

# 版本声明必须在导入前
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/cool/ldr/heartale/reader_page.ui")
class ReaderPage(Adw.NavigationPage):
    __gtype_name__ = "ReaderPage"

    # 这些 id 必须与 .ui 一致
    title: Adw.WindowTitle = Gtk.Template.Child()
    text: Gtk.TextView = Gtk.Template.Child()
    toc: Gtk.ListView = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()  # 新增绑定

    # 与 <packing name="..."> 对齐
    PAGE_LOADING = "loading"
    PAGE_ERROR = "error"
    PAGE_READER = "reader"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 可选：确保启动即在加载页（也可直接在 .ui 里设 visible-child-name）
        self.set_state(self.PAGE_LOADING)

    # --- 状态切换 ---
    def set_state(self, name: str) -> None:
        try:
            self.stack.set_visible_child_name(name)
        except Exception as e:
            logger.warning("ReaderPage.set_state failed: %r", e, exc_info=True)

    def show_loading(self, desc: str | None = None) -> None:
        if desc:
            loading = self._get_status_page("loading")
            if loading:
                loading.set_description(desc)
        self.set_state(self.PAGE_LOADING)

    def show_error(self, message: str = "无法打开本书或目录，请重试或返回。") -> None:
        error = self._get_status_page("error")
        if error:
            error.set_description(message)
        self.set_state(self.PAGE_ERROR)

    def show_reader(self) -> None:
        self.set_state(self.PAGE_READER)

    # --- 内容更新 ---
    def update_header(self, book_title: str, chapter_title: str | None = None) -> None:
        self.title.set_title(book_title or "")
        self.title.set_subtitle(chapter_title or "")

    def set_text_content(self, content: str) -> None:
        buf = self.text.get_buffer()
        buf.set_text(content or "")

    # 保留你的实现
    def get_current_text(self, selection_only: bool = True) -> str:
        buf = self.text.get_buffer()
        if selection_only and buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            return buf.get_text(start, end, False)
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, False)

    def bind_toc(self, string_list: Gtk.StringList):
        factory = Gtk.SignalListItemFactory()

        def setup(_f, li):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            lbl.set_margin_start(12)
            lbl.set_margin_end(12)
            lbl.set_ellipsize(3)  # Pango.EllipsizeMode.END
            li.set_child(lbl)

        def bind(_f, li):
            lbl: Gtk.Label = li.get_child()
            sobj: Gtk.StringObject = li.get_item()
            lbl.set_text(sobj.get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        self.toc.set_factory(factory)
        self.toc.set_model(Gtk.SingleSelection.new(string_list))

    # --- 小工具 ---
    def _get_status_page(self, widget_id: str) -> Adw.StatusPage | None:
        # 直接通过模板绑定的 stack 去找
        # ViewStack 的可见子页是 widget 本身，非 Page 对象
        for child in self._iter_children(self.stack):
            # 仅匹配我们关心的两个 StatusPage
            if isinstance(child, Adw.StatusPage):
                # 根据 .ui 的 id 判断
                buildable_id = Gtk.Buildable.get_buildable_id(
                    child) if isinstance(child, Gtk.Buildable) else None
                if buildable_id == widget_id:
                    return child
        return None

    def _iter_children(self, widget: Gtk.Widget):
        child = widget.get_first_child()
        while child:
            yield child
            child = child.get_next_sibling()
