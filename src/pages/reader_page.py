"""阅读页面"""

import threading
import time

from gi.repository import Adw, GLib, Gtk

from ..entity import LibraryDB
from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from ..servers import Server
from ..servers.legado import LegadoServer
from ..servers.txt import TxtServer
from ..utils.debug import get_logger
from ..widgets.pg_tag_view import ParagraphTagController


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
    gtv_text: Gtk.TextView = Gtk.Template.Child()
    gsw_text: Gtk.ScrolledWindow = Gtk.Template.Child()

    toc: Gtk.ListView = Gtk.Template.Child()
    gr_toc: Gtk.Revealer = Gtk.Template.Child()
    gse_toc: Gtk.SearchEntry = Gtk.Template.Child()
    btn_show_search: Gtk.ToggleButton = Gtk.Template.Child()
    btn_toggle_sidebar: Gtk.ToggleButton = Gtk.Template.Child()

    stack: Adw.ViewStack = Gtk.Template.Child()

    spinner_sync: Gtk.Spinner = Gtk.Template.Child()

    aos_reader: Adw.OverlaySplitView = Gtk.Template.Child()
    page_error: Adw.StatusPage = Gtk.Template.Child()
    page_loading: Adw.StatusPage = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, ** kwargs):
        super().__init__(**kwargs)
        # 可选：确保启动即在加载页（也可直接在 .ui 里设 visible-child-name）
        # self.set_state(self.PAGE_LOADING)

        self._nav = nav
        self.t = 0
        self._toc_sel: Gtk.SingleSelection = None
        self.chap_ns = []

        self.auto_scroll = True
        self._search_debounce_id = 0

        self._server: Server = None

        self._build_factory()

        self.ptc = ParagraphTagController(self.gtv_text, self.gsw_text)
        self.ptc.set_line_spacing(10)
        self.ptc.set_paragraph_spacing(0, 0)
        self.ptc.set_font_size_pt(14)

        self.ptc.set_on_paragraph_click(self._on_click_paragraph)
        self.ptc.set_on_visible_paragraph_changed(self._set_read_jd)

    def set_data(self, book: Book):
        """在子线程读取与解析章节，主线程更新 UI。

        Args:
            book (Book): _description_
        """
        self._search_debounce_id = 0

        self._server = None
        self._on_search_toc_stop()

        self.t = time.time()
        self.stack.set_visible_child(self.page_loading)

        self.title.set_title(book.name or "")
        pct = 0
        if book.txt_all > 0:
            pct = int(book.txt_pos * 100 / book.txt_all)
        self.title.set_subtitle(
            f"进度 {pct}% ({book.txt_pos}/{book.txt_all})")

        book_md5 = book.md5

        def update_ui(err: Exception):
            """仅在主线程运行：统一错误处理。"""
            self.show_error(f"无法打开本书或目录，请重试或返回。\n{err}")
            return False

        def worker():
            try:

                db = LibraryDB()
                book = db.get_book_by_md5(book_md5)
                db.close()

                self._server = self._get_server(book.fmt)
                self._server.initialize(book)

                if time.time() - self.t < 0.5:
                    time.sleep(0.5 - (time.time() - self.t))
                GLib.idle_add(self._on_data_ready,
                              priority=GLib.PRIORITY_DEFAULT)
            except Exception as e:  # pylint: disable=broad-except
                get_logger().error("加载书籍失败：%s", e)
                # 回到主线程展示错误
                GLib.idle_add(update_ui, e,
                              priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=worker, daemon=True).start()

    def _get_server(self, fmt: str):

        if fmt == BOOK_FMT_LEGADO:
            return LegadoServer()
        if fmt == BOOK_FMT_TXT:
            return TxtServer()

        raise ValueError(f"不支持的书籍类型 {fmt}")

    def _locate_toc(self, chap_n: int):
        """定位到某个章节

        Args:
            chap_n (int): _description_
        """
        self._toc_sel.set_selected(chap_n)
        self.toc.scroll_to(chap_n, Gtk.ListScrollFlags.FOCUS,
                           Gtk.ScrollInfo())

    def _on_data_ready(self):
        """仅在主线程运行：绑定目录与正文。"""

        self.chap_ns = range(len(self._server.chap_names))

        self._toc_sel = Gtk.SingleSelection.new(
            Gtk.StringList.new(self._server.chap_names))
        self.toc.set_model(self._toc_sel)

        self.set_chap_text()

        self.stack.set_visible_child(self.aos_reader)

        def sel_chap_name():
            """选中目录
            """
            self._locate_toc(self._server.get_chap_n())

        def worker():
            # 必须延迟
            time.sleep(0.5)
            GLib.idle_add(sel_chap_name, priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, daemon=True).start()

        return False

    def show_error(self, des="无法打开本书或目录，请重试或返回。"):
        """显示错误

        Args:
            message (str, optional): _description_. Defaults to "无法打开本书或目录，请重试或返回。".
        """
        self.stack.set_visible_child(self.page_error)
        self.page_error.set_description(des)

    def set_chap_text(self, _chap_n=-1):
        """设置文本

        Args:
            chap_n (int): 章节编号
        """

        self.spinner_sync.start()

        def _ui_update(chap_name):

            self.title.set_subtitle(
                f"{chap_name} ({self._server.book.chap_n}/{self._server.book.chap_all})")

            self.auto_scroll = True

            self.ptc.set_paragraphs(self._server.bd.chap_txts)
            self.ptc.scroll_to_paragraph(self._server.bd.chap_txt_n)
            self.ptc.highlight_paragraph(self._server.bd.chap_txt_n)
            self.spinner_sync.stop()

            self.auto_scroll = False

        def worker(chap_n):
            if chap_n > 0:
                # 初始加载不能动
                self._server.save_read_progress(chap_n, 0)

            chap_name = self._server.get_chap_name(chap_n)

            self._server.bd.update_chap_txts(
                self._server.get_chap_txt(chap_n),
                self._server.book.chap_txt_pos)

            GLib.idle_add(_ui_update, chap_name,
                          priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, args=(_chap_n,), daemon=True).start()

    def get_current_text(self, selection_only: bool = True) -> str:
        """当前的文本

        Args:
            selection_only (bool, optional): _description_. Defaults to True.

        Returns:
            str: _description_
        """
        buf = self.gtv_text.get_buffer()
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
            print("激活", position)
            # position 是被激活项的索引
            self._on_toc_chapter_activated(int(position))

        self.toc.connect("activate", on_activate)

    def _on_toc_chapter_activated(self, i: int):
        """用户点击目录中的第 idx 章。"""
        try:
            self.set_chap_text(self.chap_ns[i])
            # 更新标题副标题（可选）
        except Exception as e:  # pylint: disable=broad-except
            get_logger().error("切换章节失败：%s", e)
            self.show_error(f"切换章节失败：{e}")

    def _on_click_paragraph(self, idx: int, *_args):
        """用户点击了段落

        Args:
            idx (int): 段落索引
            tag_name (str): 段落标签名
            start_off (int): 段落起始偏移
            end_off (int): 段落结束偏移
        """
        self._set_read_jd(idx)
        self.ptc.highlight_paragraph(idx)

    def _set_read_jd(self, idx):
        """阅读进度

        Args:
            idx (_type_): _description_
        """

        if self.auto_scroll:
            return

        def worker():
            # 耗时操作放线程
            self._server.set_chap_txt_n(idx)
            self._server.save_read_progress(self._server.get_chap_n(),
                                            self._server.get_chap_txt_pos())
        threading.Thread(target=worker, daemon=True).start()

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
        self.set_data(self._server.book)  # 重试加载当前书

    @Gtk.Template.Callback()
    def _on_toggle_sidebar(self, *_args):
        self.aos_reader.set_show_sidebar(
            not self.btn_toggle_sidebar.get_active())

    @Gtk.Template.Callback()
    def _on_next_chap(self, *_args):
        self._server.book.chap_n += 1
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self._on_toc_chapter_activated(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_last_chap(self, *_args):
        self._server.book.chap_n -= 1
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self._on_toc_chapter_activated(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_fontsize_changed(self, a) -> None:
        """字体

        Args:
            spin (Adw.SpinRow): _description_
            value (_type_): _description_
        """
        v = int(a.get_value())
        self.ptc.set_font_size_pt(v)

    @Gtk.Template.Callback()
    def _on_paragraph_space_changed(self, b) -> None:
        """字体

        Args:
            spin (Adw.SpinRow): _description_
            value (_type_): _description_
        """
        v = int(b.get_value())
        self.ptc.set_paragraph_spacing(v, v)

    @Gtk.Template.Callback()
    def _on_line_space_changed(self, b) -> None:
        """字体

        Args:
            spin (Adw.SpinRow): _description_
            value (_type_): _description_
        """
        v = int(b.get_value())
        self.ptc.set_line_spacing(v)

    @Gtk.Template.Callback()
    def _on_click_title(self, *_args) -> None:
        """字体

        Args:
            spin (Adw.SpinRow): _description_
            value (_type_): _description_
        """
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_search_toc_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
        self._search_debounce_id = GLib.timeout_add(200, self._apply_search,
                                                    entry.get_text().strip())

    @Gtk.Template.Callback()
    def _on_search_toc_stop(self, *_) -> None:
        self.gse_toc.set_text("")
        self.gr_toc.set_reveal_child(False)
        self.btn_show_search.set_active(False)

        if not self._server:
            return

        self._apply_search()

    def _apply_search(self, kw=""):
        if not kw:
            self.toc.set_model(Gtk.SingleSelection.new(
                Gtk.StringList.new(self._server.chap_names)))
            return False

        kw = kw.strip()
        print(kw)
        self._search_debounce_id = 0

        self.chap_ns = []
        chap_names = []
        for i, name in enumerate(self._server.chap_names):
            if kw not in name:
                continue
            self.chap_ns.append(i)
            chap_names.append(name)

        self.toc.set_model(Gtk.SingleSelection.new(
            Gtk.StringList.new(chap_names)))

        return False

    @Gtk.Template.Callback()
    def _on_show_search_toc(self, btn: Gtk.ToggleButton) -> None:
        active = btn.get_active()
        self.gr_toc.set_reveal_child(active)
        if active:
            GLib.idle_add(self.gse_toc.grab_focus)
