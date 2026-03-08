"""书架行组件。"""

from gettext import gettext as _

from gi.repository import Gdk, GObject, Gtk  # type: ignore

from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book, BookObject


@Gtk.Template(resource_path="/cool/ldr/heartale/shelf_row.ui")
class ShelfRow(Gtk.Box):
    """显示单本书信息的书架行。"""

    __gtype_name__ = "ShelfRow"
    __gsignals__ = {
        "delete-request": (GObject.SignalFlags.RUN_FIRST, None,
                           (GObject.TYPE_PYOBJECT,)),
        "top-request": (GObject.SignalFlags.RUN_FIRST, None,
                        (GObject.TYPE_PYOBJECT,)),
    }

    lbl_title: Gtk.Label = Gtk.Template.Child()
    lbl_sub: Gtk.Label = Gtk.Template.Child()
    img_top_mark: Gtk.Image = Gtk.Template.Child()

    def __init__(self, **kw):
        super().__init__(**kw)
        self.book = None
        self._menu_top_button = self._create_menu_button()
        self._menu_delete_button = self._create_menu_button(
            label=_("Delete"),
            css_classes=["flat", "destructive-action"],
        )
        self._menu_delete_button.connect("clicked", self._on_book_del)
        self._menu_top_button.connect("clicked", self._on_book_top)
        self._context_popover = self._build_context_popover()
        self._install_context_menu_gesture()

    def do_unroot(self):
        """销毁组件前释放右键菜单。"""
        if self._context_popover.get_parent() is not None:
            self._context_popover.unparent()
        Gtk.Box.do_unroot(self)

    def _on_book_del(self, *_):
        """发出删除当前书籍的请求。"""
        self._context_popover.popdown()
        self.emit("delete-request", self.book)

    def _on_book_top(self, *_):
        """发出置顶或取消置顶当前书籍的请求。"""
        self._context_popover.popdown()
        self.emit("top-request", self.book)

    def update(self, bobj: BookObject):
        """使用书籍数据刷新当前行。

        Args:
            bobj (BookObject): 书籍对象
        """
        book: Book = bobj.to_dataclass()
        self.book = book
        name = book.name or _("(Untitled)")

        if book.fmt == BOOK_FMT_LEGADO:
            name += " [Legado]"
        elif book.fmt == BOOK_FMT_TXT:
            name += " [TXT]"

        self.lbl_title.set_text(name)
        self.lbl_sub.set_text(book.get_jd_str())
        self.img_top_mark.set_visible(book.sort > 0)
        self._update_context_menu()

    def _create_menu_button(self, label="", css_classes=None) -> Gtk.Button:
        """创建右键菜单中的按钮。

        Args:
            label (str): 按钮文字
            css_classes (list[str] | None): 需要附加的样式类

        Returns:
            Gtk.Button: 菜单按钮
        """
        button = Gtk.Button(label=label)
        button.set_halign(Gtk.Align.FILL)
        button.set_hexpand(True)
        button.set_valign(Gtk.Align.CENTER)
        button.add_css_class("flat")

        for css_class in css_classes or []:
            if css_class != "flat":
                button.add_css_class(css_class)
        return button

    def _build_context_popover(self) -> Gtk.Popover:
        """构建书架行的右键菜单。

        Returns:
            Gtk.Popover: 右键菜单弹层
        """
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        menu_box.append(self._menu_top_button)
        menu_box.append(self._menu_delete_button)

        popover = Gtk.Popover()
        popover.set_autohide(True)
        popover.set_has_arrow(False)
        popover.set_child(menu_box)
        popover.set_parent(self)
        return popover

    def _install_context_menu_gesture(self) -> None:
        """安装右键菜单手势。"""
        gesture = Gtk.GestureClick()
        gesture.set_button(Gdk.BUTTON_SECONDARY)
        gesture.connect("pressed", self._on_context_menu_pressed)
        self.add_controller(gesture)

    def _on_context_menu_pressed(self, gesture, _n_press, x, y) -> None:
        """在右键点击时弹出上下文菜单。

        Args:
            gesture (Gtk.GestureClick): 手势对象
            _n_press (int): 点击次数
            x (float): 点击横坐标
            y (float): 点击纵坐标
        """
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self._context_popover.set_pointing_to(rect)
        self._context_popover.popup()

    def _update_context_menu(self) -> None:
        """按当前书籍状态更新右键菜单文本。"""
        if self.book is None:
            return

        if self.book.sort > 0:
            self._menu_top_button.set_label(_("Cancel topping this book"))
            return

        self._menu_top_button.set_label(_("Top this book"))
