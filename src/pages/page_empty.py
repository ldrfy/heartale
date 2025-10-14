"""首页空页面"""
from gi.repository import Adw, Gtk  # type: ignore


@Gtk.Template(resource_path="/cool/ldr/heartale/page_empty.ui")
class EmptyPage(Adw.NavigationPage):
    """空的

    Args:
        Adw (_type_): _description_
    """
    __gtype_name__ = "EmptyPage"

    btn_jump_books: Gtk.Button = Gtk.Template.Child("btn_jump_books")

    def __init__(self, page_bookshelf, **kwargs):
        super().__init__(**kwargs)

        self.nav = page_bookshelf.nav

        self.page_bookshelf = page_bookshelf

    @Gtk.Template.Callback()
    def goto_bookshelf(self, *_):
        """_summary_
        """
        self.nav.push(self.page_bookshelf)
