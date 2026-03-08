"""阅读页书籍会话与章节切换逻辑。"""

import threading
import time
import traceback
from gettext import gettext as _

from gi.repository import GLib  # type: ignore

from ..entity import LibraryDB
from ..entity.book import Book
from ..tts.backends import create_active_tts_backend
from ..utils.debug import get_logger
from ..utils.reader import (create_reader_server, load_chapter_into_server,
                            prefetch_next_chapter_async)


class ReaderSessionMixin:
    """封装书籍加载、章节显示和切章逻辑。"""

    def set_data(self, book: Book) -> None:
        """在后台加载书籍数据并更新界面。

        Args:
            book (Book): 待读取的书籍对象
        """
        if self._tts_thread and self._tts_thread.is_alive():
            if self._tts_book_md5 != book.md5:
                self._stop_tts_playback()

        if self._server and self._server.book and self._server.book.md5 == book.md5:
            if self._should_restore_current_book_view(book):
                self._restore_current_book_view()
                return

        self.t = time.time()
        self._search_debounce_id = 0

        self.btn_prev_chap.set_sensitive(True)
        self.btn_next_chap.set_sensitive(True)
        self.load_reader_settings()
        self.handle_search_toc_stop()

        self.title.set_title(book.name or "")
        self.title.set_subtitle(book.get_jd_str())

        self.clear_data()
        threading.Thread(target=self._load_book_worker,
                         args=(book,), daemon=True).start()

    def _should_restore_current_book_view(self, book: Book) -> bool:
        """判断是否可以直接复用当前已加载书籍的内存状态。

        Args:
            book (Book): 当前准备打开的书籍

        Returns:
            bool: 是否直接复用当前阅读页内存状态
        """
        if not self._server or not self._server.book:
            return False

        current_book = self._server.book
        if current_book.md5 != book.md5:
            return False

        if self._tts_thread and self._tts_thread.is_alive() and self._tts_book_md5 == book.md5:
            return True

        latest_book = self._load_book_from_db(book.md5)
        if latest_book is None:
            return True

        if self._book_progress_changed(current_book, latest_book):
            return False
        return True

    def _load_book_from_db(self, md5: str) -> Book | None:
        """从数据库读取最新的书籍记录。

        Args:
            md5 (str): 书籍唯一标识

        Returns:
            Book | None: 数据库中的最新书籍对象
        """
        db = LibraryDB()
        try:
            return db.get_book_by_md5(md5)
        finally:
            db.close()

    def _book_progress_changed(self, current_book: Book, latest_book: Book) -> bool:
        """判断数据库中的阅读进度是否已领先于当前内存状态。

        Args:
            current_book (Book): 当前页面中的书籍对象
            latest_book (Book): 数据库中的最新书籍对象

        Returns:
            bool: 数据库进度是否发生变化
        """
        return (
            current_book.chap_n != latest_book.chap_n
            or current_book.chap_txt_pos != latest_book.chap_txt_pos
            or current_book.update_date != latest_book.update_date
        )

    def _restore_current_book_view(self) -> None:
        """复用当前已加载书籍的内存状态刷新界面。"""
        if not self._server or not self._server.book:
            return

        self.btn_prev_chap.set_sensitive(True)
        self.btn_next_chap.set_sensitive(True)
        self.load_reader_settings()
        self.handle_search_toc_stop()

        self.title.set_title(self._server.book.name or "")
        self.title.set_subtitle(self._server.book.get_jd_str())
        self.stack.set_visible_child(self.aos_reader)
        self.apply_toc_search()

        if self._server.bd:
            self.ptc.set_paragraphs(self._server.bd.chap_txts)
            self.ptc.scroll_to_paragraph(self._server.bd.chap_txt_n)
            self.ptc.highlight_paragraph(self._server.bd.chap_txt_n)
            self._update_chap_txt_progress_label(
                self._server.bd.chap_txt_n,
                len(self._server.bd.chap_txts),
            )

        self._locate_toc(self._server.get_chap_n())

    def refresh_current_read_position(self) -> None:
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

    def _load_book_worker(self, book: Book) -> None:
        """后台加载书籍与章节目录。

        Args:
            book (Book): 待读取的书籍对象
        """
        try:
            self.tts = create_active_tts_backend()
            loaded_book = self._load_book_from_db(book.md5)

            self._server = create_reader_server(loaded_book)
            self._wait_minimum_loading_time()
            GLib.idle_add(self._on_data_ready, book,
                          priority=GLib.PRIORITY_DEFAULT)
        except Exception as exc:  # pylint: disable=broad-except
            self._wait_minimum_loading_time()
            error_text = f"Failed to load book: {exc}\n{traceback.format_exc()}"
            get_logger().error(error_text)
            GLib.idle_add(
                self._handle_load_error,
                book,
                error_text,
                priority=GLib.PRIORITY_DEFAULT,
            )

    def _wait_minimum_loading_time(self) -> None:
        """保证加载页至少显示一小段时间。"""
        elapsed = time.time() - self.t
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)

    def _handle_load_error(self, book: Book, err: str) -> bool:
        """在主线程处理后台加载错误。

        Args:
            book (Book): 当前尝试加载的书籍对象
            err (str): 错误文本

        Returns:
            bool: 是否继续保留空闲回调
        """
        if self._server and self._server.book and book.md5 != self._server.book.md5:
            get_logger().info("Book switched, ignoring error display")
            return False
        self.show_error(
            _(
                "Unable to open this book or its table of contents."
                "\n{title}: {path}"
                "\n\nTry again or go back:\n{error}"
            ).format(title=book.name, path=book.get_path(), error=err)
        )
        return False

    def _on_data_ready(self, book: Book) -> bool:
        """在主线程绑定目录和章节正文。

        Args:
            book (Book): 已加载完成的书籍对象

        Returns:
            bool: 是否继续保留空闲回调
        """
        if book.md5 != self._server.book.md5:
            get_logger().info("Book switched, ignoring error display")
            return False

        self.stack.set_visible_child(self.aos_reader)
        self.apply_toc_search()
        self.set_chap_text()
        GLib.timeout_add(500, self._select_current_toc_item)
        return False

    def _select_current_toc_item(self) -> bool:
        """在目录中选中当前章节。

        Returns:
            bool: 是否继续保留超时回调
        """
        if not self._server:
            return False
        self._locate_toc(self._server.get_chap_n())
        return False

    def show_error(self, des: str | None = None) -> None:
        """显示错误页。

        Args:
            des (str | None, optional): 错误描述文本. Defaults to None.
        """
        if des is None:
            des = _(
                "Unable to open this book or its table of contents. Please try again or go back."
            )
        self.stack.set_visible_child(self.page_error)
        self.page_error.set_description(des)

    def set_chap_text(self, chap_n: int = -1) -> None:
        """加载并显示指定章节内容。

        Args:
            chap_n (int, optional): 章节索引. Defaults to -1.
        """
        self.btn_prev_chap.set_sensitive(False)
        self.btn_next_chap.set_sensitive(False)
        self.spinner_sync.start()
        threading.Thread(target=self._load_chapter_worker,
                         args=(chap_n,), daemon=True).start()

    def _load_chapter_worker(self, chap_n: int) -> None:
        """后台加载章节正文。

        Args:
            chap_n (int): 章节索引
        """
        chap_name = load_chapter_into_server(
            self._server,
            chap_n,
            chap_txt_pos=self._server.book.chap_txt_pos,
            save_progress=chap_n > 0,
        )
        prefetch_next_chapter_async(self._server)
        GLib.idle_add(self._update_chapter_ui, chap_name,
                      priority=GLib.PRIORITY_DEFAULT)

    def _update_chapter_ui(self, chap_name: str) -> bool:
        """在主线程刷新章节正文界面。

        Args:
            chap_name (str): 当前章节名称

        Returns:
            bool: 是否继续保留空闲回调
        """
        self.title.set_subtitle(
            f"{chap_name} ({self._server.book.chap_n}/{self._server.book.chap_all})"
        )
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
        return False

    def handle_cancel_load_book(self, *_args) -> None:
        """返回书架页面。"""
        self._nav.pop()

    def handle_retry_load(self, *_args) -> None:
        """重新加载当前书籍。"""
        self.set_data(self._server.book)

    def handle_next_chap(self, *_args) -> None:
        """切换到下一章。"""
        self._stop_tts_playback()
        if self._server.book.chap_n + 1 >= len(self._server.chap_names):
            self.get_root().toast_msg(_("You have reached the last chapter."))
            return
        self._jump_to_relative_chapter(1)

    def handle_last_chap(self, *_args) -> None:
        """切换到上一章。"""
        self._stop_tts_playback()
        if self._server.book.chap_n - 1 <= 0:
            self.get_root().toast_msg(_("You are already at the first chapter."))
            return
        self._jump_to_relative_chapter(-1)

    def _jump_to_relative_chapter(self, offset: int) -> None:
        """按相对偏移切换章节。

        Args:
            offset (int): 相对章节偏移
        """
        self._server.book.chap_n += offset
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self._on_toc_chapter_activated(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())
