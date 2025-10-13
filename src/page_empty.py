# page_bookshelf0.py
from gi.repository import Adw, Gtk

from .page_bookshelf import BookshelfPage


@Gtk.Template(resource_path="/cool/ldr/heartale/page_empty.ui")
class EmptyPage(Adw.NavigationPage):
    __gtype_name__ = "EmptyPage"

    btn_jump_books: Gtk.Button = Gtk.Template.Child("btn_jump_books")

    def __init__(self, nav, **kwargs):
        super().__init__(**kwargs)

        self.nav = nav
        self.btn_jump_books.connect("clicked", self._goto_bookshelf)

    # ---------- 导航 ----------
    def _goto_bookshelf(self, *_):
        self.nav.push(BookshelfPage(self.nav))
