"""单本书 TXT 解析规则设置对话框。"""

from __future__ import annotations

from gettext import gettext as _
from typing import Callable, Optional

from gi.repository import Adw, Gtk  # type: ignore

from ..entity import LibraryDB
from ..entity.book import Book
from ..servers.txt import (get_txt_parse_config,
                           validate_book_txt_parse_overrides)


@Gtk.Template(resource_path="/cool/ldr/heartale/book_txt_parse_dialog.ui")
class BookTxtParseDialog(Adw.PreferencesDialog):
    """用于编辑单本书 TXT 章节解析规则的对话框。"""

    __gtype_name__ = "BookTxtParseDialog"

    row_volume: Adw.EntryRow = Gtk.Template.Child()
    row_chapter: Adw.EntryRow = Gtk.Template.Child()

    def __init__(self, book: Book, on_done: Optional[Callable[[], None]] = None):
        """初始化对话框。

        Args:
            book (Book): 当前书籍
            on_done (Callable[[], None] | None): 保存/清除后的回调
        """
        super().__init__()
        self._book = book
        self._on_done = on_done

        global_cfg = get_txt_parse_config()

        self.row_volume.set_text(str(book.txt_volume_pattern or ""))
        if hasattr(self.row_volume, "set_placeholder_text"):
            self.row_volume.set_placeholder_text(
                str(global_cfg.get("volume_pattern", "")))

        self.row_chapter.set_text(str(book.txt_chapter_pattern or ""))
        if hasattr(self.row_chapter, "set_placeholder_text"):
            self.row_chapter.set_placeholder_text(
                str(global_cfg.get("chapter_pattern", "")))

    def _close_self(self) -> None:
        """关闭当前对话框。"""
        if hasattr(self, "close"):
            self.close()
            return
        if hasattr(self, "destroy"):
            self.destroy()

    def _show_error(self, heading: str, body: str) -> None:
        """显示错误对话框。

        Args:
            heading (str): 标题
            body (str): 详细信息
        """
        parent = self.get_root()
        dialog = Adw.MessageDialog(
            transient_for=parent,
            modal=True,
            heading=heading,
            body=body,
        )
        dialog.add_response("ok", _("OK"))
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present()

    @Gtk.Template.Callback()
    def _on_save_clicked(self, *_args) -> None:
        """保存书籍自定义解析规则。"""
        try:
            volume_pattern, chapter_pattern = validate_book_txt_parse_overrides(
                self.row_volume.get_text(),
                self.row_chapter.get_text(),
            )
        except ValueError as exc:
            self._show_error(_("Failed to save TXT parse rules"), str(exc))
            return

        self._book.txt_volume_pattern = volume_pattern
        self._book.txt_chapter_pattern = chapter_pattern
        db = LibraryDB()
        db.update_book(self._book)
        db.close()

        if self._on_done:
            self._on_done()
        self._close_self()

    @Gtk.Template.Callback()
    def _on_clear_clicked(self, *_args) -> None:
        """清除书籍自定义解析规则。"""
        self._book.txt_volume_pattern = ""
        self._book.txt_chapter_pattern = ""
        db = LibraryDB()
        db.update_book(self._book)
        db.close()

        if self._on_done:
            self._on_done()
        self._close_self()
