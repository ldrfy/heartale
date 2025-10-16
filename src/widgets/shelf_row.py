"""书架中每一行的组件"""
from gi.repository import GObject, Gtk  # type: ignore


@Gtk.Template(resource_path="/cool/ldr/heartale/shelf_row.ui")
class ShelfRow(Gtk.Box):
    """_summary_

    Args:
        Gtk (_type_): _description_
    """
    __gtype_name__ = "ShelfRow"
    __gsignals__ = {
        "delete-request": (GObject.SignalFlags.RUN_FIRST, None,
                           (GObject.TYPE_PYOBJECT,))
    }
    lbl_title: Gtk.Label = Gtk.Template.Child()
    lbl_sub: Gtk.Label = Gtk.Template.Child()
    btn_del: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kw):
        super().__init__(**kw)
        self._bound_item = None
        self.btn_del.connect("clicked", self._on_delete)

    def _on_delete(self, *_):
        self.emit("delete-request", self._bound_item)

    def update(self, bobj):
        """_summary_

        Args:
            bobj (_type_): _description_
        """
        self._bound_item = bobj
        name = getattr(bobj, "name", None) or "(未命名)"
        self.lbl_title.set_text(name)
        txt_all = getattr(bobj, "txt_all", 0) or 0
        txt_pos = getattr(bobj, "txt_pos", 0) or 0
        pct = int(txt_pos * 100 / txt_all) if txt_all else 0
        enc = getattr(bobj, "encoding", "") or ""
        self.lbl_sub.set_text(f"进度 {pct}% · 编码 {enc}")
