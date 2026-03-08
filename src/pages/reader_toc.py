"""阅读页目录相关逻辑。"""

import threading
from gettext import gettext as _

from gi.repository import GLib, Gtk  # type: ignore

from ..utils.debug import get_logger


class ReaderTocMixin:
    """封装阅读页的目录列表、定位与搜索逻辑。"""

    def build_toc(self) -> None:
        """初始化目录组件。"""
        self._build_factory()

    def apply_toc_search(self, keyword: str = "") -> bool:
        """按关键字刷新目录列表。

        Args:
            keyword (str, optional): 目录搜索关键字. Defaults to "".

        Returns:
            bool: 是否继续保留延迟回调
        """
        return self._apply_search(keyword)

    def _build_factory(self) -> None:
        """初始化目录列表项工厂。"""
        factory = Gtk.SignalListItemFactory()

        def setup(_factory, list_item):
            label = Gtk.Label(xalign=0.0)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_ellipsize(3)
            list_item.set_child(label)

        def bind(_factory, list_item):
            label: Gtk.Label = list_item.get_child()
            string_object: Gtk.StringObject = list_item.get_item()
            label.set_text(string_object.get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)

        self.toc.set_factory(factory)
        self.toc.connect("activate", self._on_toc_activated)

    def _on_toc_activated(self, _listview, position: int) -> None:
        """响应目录项激活事件。

        Args:
            position (int): 被激活的目录位置
        """
        self._on_toc_chapter_activated(int(position))

    def _locate_toc(self, chap_n: int) -> None:
        """在目录中定位并选中指定章节。

        Args:
            chap_n (int): 章节索引
        """
        if not self._toc_sel:
            return
        chap_count = len(self.chap_ns) if self.chap_ns else 0
        if chap_count <= 0:
            return

        safe_idx = max(0, min(chap_n, chap_count - 1))
        self._toc_sel.set_selected(safe_idx)

        def scroll_selected():
            if not self._toc_sel or self.toc.get_model() is None:
                return False
            self.toc.scroll_to(
                safe_idx,
                Gtk.ListScrollFlags.SELECT | Gtk.ListScrollFlags.FOCUS,
                Gtk.ScrollInfo.new(),
            )
            return False

        GLib.idle_add(scroll_selected, priority=GLib.PRIORITY_DEFAULT)

    def _on_toc_chapter_activated(self, idx: int) -> None:
        """处理目录中章节被激活后的切换逻辑。

        Args:
            idx (int): 当前目录中的位置索引
        """
        try:
            self._stop_tts_playback()
            self.set_chap_text(self.chap_ns[idx])
        except Exception as exc:  # pylint: disable=broad-except
            get_logger().error("Failed to switch chapter: %s", exc)
            self.show_error(
                _("Failed to switch chapter: {error}").format(error=exc)
            )

    def handle_search_toc_changed(self, entry: Gtk.SearchEntry) -> None:
        """响应目录搜索框内容变化。

        Args:
            entry (Gtk.SearchEntry): 目录搜索输入框
        """
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
        self._search_debounce_id = GLib.timeout_add(
            500,
            self._apply_search,
            entry.get_text().strip(),
        )

    def handle_search_toc_stop(self, *_args) -> None:
        """清空目录搜索条件并恢复完整目录。"""
        self.gse_toc.set_text("")
        self.btn_show_search.set_active(False)

        if not self._server:
            return

        self._apply_search()

    def _apply_search(self, keyword: str = ""):
        """按关键字过滤目录并刷新目录列表。

        Args:
            keyword (str, optional): 目录搜索关键字. Defaults to "".

        Returns:
            bool: 是否继续保留延迟回调
        """
        def update_ui(chap_names: list[str], chap_ns: list[int]) -> bool:
            self.chap_ns = chap_ns
            self._toc_sel = Gtk.SingleSelection.new(Gtk.StringList.new(chap_names))
            self.toc.set_model(self._toc_sel)
            return False

        def worker(kw: str) -> None:
            self._search_debounce_id = 0
            chap_names, chap_ns = self._filter_toc_items(kw)
            GLib.idle_add(
                update_ui,
                chap_names,
                chap_ns,
                priority=GLib.PRIORITY_DEFAULT,
            )

        threading.Thread(target=worker, args=(keyword,), daemon=True).start()
        return False

    def _filter_toc_items(self, keyword: str) -> tuple[list[str], list[int]]:
        """按关键字筛选目录项。

        Args:
            keyword (str): 目录搜索关键字

        Returns:
            tuple[list[str], list[int]]: 过滤后的目录名和原始章节索引
        """
        keyword = keyword.strip()
        if not keyword:
            chap_names = list(self._server.chap_names)
            return chap_names, list(range(len(chap_names)))

        chap_names = []
        chap_ns = []
        for idx, name in enumerate(self._server.chap_names):
            if keyword not in name:
                continue
            chap_ns.append(idx)
            chap_names.append(name)
        return chap_names, chap_ns

    def handle_show_search_toc(self, btn: Gtk.ToggleButton) -> None:
        """在显示目录搜索框后将焦点移入输入框。

        Args:
            btn (Gtk.ToggleButton): 搜索切换按钮
        """
        if btn.get_active():
            GLib.idle_add(self.gse_toc.grab_focus)
