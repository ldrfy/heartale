"""输入对话框"""
from gi.repository import Adw, Gtk


class InputDialog(Adw.MessageDialog):
    """_summary_

    Args:
        Adw (_type_): _description_
    """
    def __init__(self, parent, title="输入文字", subtitle=""):
        super().__init__(transient_for=parent)
        self.set_heading(title)

        if subtitle:
            self.set_body(subtitle)

        entry = Gtk.Entry()
        entry.set_hexpand(True)
        self.set_extra_child(entry)
        self.entry = entry

        self.add_response("cancel", "取消")
        self.add_response("ok", "确定")
        self.set_default_response("ok")
        self.set_close_response("cancel")


# win = Adw.ApplicationWindow()
# dlg = InputDialog(win)
# dlg.connect("response", lambda d, r: print(
#     "输入结果:", d.entry.get_text() if r == "ok" else None))
# dlg.present()
