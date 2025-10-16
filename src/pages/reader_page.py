"""阅读页面"""

import logging
import threading
import time

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
    stack: Adw.ViewStack = Gtk.Template.Child()

    aos_reader: Adw.OverlaySplitView = Gtk.Template.Child()
    page_error: Adw.StatusPage = Gtk.Template.Child()
    page_loading: Adw.StatusPage = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, ** kwargs):
        super().__init__(**kwargs)
        # 可选：确保启动即在加载页（也可直接在 .ui 里设 visible-child-name）
        # self.set_state(self.PAGE_LOADING)

        self._nav = nav
        self.t = 0
        self._chap_names, self._chaps_ps = [], []
        self.book: Book | None = None
        self.toggle_sidebar = False
        self._build_factory()

    def set_data(self, book: Book):
        """在子线程读取与解析章节，主线程更新 UI。

        Args:
            book (Book): _description_
        """
        self.show_loading()
        self.t = time.time()
        self.title.set_title(book.name or "")
        pct = 0
        if book.txt_all > 0:
            pct = int(book.txt_pos * 100 / book.txt_all)
        self.title.set_subtitle(f"进度 {pct}%")

        def worker():
            try:
                self.book = book

                with open(book.path, "r", encoding=book.encoding) as f:
                    text = f.read()
                self._chap_names, self._chaps_ps = parse_chap_names(text)

                print("------", time.time() - self.t)
                if time.time() - self.t < 0.5:
                    time.sleep(0.5 - (time.time() - self.t))

                # 回到主线程更新 UI（非常重要：GTK 只能主线程改）
                GLib.idle_add(self._on_data_ready,
                              priority=GLib.PRIORITY_DEFAULT)
            except Exception as e:  # pylint: disable=broad-except
                # 回到主线程展示错误
                GLib.idle_add(self._on_error, e,
                              priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, daemon=True).start()

    def _on_data_ready(self):
        """仅在主线程运行：绑定目录与正文。"""

        self.title.set_subtitle(f"{self._chap_names[self.book.chap_n]}")

        cn = Gtk.StringList.new(self._chap_names)
        self.toc.set_model(Gtk.SingleSelection.new(cn))

        self.set_chap_text(self.book.chap_n)

        self.show_reader()

        # 告诉 GLib.idle_add 只执行一次
        return False

    def _on_error(self, err: Exception):
        """仅在主线程运行：统一错误处理。"""
        self.show_error(f"无法打开本书或目录，请重试或返回。\n{err}")
        return False

    def show_loading(self):
        """载入中

        Args:
            desc (str | None, optional): _description_. Defaults to None.
        """
        self.stack.set_visible_child(self.page_loading)

    def show_error(self, des="无法打开本书或目录，请重试或返回。"):
        """显示错误

        Args:
            message (str, optional): _description_. Defaults to "无法打开本书或目录，请重试或返回。".
        """
        self.stack.set_visible_child(self.page_error)
        self.page_error.set_description(des)

    def show_reader(self):
        """显示阅读
        """
        self.stack.set_visible_child(self.aos_reader)

    def set_chap_text(self, chap_n: int):
        """设置文本

        Args:
            chap_n (int): 章节编号
        """
        content = ""
        with open(self.book.path, "r", encoding=self.book.encoding) as f:
            if chap_n + 1 == len(self._chaps_ps):
                content = f.read()[self._chaps_ps[chap_n]:]
                return
            content = f.read()[self._chaps_ps[chap_n]: self._chaps_ps[chap_n + 1]]

        self.text.get_buffer().set_text(content)

    def get_current_text(self, selection_only: bool = True) -> str:
        """当前的文本

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

    def _build_factory(self):
        """初始化模型，仅一次
        """
        factory = Gtk.SignalListItemFactory()

        def setup(_f, li):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            lbl.set_margin_start(12)
            lbl.set_margin_end(12)
            lbl.set_ellipsize(3)
            li.set_child(lbl)

        def bind(_f, li):
            lbl: Gtk.Label = li.get_child()
            sobj: Gtk.StringObject = li.get_item()
            lbl.set_text(sobj.get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)

        self.toc.set_factory(factory)

        def on_activate(_listview, position):
            # position 是被激活项的索引
            self._on_toc_chapter_activated(int(position))

        self.toc.connect("activate", on_activate)

    def _on_toc_chapter_activated(self, chap_n: int):
        """用户点击目录中的第 idx 章。"""
        # 如果你已经把整书文本缓存进内存，直接切片；否则按你现有逻辑读取
        try:
            # 更新正文
            self.set_chap_text(chap_n)
            # 更新标题副标题（可选）
            if 0 <= chap_n < len(self._chap_names):
                self.title.set_subtitle(self._chap_names[chap_n])
            # 记录当前章号（可选）
            if self.book:
                self.book.chap_n = chap_n
        except Exception as e:  # pylint: disable=broad-except
            self.show_error(f"切换章节失败：{e}")

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
