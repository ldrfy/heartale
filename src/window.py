"""主窗口"""

from gi.repository import Adw, Gtk  # type: ignore

from .pages.reader_page import ReaderPage
from .pages.shelf_page import ShelfPage


@Gtk.Template(resource_path="/cool/ldr/heartale/window.ui")
class HeartaleWindow(Adw.ApplicationWindow):
    """主窗口

    Args:
        Adw (_type_): _description_
    """
    __gtype_name__ = "HeartaleWindow"

    nav: Adw.NavigationView = Gtk.Template.Child()
    toasts: Adw.ToastOverlay = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._reader_page = ReaderPage(self.nav)
        self._shelf_page = ShelfPage(self.nav, self._reader_page)

        self.nav.push(self._shelf_page)

    @Gtk.Template.Callback()
    def on_visible_page_changed(self, *_):
        """加载书架数据
        """
        page = self.nav.get_visible_page()
        if not page:
            return

        if isinstance(page, ShelfPage):
            print("当前页面变化为：ShelfPage，重新加载书架数据")
            self._shelf_page.reload_bookshel()

    def toast_msg(self, toast_msg):
        """在 main.py 中的通知

        Args:
            toast_msg (str): _description_
        """
        # 放置初始化时，不断调用误以为选择
        toast = Adw.Toast.new("")
        toast.set_timeout(2)
        toast.dismiss()
        toast.set_title(toast_msg)
        self.toasts.add_toast(toast)
