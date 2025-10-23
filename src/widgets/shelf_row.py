"""书架中每一行的组件"""
from gi.repository import GLib, GObject, Gtk  # type: ignore

from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book, BookObject


@Gtk.Template(resource_path="/cool/ldr/heartale/shelf_row.ui")
class ShelfRow(Gtk.Box):
    """_summary_

    Args:
        Gtk (_type_): _description_
    """
    __gtype_name__ = "ShelfRow"
    __gsignals__ = {
        "delete-request": (GObject.SignalFlags.RUN_FIRST, None,
                           (GObject.TYPE_PYOBJECT,)),
        "top-request": (GObject.SignalFlags.RUN_FIRST, None,
                        (GObject.TYPE_PYOBJECT,)),
    }

    lbl_title: Gtk.Label = Gtk.Template.Child()
    lbl_sub: Gtk.Label = Gtk.Template.Child()
    btn_top: Gtk.Button = Gtk.Template.Child()  # 新增按钮

    def __init__(self, **kw):
        super().__init__(**kw)
        self.book = None

    @Gtk.Template.Callback()
    def _on_book_del(self, *_):
        self.emit("delete-request", self.book)

    @Gtk.Template.Callback()
    def _on_book_top(self, *_):
        self.emit("top-request", self.book)

    def update(self, bobj: BookObject):
        """_summary_

        Args:
            bobj (_type_): _description_
        """
        book: Book = bobj.to_dataclass()
        self.book = book
        name = book.name or "(未命名)"

        if book.fmt == BOOK_FMT_LEGADO:
            name += " [Legado]"
        elif book.fmt == BOOK_FMT_TXT:
            name += " [TXT]"

        self.lbl_title.set_text(name)

        self.lbl_sub.set_text(book.get_jd_str())

        context = self.btn_top.get_style_context()

        if book.sort > 0:
            context.add_class("top")  # 添加选中样式
            self.btn_top.set_icon_name("go-bottom-symbolic")  # 不可点击
            self.btn_top.set_tooltip_text("取消置顶")  # 不可点击
        else:
            context.remove_class("top")  # 移除选中样式
            self.btn_top.set_icon_name("go-top-symbolic")  # 不可点击
            self.btn_top.set_tooltip_text("置顶此书")  # 不可点击
