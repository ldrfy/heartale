"""阅读页面。"""
# pylint: disable=too-many-lines

import copy
import shutil
import subprocess
import threading
import time
import traceback
from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity import LibraryDB
from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from ..entity.time_read import TIME_READ_WAY_LISTEN, TIME_READ_WAY_READ
from ..servers import Server
from ..servers.legado import LegadoServer
from ..servers.txt import TxtServer
from ..tts import THS
from ..tts.cache import AudioPrefetchSlot
from ..tts.read_flow import (build_intro_texts,
                             ensure_next_chapter_prefetched_for_text,
                             get_next_intro_text, get_next_tts_text,
                             get_start_read_text)
from ..tts.server_android import TtsSA
from ..utils.debug import get_logger
from ..widgets.pg_tag_view import ParagraphTagController

READER_CONFIG_KEY = "reader_page"
READER_DEFAULT_CONFIG = {
    "font_size": 14,
    "line_space": 8,
    "paragraph_space": 24,
}


@Gtk.Template(resource_path="/cool/ldr/heartale/reader_page.ui")
# Gtk.Template 子组件和运行时状态较多，这里保留集中管理。
# pylint: disable=too-many-instance-attributes
class ReaderPage(Adw.NavigationPage):
    """展示阅读视图的导航页面。"""
    __gtype_name__ = "ReaderPage"

    btn_prev_chap: Gtk.Button = Gtk.Template.Child()
    btn_next_chap: Gtk.Button = Gtk.Template.Child()

    # These IDs must match the ones defined in the .ui files
    title: Adw.WindowTitle = Gtk.Template.Child()
    gtv_text: Gtk.TextView = Gtk.Template.Child()
    gsw_text: Gtk.ScrolledWindow = Gtk.Template.Child()

    toc: Gtk.ListView = Gtk.Template.Child()
    gse_toc: Gtk.SearchEntry = Gtk.Template.Child()
    btn_show_search: Gtk.ToggleButton = Gtk.Template.Child()

    stack: Adw.ViewStack = Gtk.Template.Child()

    spinner_sync: Gtk.Spinner = Gtk.Template.Child()
    gs_tts_loading: Gtk.Spinner = Gtk.Template.Child()
    gb_tts_start: Gtk.Button = Gtk.Template.Child()

    aos_reader: Adw.OverlaySplitView = Gtk.Template.Child()
    page_error: Adw.StatusPage = Gtk.Template.Child()
    page_loading: Adw.StatusPage = Gtk.Template.Child()

    ga_f: Gtk.Adjustment = Gtk.Template.Child()
    ga_l: Gtk.Adjustment = Gtk.Template.Child()
    ga_p: Gtk.Adjustment = Gtk.Template.Child()
    glb_chap_txt_n: Gtk.Label = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, **kwargs):
        super().__init__(**kwargs)

        self._nav = nav
        self.t = 0
        self._toc_sel: Gtk.SingleSelection = None
        self.chap_ns = []

        self._search_debounce_id = 0

        self._server: Server = None
        self.tts: THS = None

        self._build_factory()

        self.ptc = ParagraphTagController(self.gtv_text, self.gsw_text)
        self.ptc.set_on_paragraph_click(self._on_click_paragraph)
        self.ptc.set_on_visible_paragraph_changed(self._set_read_jd)

        self._tts_thread: threading.Thread = None
        self._tts_stop_event = threading.Event()
        self._tts_proc: subprocess.Popen = None
        self._tts_proc_lock = threading.Lock()
        self._tts_book_md5 = None
        self._on_tts_state_changed = None
        self._tts_prefetch_slot: AudioPrefetchSlot | None = None

        self._reader_config = dict(READER_DEFAULT_CONFIG)
        self._suspend_reader_config_save = False

    def clear_data(self):
        """清空当前阅读数据并显示加载页。"""
        self._server = None
        self._toc_sel = None
        self.chap_ns = []
        self.ptc.clear()
        self.stack.set_visible_child(self.page_loading)

    def set_data(self, book: Book):
        """在后台加载书籍数据并更新界面。"""
        if self._tts_thread and self._tts_thread.is_alive():
            if self._tts_book_md5 != book.md5:
                self._stop_tts_playback()

        if self._server and self._server.book and self._server.book.md5 == book.md5:
            self._restore_current_book_view()
            return

        self.t = time.time()
        self._search_debounce_id = 0

        self.btn_prev_chap.set_sensitive(True)
        self.btn_next_chap.set_sensitive(True)
        self._load_reader_settings()
        self._on_search_toc_stop()

        self.title.set_title(book.name or "")
        self.title.set_subtitle(book.get_jd_str())

        self.clear_data()

        def update_ui(_b: Book, err: Exception):
            """在主线程处理后台加载错误。"""
            if _b.md5 != self._server.book.md5:
                get_logger().info("Book switched, ignoring error display")
                return False
            self.show_error(
                _(
                    "Unable to open this book or its table of contents."
                    "\n{title}: {path}"
                    "\n\nTry again or go back:\n{error}"
                ).format(title=_b.name, path=_b.get_path(), error=err)
            )
            return False

        def worker(_book: Book):
            try:
                self.tts = TtsSA()

                db = LibraryDB()
                book = db.get_book_by_md5(_book.md5)
                db.close()

                self._server = self._get_server(book.fmt)
                self._server.initialize(book)

                if time.time() - self.t < 0.5:
                    time.sleep(0.5 - (time.time() - self.t))
                GLib.idle_add(self._on_data_ready, _book,
                              priority=GLib.PRIORITY_DEFAULT)
            except Exception as e:  # pylint: disable=broad-except
                s = f"Failed to load book: {e}\n{traceback.format_exc()}"
                get_logger().error(s)
                if time.time() - self.t < 0.5:
                    time.sleep(0.5 - (time.time() - self.t))
                GLib.idle_add(update_ui, _book, s,
                              priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, args=(book,), daemon=True).start()

    def _restore_current_book_view(self):
        """复用当前已加载书籍的内存状态刷新界面。"""
        if not self._server or not self._server.book:
            return

        self.btn_prev_chap.set_sensitive(True)
        self.btn_next_chap.set_sensitive(True)
        self._load_reader_settings()
        self._on_search_toc_stop()

        self.title.set_title(self._server.book.name or "")
        self.title.set_subtitle(self._server.book.get_jd_str())
        self.stack.set_visible_child(self.aos_reader)
        self._apply_search()

        if self._server.bd:
            self.ptc.set_paragraphs(self._server.bd.chap_txts)
            self.ptc.scroll_to_paragraph(self._server.bd.chap_txt_n)
            self.ptc.highlight_paragraph(self._server.bd.chap_txt_n)
            self._update_chap_txt_progress_label(
                self._server.bd.chap_txt_n,
                len(self._server.bd.chap_txts),
            )

        self._locate_toc(self._server.get_chap_n())

    def refresh_current_read_position(self):
        """按当前内存中的阅读进度刷新正文高亮和滚动位置。"""
        if not self._server or not self._server.bd:
            return

        idx = self._server.bd.chap_txt_n
        total = len(self._server.bd.chap_txts)
        if total <= 0:
            return

        idx = max(0, min(idx, total - 1))
        self.ptc.highlight_paragraph(idx, True)
        self._update_chap_txt_progress_label(idx, total)
        self._locate_toc(self._server.get_chap_n())

    def _get_server(self, fmt: str):

        if fmt == BOOK_FMT_LEGADO:
            return LegadoServer()
        if fmt == BOOK_FMT_TXT:
            return TxtServer()

        raise ValueError(f"Unsupported book format {fmt}")

    def _locate_toc(self, chap_n: int):
        """在目录中定位并选中指定章节。"""
        if not self._toc_sel:
            return
        self._toc_sel.set_selected(chap_n)
        self.toc.scroll_to(chap_n, Gtk.ListScrollFlags.FOCUS,
                           Gtk.ScrollInfo())

    def _on_data_ready(self, _b: Book):
        """在主线程绑定目录和章节正文。"""

        if _b.md5 != self._server.book.md5:
            get_logger().info("Book switched, ignoring error display")
            return False

        self.stack.set_visible_child(self.aos_reader)

        self._apply_search()

        self.set_chap_text()

        def sel_chap_name():
            """在目录中选中当前章节。"""
            if not self._server:
                return False
            self._locate_toc(self._server.get_chap_n())
            return False

        GLib.timeout_add(500, sel_chap_name)

        return False

    def show_error(self, des=None):
        """显示错误页。"""
        if des is None:
            des = _(
                "Unable to open this book or its table of contents. Please try again or go back.")
        self.stack.set_visible_child(self.page_error)
        self.page_error.set_description(des)

    def set_chap_text(self, _chap_n=-1):
        """加载并显示指定章节内容。

        Args:
            _chap_n (int, optional): 章节索引. Defaults to -1.
        """

        self.btn_prev_chap.set_sensitive(False)
        self.btn_next_chap.set_sensitive(False)

        self.spinner_sync.start()

        def _ui_update(chap_name):
            self.title.set_subtitle(
                f"{chap_name} ({self._server.book.chap_n}/{self._server.book.chap_all})")

            self.ptc.set_paragraphs(self._server.bd.chap_txts)
            self.ptc.scroll_to_paragraph(self._server.bd.chap_txt_n)
            self.ptc.highlight_paragraph(self._server.bd.chap_txt_n)
            self.spinner_sync.stop()
            self._update_chap_txt_progress_label(
                self._server.bd.chap_txt_n,
                len(self._server.bd.chap_txts),
            )

            self.btn_prev_chap.set_sensitive(True)
            self.btn_next_chap.set_sensitive(True)

        def worker(chap_n):
            if chap_n > 0:
                # Skip updates during the initial load
                self._server.save_read_progress(chap_n, 0)

            chap_name = self._server.get_chap_name(chap_n)

            self._server.bd.update_chap_txts(
                self._server.load_chap_txt(chap_n),
                self._server.book.chap_txt_pos)
            self._server.prefetch_next_chap_txt(chap_n)

            GLib.idle_add(_ui_update, chap_name,
                          priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, args=(_chap_n,), daemon=True).start()

    def get_current_text(self, selection_only: bool = True) -> str:
        """获取当前选中文本或整章正文。

        Args:
            selection_only (bool, optional): 是否优先返回选中文本. Defaults to True.

        Returns:
            str: 提取出的文本
        """
        buf = self.gtv_text.get_buffer()
        if selection_only and buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            return buf.get_text(start, end, False)
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, False)

    def _build_factory(self):
        """初始化目录列表项工厂。"""
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
            self._on_toc_chapter_activated(int(position))

        self.toc.connect("activate", on_activate)

    def _on_toc_chapter_activated(self, i: int):
        """处理目录中章节被激活后的切换逻辑。"""
        try:
            self._stop_tts_playback()
            self.set_chap_text(self.chap_ns[i])
            # Optionally update the title/subtitle
        except Exception as e:  # pylint: disable=broad-except
            get_logger().error("Failed to switch chapter: %s", e)
            self.show_error(
                _("Failed to switch chapter: {error}").format(error=e))

    def _on_click_paragraph(self, idx: int, *_args):
        """处理正文段落点击事件。

        Args:
            idx (int): 段落索引
        """
        self._set_read_jd(idx, False)

        self.ptc.highlight_paragraph(idx)
        if self._tts_thread and self._tts_thread.is_alive():
            self._restart_read_aloud_from(idx)

    def _set_read_jd(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        idx,
        add=True,
        save_progress: bool = True,
        way: int = TIME_READ_WAY_READ,
        seconds_override: float | None = None,
    ):
        """按当前段落索引更新阅读进度

        Args:
            idx (int): 段落索引
        """
        if not self._server or not self._server.bd:
            return

        if self._server.bd.chap_txt_n > idx and add:
            # Auto-scrolling to the previous position keeps firing for a few seconds
            # This prevents saving progress when the user scrolls backwards
            return
        if add and save_progress and self._tts_thread and self._tts_thread.is_alive():
            # Ignore auto-scroll callbacks during TTS to avoid duplicate timing records.
            return

        server = self._server

        def worker():
            if not server or not server.bd:
                return

            chap_txts = server.bd.chap_txts
            if not chap_txts:
                return

            safe_idx = max(0, min(int(idx), len(chap_txts) - 1))
            GLib.idle_add(
                self._update_chap_txt_progress_label,
                safe_idx,
                len(chap_txts),
                priority=GLib.PRIORITY_DEFAULT,
            )
            if server is not self._server:
                return

            server.set_chap_txt_n(safe_idx)
            GLib.idle_add(self._emit_tts_state, self.is_read_aloud_active(),
                          priority=GLib.PRIORITY_DEFAULT)
            if save_progress:
                server.save_read_progress(
                    server.get_chap_n(),
                    server.get_chap_txt_pos(),
                    way=way,
                    seconds_override=seconds_override,
                )

        threading.Thread(target=worker, daemon=True).start()

    @Gtk.Template.Callback()
    def _on_read_aloud(self, *_args):
        if not self.tts:
            self.get_root().toast_msg(_("TTS is not available yet."))
            return
        self.tts.reload_config()
        if not shutil.which("paplay"):
            self.get_root().toast_msg(_("paplay is not installed."))
            return
        if self._tts_thread and self._tts_thread.is_alive():
            self.get_root().toast_msg(_("Already reading aloud."))
            return

        chap_txts = self._server.bd.chap_txts
        start_idx = max(0, min(self._server.bd.chap_txt_n, len(chap_txts) - 1))
        if not chap_txts:
            self.get_root().toast_msg(_("No text to read aloud."))
            return

        self._start_read_aloud_from(start_idx)

    def _start_read_aloud_from(self, start_idx: int):  # pylint: disable=too-many-statements
        """从指定段落开始朗读当前章节

        Args:
            start_idx (int): 起始段落索引
        """
        chap_txts = self._server.bd.chap_txts
        start_idx = max(0, min(start_idx, len(chap_txts) - 1))
        if self._tts_prefetch_slot is None:
            self._tts_prefetch_slot = AudioPrefetchSlot(self.tts)

        self.gb_tts_start.set_visible(False)
        self.gs_tts_loading.set_visible(True)
        self.gs_tts_loading.start()
        self._emit_tts_state(True)
        self._tts_book_md5 = self._server.book.md5

        self._tts_stop_event.clear()

        def worker():  # pylint: disable=too-many-branches,too-many-statements
            auto_next_chapter = False
            playback_failed = False
            try:
                first_downloaded = False
                intro_texts = build_intro_texts(self._server)
                start_text = get_start_read_text(self._server, chap_txts, start_idx)
                if start_text and self._tts_prefetch_slot is not None:
                    self._tts_prefetch_slot.prefetch(start_text)

                for intro_idx, intro_text in enumerate(intro_texts):
                    if self._tts_stop_event.is_set():
                        break
                    if not intro_text:
                        continue

                    audio_path = self._take_tts_audio(intro_text)
                    if not audio_path:
                        playback_failed = True
                        GLib.idle_add(
                            self._toast_msg_safe,
                            _("Read aloud failed. Remote TTS service may be unavailable."),
                            priority=GLib.PRIORITY_DEFAULT,
                        )
                        break

                    if not first_downloaded:
                        first_downloaded = True
                        GLib.idle_add(self._set_tts_loading, False,
                                      priority=GLib.PRIORITY_DEFAULT)

                    next_text = get_next_intro_text(
                        intro_texts, intro_idx, start_idx, chap_txts
                    )
                    self._schedule_tts_prefetch(next_text)

                    try:
                        played_ok = self._play_audio(audio_path)
                    finally:
                        self._release_tts_audio(audio_path)
                    if not played_ok:
                        playback_failed = not self._tts_stop_event.is_set()
                        break

                if self._tts_stop_event.is_set() or playback_failed:
                    return

                for idx in range(start_idx, len(chap_txts)):
                    if self._tts_stop_event.is_set():
                        break

                    text = (chap_txts[idx] or "").strip()
                    if not text:
                        continue

                    audio_path = self._take_tts_audio(text)
                    if not audio_path:
                        playback_failed = True
                        GLib.idle_add(
                            self._toast_msg_safe,
                            _("Read aloud failed. Remote TTS service may be unavailable."),
                            priority=GLib.PRIORITY_DEFAULT,
                        )
                        break

                    self._schedule_tts_prefetch(
                        get_next_tts_text(self._server, idx, chap_txts)
                    )

                    if not first_downloaded:
                        first_downloaded = True
                        GLib.idle_add(self._set_tts_loading, False,
                                      priority=GLib.PRIORITY_DEFAULT)

                    self._server.set_chap_txt_n(idx)
                    GLib.idle_add(self._emit_tts_state, True,
                                  priority=GLib.PRIORITY_DEFAULT)
                    if self._can_update_reader_ui_for_tts():
                        GLib.idle_add(self.ptc.highlight_paragraph, idx, True,
                                      priority=GLib.PRIORITY_DEFAULT)
                        # Keep UI position in sync, but save timing after audio playback.
                        self._set_read_jd(idx, False, save_progress=False)

                    play_start = time.time()
                    try:
                        played_ok = self._play_audio(audio_path)
                    finally:
                        self._release_tts_audio(audio_path)
                    play_seconds = max(0.0, time.time() - play_start)
                    if play_seconds > 0:
                        self._set_read_jd(
                            idx,
                            False,
                            save_progress=True,
                            way=TIME_READ_WAY_LISTEN,
                            seconds_override=play_seconds,
                        )

                    if not played_ok:
                        playback_failed = not self._tts_stop_event.is_set()
                        break

                if not self._tts_stop_event.is_set() and not playback_failed:
                    auto_next_chapter = True
            except Exception as e:  # pylint: disable=broad-except
                get_logger().error("TTS playback failed: %s", e)
                GLib.idle_add(self._toast_msg_safe,
                              _("Read aloud failed. Check TTS settings or server status."),
                              priority=GLib.PRIORITY_DEFAULT)
            finally:
                if not auto_next_chapter:
                    self._clear_prefetched_tts_audio()
                if auto_next_chapter:
                    GLib.idle_add(self._auto_next_chapter_for_tts,
                                  priority=GLib.PRIORITY_DEFAULT)
                GLib.idle_add(self._set_tts_loading, False,
                              priority=GLib.PRIORITY_DEFAULT)
                GLib.idle_add(self._emit_tts_state, False,
                              priority=GLib.PRIORITY_DEFAULT)
                self._tts_book_md5 = None

        self._tts_thread = threading.Thread(target=worker, daemon=True)
        self._tts_thread.start()

    def _restart_read_aloud_from(self, idx: int):
        self._stop_tts_playback()

        def wait_and_restart():
            if self._tts_thread and self._tts_thread.is_alive():
                return True
            self._start_read_aloud_from(idx)
            return False

        GLib.timeout_add(80, wait_and_restart)

    def _set_tts_loading(self, loading: bool):
        if loading:
            self.gb_tts_start.set_visible(False)
            self.gs_tts_loading.set_visible(True)
            self.gs_tts_loading.start()
        else:
            self.gs_tts_loading.stop()
            self.gs_tts_loading.set_visible(False)
            self.gb_tts_start.set_visible(True)
        return False

    def _stop_tts_playback(self):
        """停止当前 TTS 播放并清理预取状态"""
        self._tts_stop_event.set()
        with self._tts_proc_lock:
            if self._tts_proc and self._tts_proc.poll() is None:
                self._tts_proc.terminate()
        self._tts_proc = None
        self._tts_book_md5 = None
        self._clear_prefetched_tts_audio()
        GLib.idle_add(self._emit_tts_state, False,
                      priority=GLib.PRIORITY_DEFAULT)

    def _play_audio(self, audio_path):
        """播放单个音频文件直到结束或被中断

        Args:
            audio_path (Path | str): 音频文件路径

        Returns:
            bool: 是否播放成功结束
        """
        with subprocess.Popen(["paplay", str(audio_path)]) as proc:
            with self._tts_proc_lock:
                self._tts_proc = proc

            while True:
                if self._tts_stop_event.is_set():
                    with self._tts_proc_lock:
                        if self._tts_proc and self._tts_proc.poll() is None:
                            self._tts_proc.terminate()
                        self._tts_proc = None
                    return False

                with self._tts_proc_lock:
                    if not self._tts_proc:
                        return False
                    code = self._tts_proc.poll()

                if code is not None:
                    with self._tts_proc_lock:
                        self._tts_proc = None
                    return code == 0
                time.sleep(0.1)

    def _prefetch_tts_audio(self, text: str):
        """后台预取下一条 TTS 音频

        Args:
            text (str): 待预取文本
        """
        try:
            text = (text or "").strip()
            if text:
                ensure_next_chapter_prefetched_for_text(self._server, text)
                if self._tts_prefetch_slot is not None:
                    self._tts_prefetch_slot.prefetch(text)
        except Exception as e:  # pylint: disable=broad-except
            get_logger().warning("Prefetch TTS failed: %s", e)

    def _take_tts_audio(self, text: str):
        """获取已预取音频，不存在时同步下载

        Args:
            text (str): 待转语音文本

        Returns:
            Path | None: 可直接播放的音频文件路径
        """
        text = (text or "").strip()
        if not text or not self.tts:
            return None
        if self._tts_prefetch_slot is None:
            self._tts_prefetch_slot = AudioPrefetchSlot(self.tts)
        return self._tts_prefetch_slot.take(text)

    def _release_tts_audio(self, audio_path):
        """释放当前音频文件引用

        Args:
            audio_path (Path | str | None): 音频文件路径
        """
        if audio_path and self.tts:
            self.tts.release(audio_path)

    def _clear_prefetched_tts_audio(self):
        """清空并释放预取槽中的音频"""
        if self._tts_prefetch_slot is not None:
            self._tts_prefetch_slot.clear()
            self._tts_prefetch_slot = None

    def _schedule_tts_prefetch(self, text: str | None):
        """启动后台线程预取下一条音频

        Args:
            text (str | None): 待预取文本
        """
        text = (text or "").strip()
        if not text or self._tts_stop_event.is_set():
            return
        threading.Thread(
            target=self._prefetch_tts_audio,
            args=(text,),
            daemon=True,
        ).start()

    def _auto_next_chapter_for_tts(self):
        """当前章节朗读结束后自动切到下一章并继续播放

        Returns:
            bool: 是否继续保留超时回调
        """
        if not self._server:
            return False
        if self._server.book.chap_n + 1 >= len(self._server.chap_names):
            return False

        self._server.book.chap_n += 1
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self.set_chap_text(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())

        def wait_and_restart():
            if self.spinner_sync.get_spinning():
                return True
            self._start_read_aloud_from(0)
            return False

        GLib.timeout_add(80, wait_and_restart)
        return False

    def _can_update_reader_ui_for_tts(self) -> bool:
        if not self._server:
            return False
        try:
            return self._nav.get_visible_page() is self
        except Exception:  # pylint: disable=broad-except
            return False

    def stop_read_aloud(self):
        """停止朗读并重置朗读按钮状态。"""
        self._stop_tts_playback()
        self._set_tts_loading(False)

    def is_read_aloud_active(self) -> bool:
        """返回当前是否仍在朗读中。

        Returns:
            bool: 当前是否仍在朗读中
        """
        return bool(self._tts_thread and self._tts_thread.is_alive())

    def get_read_aloud_status_text(self) -> str:
        """返回当前朗读状态文本。

        Returns:
            str: 停止朗读按钮显示的状态文本
        """
        if not self._server or not self._server.book:
            return _("Stop reading aloud")

        book_name = (self._server.book.name or "").strip()
        chap_name = (self._server.get_chap_name(self._server.get_chap_n()) or "").strip()
        total = len(self._server.bd.chap_txts) if self._server.bd else 0
        current = 0
        if total > 0 and self._server.bd:
            current = max(0, min(self._server.bd.chap_txt_n, total - 1)) + 1

        parts = [_("Stop reading aloud")]
        if book_name:
            parts.append(book_name)
        if chap_name:
            parts.append(chap_name)
        if total > 0:
            parts.append(f"{current}/{total}")
        return " - ".join(parts)

    def get_current_read_summary_text(self) -> str:
        """返回当前阅读位置摘要文本。

        Returns:
            str: 当前阅读摘要
        """
        if not self._server or not self._server.book:
            return ""

        book_name = (self._server.book.name or "").strip()
        chap_name = (self._server.get_chap_name(self._server.get_chap_n()) or "").strip()
        total = len(self._server.bd.chap_txts) if self._server.bd else 0
        current = 0
        if total > 0 and self._server.bd:
            current = max(0, min(self._server.bd.chap_txt_n, total - 1)) + 1

        parts = []
        if book_name:
            parts.append(book_name)
        if chap_name:
            parts.append(chap_name)
        summary = " - ".join(parts)
        if total > 0:
            return f"{summary} ({current}/{total})" if summary else f"{current}/{total}"
        return summary

    def set_tts_state_changed_callback(self, callback):
        """设置 TTS 播放状态变更回调。

        Args:
            callback (Callable[[bool, str], None]): 状态变更回调函数
        """
        self._on_tts_state_changed = callback

    def _emit_tts_state(self, is_playing: bool):
        if self._on_tts_state_changed:
            self._on_tts_state_changed(is_playing, self.get_read_aloud_status_text())
        return False

    def _toast_msg_safe(self, msg: str):
        root = self.get_root()
        if root and hasattr(root, "toast_msg"):
            root.toast_msg(msg)
        return False

    @Gtk.Template.Callback()
    def _on_cancel_load_book(self, *_args):
        self._nav.pop()  # Return to the bookshelf page

    @Gtk.Template.Callback()
    def _on_retry_load(self, *_args):
        self.set_data(self._server.book)  # Retry loading the current book

    @Gtk.Template.Callback()
    def _on_next_chap(self, *_args):
        self._stop_tts_playback()
        if self._server.book.chap_n + 1 >= len(self._server.chap_names):
            self.get_root().toast_msg(_("You have reached the last chapter."))
            return
        self._server.book.chap_n += 1
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self._on_toc_chapter_activated(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_last_chap(self, *_args):
        self._stop_tts_playback()
        if self._server.book.chap_n - 1 <= 0:
            self.get_root().toast_msg(_("You are already at the first chapter."))
            return
        self._server.book.chap_n -= 1
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self._on_toc_chapter_activated(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_fontsize_changed(self, b, persist: bool = True) -> None:
        """调整字体大小

        Args:
            b (Adw.SpinRow | int | float): 控件对象或目标值
            persist (bool, optional): 是否持久化保存. Defaults to True.
        """
        if isinstance(b, Adw.SpinRow):
            v = b.get_value()
        else:
            v = b
        v = self._clamp_setting(v, self.ga_f)
        self.ptc.set_font_size_pt(v)
        if persist and not self._suspend_reader_config_save:
            self._save_reader_setting("font_size", v)

    @Gtk.Template.Callback()
    def _on_paragraph_space_changed(self, b, persist: bool = True) -> None:
        """调整段间距

        Args:
            b (Adw.SpinRow | int | float): 控件对象或目标值
            persist (bool, optional): 是否持久化保存. Defaults to True.
        """
        if isinstance(b, Adw.SpinRow):
            v = b.get_value()
        else:
            v = b
        v = self._clamp_setting(v, self.ga_p)
        self.ptc.set_paragraph_spacing(0, v)
        if persist and not self._suspend_reader_config_save:
            self._save_reader_setting("paragraph_space", v)

    @Gtk.Template.Callback()
    def _on_line_space_changed(self, b, persist: bool = True) -> None:
        """调整行间距

        Args:
            b (Adw.SpinRow | int | float): 控件对象或目标值
            persist (bool, optional): 是否持久化保存. Defaults to True.
        """
        if isinstance(b, Adw.SpinRow):
            v = b.get_value()
        else:
            v = b
        v = self._clamp_setting(v, self.ga_l)
        self.ptc.set_line_spacing(v)
        if persist and not self._suspend_reader_config_save:
            self._save_reader_setting("line_space", v)

    @Gtk.Template.Callback()
    def _on_click_title(self, *_args) -> None:
        """将目录滚动到当前章节。"""
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_search_toc_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
        self._search_debounce_id = GLib.timeout_add(500, self._apply_search,
                                                    entry.get_text().strip())

    @Gtk.Template.Callback()
    def _on_search_toc_stop(self, *_) -> None:
        self.gse_toc.set_text("")
        self.btn_show_search.set_active(False)

        if not self._server:
            return

        self._apply_search()

    def _apply_search(self, kw_=""):

        def update_ui():
            self.toc.set_model(self._toc_sel)
            return False

        def worker(kw):
            self._search_debounce_id = 0
            kw = kw.strip()
            if kw:
                self.chap_ns = []
                chap_names = []
                for i, name in enumerate(self._server.chap_names):
                    if kw not in name:
                        continue
                    self.chap_ns.append(i)
                    chap_names.append(name)
            else:
                chap_names = copy.deepcopy(self._server.chap_names)
                self.chap_ns = range(len(chap_names))

            self._toc_sel = Gtk.SingleSelection.new(
                Gtk.StringList.new(chap_names))

            GLib.idle_add(update_ui, priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, args=(kw_,), daemon=True).start()

        return False

    @Gtk.Template.Callback()
    def _on_show_search_toc(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            GLib.idle_add(self.gse_toc.grab_focus)

    @Gtk.Template.Callback()
    def _on_set_default(self, *_args) -> None:
        """恢复默认阅读设置。"""
        self._apply_reader_settings(READER_DEFAULT_CONFIG, persist=True)

    def _clamp_setting(self, value, adjustment: Gtk.Adjustment) -> int:
        try:
            v = int(round(float(value)))
        except (TypeError, ValueError):
            v = int(round(float(adjustment.get_value())))
        lower = int(round(adjustment.get_lower()))
        upper = int(round(adjustment.get_upper()))
        return max(lower, min(upper, v))

    def _normalize_reader_settings(self, raw) -> dict:
        cfg = dict(READER_DEFAULT_CONFIG)
        if isinstance(raw, dict):
            cfg.update(raw)
        cfg["font_size"] = self._clamp_setting(cfg["font_size"], self.ga_f)
        cfg["line_space"] = self._clamp_setting(cfg["line_space"], self.ga_l)
        cfg["paragraph_space"] = self._clamp_setting(
            cfg["paragraph_space"], self.ga_p)
        return cfg

    def _load_reader_settings(self):
        cfg = dict(READER_DEFAULT_CONFIG)
        try:
            db = LibraryDB()
            cfg = self._normalize_reader_settings(
                db.get_config(READER_CONFIG_KEY, READER_DEFAULT_CONFIG))
            db.close()
        except Exception as e:  # pylint: disable=broad-except
            get_logger().warning("Failed to load reader settings: %s", e)
            cfg = self._normalize_reader_settings(READER_DEFAULT_CONFIG)
        self._apply_reader_settings(cfg, persist=False)

    def _apply_reader_settings(self, cfg: dict, persist: bool):
        cfg = self._normalize_reader_settings(cfg)
        self._suspend_reader_config_save = True
        try:
            self.ga_f.set_value(cfg["font_size"])
            self.ga_l.set_value(cfg["line_space"])
            self.ga_p.set_value(cfg["paragraph_space"])
            self._on_fontsize_changed(cfg["font_size"], persist=False)
            self._on_line_space_changed(cfg["line_space"], persist=False)
            self._on_paragraph_space_changed(
                cfg["paragraph_space"], persist=False)
        finally:
            self._suspend_reader_config_save = False
        self._reader_config = dict(cfg)
        if persist:
            self._save_reader_settings()

    def _save_reader_setting(self, key: str, value: int):
        if self._reader_config.get(key) == value:
            return
        self._reader_config[key] = value
        self._save_reader_settings()

    def _save_reader_settings(self):
        try:
            db = LibraryDB()
            db.set_config(READER_CONFIG_KEY, self._reader_config)
            db.close()
        except Exception as e:  # pylint: disable=broad-except
            get_logger().warning("Failed to save reader settings: %s", e)

    def _update_chap_txt_progress_label(self, idx: int, total: int):
        if total <= 0:
            self.glb_chap_txt_n.set_text("")
            return False
        self.glb_chap_txt_n.set_text(f"{idx + 1}/{total}")
        return False
