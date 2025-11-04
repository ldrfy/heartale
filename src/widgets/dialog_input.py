"""Input dialog helpers."""
from gettext import gettext as _

from gi.repository import Adw, Gtk  # type: ignore


class InputDialog(Adw.MessageDialog):
    """Adwaita message dialog with a text entry."""

    def __init__(self, parent, title=_("Enter text"), subtitle=""):
        super().__init__(transient_for=parent)
        self.set_heading(title)

        if subtitle:
            self.set_body(subtitle)

        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        self.set_extra_child(self.entry)

        self.add_response("cancel", _("Cancel"))
        self.add_response("ok", _("OK"))
        self.set_default_response("ok")
        self.set_close_response("cancel")
    
    def set_input_text(self, text: str):
        """Pre-fill the entry widget with text."""
        self.entry.set_text(text)


# win = Adw.ApplicationWindow()
# dlg = InputDialog(win)
# dlg.connect("response", lambda d, r: print(
#     "输入结果:", d.entry.get_text() if r == "ok" else None))
# dlg.present()
