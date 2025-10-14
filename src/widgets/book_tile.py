"""封面"""
from pathlib import Path

from gi.repository import Gtk  # type: ignore


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

    def __init__(self, book: dict, **kwargs):
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
        title = self._book.get("title") or Path(
            self._book.get("path", "")).name or "Untitled"
        self.lb_title.set_text(title)
