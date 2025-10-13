# book_tile.py
from pathlib import Path

from gi.repository import Gtk


@Gtk.Template(resource_path="/cool/ldr/heartale/book_tile.ui")
class BookTile(Gtk.Box):
    __gtype_name__ = "BookTile"
    lbl_title: Gtk.Label = Gtk.Template.Child()
    box_cover: Gtk.Box = Gtk.Template.Child()

    def __init__(self, book: dict, **kwargs):
        super().__init__(**kwargs)
        self._book = book
        self._apply_book()

    @property
    def book(self):
        return self._book

    def _apply_book(self):
        title = self._book.get("title") or Path(
            self._book.get("path", "")).name or "Untitled"
        self.lbl_title.set_text(title)
        # 如要封面，这里给 box_cover 塞 Gtk.Picture 即可
