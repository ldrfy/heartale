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
        "statistics-request": (GObject.SignalFlags.RUN_FIRST, None,
                        (GObject.TYPE_PYOBJECT,)),
    }

    lbl_title: Gtk.Label = Gtk.Template.Child()
    lbl_sub: Gtk.Label = Gtk.Template.Child()
    btn_top: Gtk.Button = Gtk.Template.Child()  # 新增按钮

    def __init__(self, **kw):
        super().__init__(**kw)
        self._bound_item = None

    @Gtk.Template.Callback()
    def _on_book_del(self, *_):
        self.emit("delete-request", self._bound_item)

    @Gtk.Template.Callback()
    def _on_book_top(self, *_):
        """置顶处理：发出信号，由上层接管 DB 修改 sort"""
        self.emit("top-request", self._bound_item)

    @Gtk.Template.Callback()
    def _on_book_statistics(self, *_):
        """置顶处理：发出信号，由上层接管 DB 修改 sort"""
        self.emit("statistics-request", self._bound_item)
        self.get_root().toast_msg("阅读统计功能开发中，敬请期待！")

    def update(self, bobj: BookObject):
        """_summary_

        Args:
            bobj (_type_): _description_
        """
        self._bound_item = bobj
        book: Book = bobj.to_dataclass()
        name = book.name or "(未命名)"

        if book.fmt == BOOK_FMT_LEGADO:
            name += " [Legado]"
        elif book.fmt == BOOK_FMT_TXT:
            name += " [TXT]"

        self.lbl_title.set_text(name)
        txt_all = book.txt_all or 0
        txt_pos = book.txt_pos or 0
        pct = int(txt_pos * 100 / txt_all) if txt_all else 0
        enc = getattr(bobj, "encoding", "") or ""
        home = GLib.get_home_dir()

        path = book.path.replace(home, '~')
        subtitle = f"进度 {pct}% ({book.chap_n}/{book.chap_all}) · 编码 {enc} · 路径 {path}"

        self.lbl_sub.set_text(subtitle)

        context = self.btn_top.get_style_context()

        if book.sort > 0:
            context.add_class("top")  # 添加选中样式
            self.btn_top.set_icon_name("go-bottom-symbolic")  # 不可点击
            self.btn_top.set_tooltip_text("取消置顶")  # 不可点击
        else:
            context.remove_class("top")  # 移除选中样式
            self.btn_top.set_icon_name("go-top-symbolic")  # 不可点击
            self.btn_top.set_tooltip_text("置顶此书")  # 不可点击
