"""阅读页面"""

import logging
import threading

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity.book import Book
from ..entity.utils import parse_chap_names

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/cool/ldr/heartale/reader_page.ui")
class ReaderPage(Adw.NavigationPage):
    """阅读

    Args:
        Adw (_type_): _description_

    Returns:
        _type_: _description_

    Yields:
        _type_: _description_
    """
    __gtype_name__ = "ReaderPage"

    # 这些 id 必须与 .ui 一致
    title: Adw.WindowTitle = Gtk.Template.Child()
    text: Gtk.TextView = Gtk.Template.Child()
    toc: Gtk.ListView = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()  # 新增绑定
    aos_reader: Adw.OverlaySplitView = Gtk.Template.Child()  # 新增绑定
    page_reader: Adw.StatusPage = Gtk.Template.Child()  # 新增绑定
    page_error: Adw.StatusPage = Gtk.Template.Child()  # 新增绑定
    page_loading: Adw.StatusPage = Gtk.Template.Child()  # 新增绑定


    def __init__(self, nav: Adw.NavigationView, ** kwargs):
        super().__init__(**kwargs)
        # 可选：确保启动即在加载页（也可直接在 .ui 里设 visible-child-name）
        # self.set_state(self.PAGE_LOADING)

        self._nav = nav
        self.chap_names, self.chaps_ps = [], []
        self.chap_content = ""
        self.book: Book | None = None
        self.toggle_sidebar = False

    def set_data(self, book: Book):
        """在子线程读取与解析章节，主线程更新 UI。"""
        print("data set:", book)
        self.show_loading()
        self.title.set_title(book.name or "")

        def worker():
            print("---- worker thread start ----")
            try:
                self.book = book
                with open(book.path, "r", encoding=book.encoding) as f:
                    text = f.read()
                self.chap_names, self.chaps_ps = parse_chap_names(text)
                self.chap_content = self._get_chap_content_by_idx(book.chap_n)

                # 回到主线程更新 UI（非常重要：GTK 只能主线程改）
                GLib.idle_add(
                    self._on_data_ready,
                    priority=GLib.PRIORITY_DEFAULT,
                )
            except Exception as e:  # pylint: disable=broad-except
                # 回到主线程展示错误
                GLib.idle_add(self._on_error, e,
                              priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, daemon=True).start()

    def _get_chap_content_by_idx(self, n: int) -> str:
        with open(self.book.path, "r", encoding=self.book.encoding) as f:
            if n + 1 == len(self.chaps_ps):
                return f.read()[self.chaps_ps[n]:]

            return f.read()[self.chaps_ps[n]: self.chaps_ps[n + 1]]

    def _on_data_ready(self):
        """仅在主线程运行：绑定目录与正文。"""
        print("ReaderPage: data ready, updating UI...")
        self.show_reader()
        print()
        self.title.set_subtitle(f"{self.chap_names[self.book.chap_n]}")
        self.bind_toc(Gtk.StringList.new(self.chap_names))
        self.set_text_content(self._get_chap_content_by_idx(self.book.chap_n))
        return False  # 告诉 GLib.idle_add 只执行一次

    def _on_error(self, err: Exception):
        """仅在主线程运行：统一错误处理。"""
        print(err)
        self.show_error()
        return False

    def show_loading(self) -> None:
        """载入中

        Args:
            desc (str | None, optional): _description_. Defaults to None.
        """
        self.stack.set_visible_child(self.page_loading)

    def show_error(self) -> None:
        """显示错误

        Args:
            message (str, optional): _description_. Defaults to "无法打开本书或目录，请重试或返回。".
        """
        self.stack.set_visible_child(self.page_error)

    def show_reader(self) -> None:
        """显示阅读
        """
        self.stack.set_visible_child(self.page_reader)
        print("---- show reader ----")

    def set_text_content(self, content: str) -> None:
        """_summary_

        Args:
            content (str): _description_
        """
        buf = self.text.get_buffer()
        buf.set_text(content or "")

    # 保留你的实现
    def get_current_text(self, selection_only: bool = True) -> str:
        """_summary_

        Args:
            selection_only (bool, optional): _description_. Defaults to True.

        Returns:
            str: _description_
        """
        buf = self.text.get_buffer()
        if selection_only and buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            return buf.get_text(start, end, False)
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, False)

    def bind_toc(self, string_list: Gtk.StringList):
        """_summary_

        Args:
            string_list (Gtk.StringList): _description_
        """
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


    def _iter_children(self, widget: Gtk.Widget):
        child = widget.get_first_child()
        while child:
            yield child
            child = child.get_next_sibling()

    @Gtk.Template.Callback()
    def _on_read_aloud(self, *_args):
        text = self.get_current_text(selection_only=True)
        if not text:
            text = self.get_current_text(selection_only=False)
        # 这里先打印，后续可替换为实际 TTS
        print("[TTS] 朗读内容：")
        # 为避免控制台刷屏，演示时截断
        print(text[:400])

    @Gtk.Template.Callback()
    def _on_cancel_load_book(self, *_args):
        self._nav.pop()  # 返回书架页

    @Gtk.Template.Callback()
    def _on_retry_load(self, *_args):
        self.set_data(self.book)  # 重试加载当前书

    @Gtk.Template.Callback()
    def _on_toggle_sidebar(self, *_args):
        self.aos_reader.set_show_sidebar(self.toggle_sidebar)
        self.toggle_sidebar = not self.toggle_sidebar
