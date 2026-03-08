"""阅读页面。"""
# pylint: disable=too-many-lines

import shutil
import subprocess
import threading
import time
from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity.time_read import TIME_READ_WAY_LISTEN, TIME_READ_WAY_READ
from ..servers import Server
from ..tts import THS
from ..tts.cache import AudioPrefetchSlot
from ..tts.read_runner import (TtsReadContext, TtsReadRunnerHooks,
                               run_tts_read_loop)
from ..utils.debug import get_logger
from ..widgets.pg_tag_view import ParagraphTagController
from .reader_session import ReaderSessionMixin
from .reader_settings import READER_DEFAULT_CONFIG, ReaderSettingsMixin
from .reader_toc import ReaderTocMixin


@Gtk.Template(resource_path="/cool/ldr/heartale/reader_page.ui")
# Gtk.Template 子组件和运行时状态较多，这里保留集中管理。
# pylint: disable=too-many-instance-attributes
class ReaderPage(ReaderSessionMixin, ReaderSettingsMixin, ReaderTocMixin, Adw.NavigationPage):
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
    btn_tts_stop: Gtk.Button = Gtk.Template.Child()

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

        self.build_toc()

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

    def _start_read_aloud_from(self, start_idx: int):
        """从指定段落开始朗读当前章节

        Args:
            start_idx (int): 起始段落索引
        """
        chap_txts = self._server.bd.chap_txts
        start_idx = max(0, min(start_idx, len(chap_txts) - 1))
        if self._tts_prefetch_slot is None:
            self._tts_prefetch_slot = AudioPrefetchSlot(self.tts)

        self.gb_tts_start.set_visible(False)
        self.btn_tts_stop.set_visible(True)
        self.gs_tts_loading.set_visible(True)
        self.gs_tts_loading.start()
        self._emit_tts_state(True)
        self._tts_book_md5 = self._server.book.md5

        self._tts_stop_event.clear()

        def worker():
            auto_next_chapter = False
            try:
                result = run_tts_read_loop(
                    TtsReadContext(
                        server=self._server,
                        tts=self.tts,
                        prefetch_slot=self._tts_prefetch_slot,
                        chap_txts=chap_txts,
                        hooks=TtsReadRunnerHooks(
                            play_audio=self._play_audio,
                            should_stop=self._tts_stop_event.is_set,
                            on_first_audio_ready=self._on_tts_first_audio_ready,
                            before_paragraph=self._before_gui_tts_paragraph,
                            after_paragraph=self._after_gui_tts_paragraph,
                            on_prefetch_error=self._on_tts_prefetch_error,
                        ),
                    ),
                    start_idx=start_idx,
                )
                if result.missing_audio:
                    GLib.idle_add(
                        self._toast_msg_safe,
                        _("Read aloud failed. Remote TTS service may be unavailable."),
                        priority=GLib.PRIORITY_DEFAULT,
                    )
                    return
                if result.playback_failed or result.stopped:
                    return
                if result.completed_chapter:
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
            self.gs_tts_loading.set_visible(True)
            self.gs_tts_loading.start()
        else:
            self.gs_tts_loading.stop()
            self.gs_tts_loading.set_visible(False)
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

    def _clear_prefetched_tts_audio(self):
        """清空并释放预取槽中的音频"""
        if self._tts_prefetch_slot is not None:
            self._tts_prefetch_slot.clear()
            self._tts_prefetch_slot = None

    def _on_tts_first_audio_ready(self) -> None:
        """在首条音频就绪后关闭加载状态。"""
        GLib.idle_add(self._set_tts_loading, False,
                      priority=GLib.PRIORITY_DEFAULT)

    def _before_gui_tts_paragraph(self, idx: int, text: str) -> None:
        """在 GUI 朗读每段正文前同步阅读状态。

        Args:
            idx (int): 当前段落索引
            text (str): 当前段落文本
        """
        _ = text
        self._server.set_chap_txt_n(idx)
        GLib.idle_add(self._emit_tts_state, True,
                      priority=GLib.PRIORITY_DEFAULT)
        if self._can_update_reader_ui_for_tts():
            GLib.idle_add(self.ptc.highlight_paragraph, idx, True,
                          priority=GLib.PRIORITY_DEFAULT)
            self._set_read_jd(idx, False, save_progress=False)

    def _after_gui_tts_paragraph(self, idx: int, seconds: float) -> None:
        """在 GUI 朗读每段正文后保存阅读进度。

        Args:
            idx (int): 当前段落索引
            seconds (float): 当前段朗读耗时
        """
        if seconds <= 0:
            return
        self._set_read_jd(
            idx,
            False,
            save_progress=True,
            way=TIME_READ_WAY_LISTEN,
            seconds_override=seconds,
        )

    def _on_tts_prefetch_error(self, exc: Exception) -> None:
        """记录后台预取失败日志。

        Args:
            exc (Exception): 预取阶段抛出的异常
        """
        get_logger().warning("Prefetch TTS failed: %s", exc)

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

    @Gtk.Template.Callback()
    def _on_cancel_load_book(self, *_args) -> None:
        """响应取消加载书籍按钮点击事件。"""
        self.handle_cancel_load_book(*_args)

    @Gtk.Template.Callback()
    def _on_retry_load(self, *_args) -> None:
        """响应重试加载书籍按钮点击事件。"""
        self.handle_retry_load(*_args)

    @Gtk.Template.Callback()
    def _on_next_chap(self, *_args) -> None:
        """响应切换到下一章按钮点击事件。"""
        self.handle_next_chap(*_args)

    @Gtk.Template.Callback()
    def _on_last_chap(self, *_args) -> None:
        """响应切换到上一章按钮点击事件。"""
        self.handle_last_chap(*_args)

    @Gtk.Template.Callback()
    def _on_search_toc_changed(self, entry: Gtk.SearchEntry) -> None:
        """响应目录搜索框内容变化。"""
        self.handle_search_toc_changed(entry)

    @Gtk.Template.Callback()
    def _on_search_toc_stop(self, *_args) -> None:
        """响应目录搜索停止事件。"""
        self.handle_search_toc_stop(*_args)

    @Gtk.Template.Callback()
    def _on_show_search_toc(self, btn: Gtk.ToggleButton) -> None:
        """响应显示目录搜索框按钮点击事件。"""
        self.handle_show_search_toc(btn)

    @Gtk.Template.Callback()
    def _on_fontsize_changed(self, widget, persist: bool = True) -> None:
        """响应字体大小设置变化。"""
        self.handle_fontsize_changed(widget, persist=persist)

    @Gtk.Template.Callback()
    def _on_line_space_changed(self, widget, persist: bool = True) -> None:
        """响应行间距设置变化。"""
        self.handle_line_space_changed(widget, persist=persist)

    @Gtk.Template.Callback()
    def _on_paragraph_space_changed(self, widget, persist: bool = True) -> None:
        """响应段间距设置变化。"""
        self.handle_paragraph_space_changed(widget, persist=persist)

    @Gtk.Template.Callback()
    def _on_set_default(self, *_args) -> None:
        """响应恢复默认阅读设置按钮点击事件。"""
        self.handle_set_default(*_args)

    @Gtk.Template.Callback()
    def _on_stop_read_aloud(self, *_args):
        """响应阅读页内停止朗读按钮点击事件。"""
        self.stop_read_aloud()

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
        chap_name = (self._server.get_chap_name(
            self._server.get_chap_n()) or "").strip()
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
        chap_name = (self._server.get_chap_name(
            self._server.get_chap_n()) or "").strip()
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
        self.gb_tts_start.set_visible(not is_playing)
        self.btn_tts_stop.set_visible(is_playing)
        if self._on_tts_state_changed:
            self._on_tts_state_changed(
                is_playing, self.get_read_aloud_status_text())
        return False

    def _toast_msg_safe(self, msg: str):
        root = self.get_root()
        if root and hasattr(root, "toast_msg"):
            root.toast_msg(msg)
        return False

    @Gtk.Template.Callback()
    def _on_click_title(self, *_args) -> None:
        """将目录滚动到当前章节。"""
        self._locate_toc(self._server.get_chap_n())

    def _update_chap_txt_progress_label(self, idx: int, total: int):
        if total <= 0:
            self.glb_chap_txt_n.set_text("")
            return False
        self.glb_chap_txt_n.set_text(f"{idx + 1}/{total}")
        return False
