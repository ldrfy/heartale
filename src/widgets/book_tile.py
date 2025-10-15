"""封面"""
from pathlib import Path

from gi.repository import Gtk  # type: ignore

from ..entity import Book


@Gtk.Template(resource_path="/cool/ldr/heartale/book_tile.ui")
class BookTile(Gtk.Box):
    """_summary_

    Args:
        Gtk (_type_): _description_

    Returns:
        _type_: _description_
    """
    __gtype_name__ = "BookTile"
    lb_title: Gtk.Label = Gtk.Template.Child()
    sp_book_loading: Gtk.Label = Gtk.Template.Child()

    def __init__(self, book: Book, **kwargs):
        super().__init__(**kwargs)
        self._book = book
        self._apply_book()

    @property
    def book(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        return self._book

    def _apply_book(self):
        self.lb_title.set_text(self._book.name)
