from gi.repository import Gio, Gtk

PACKAGE_URL = "https://github.com/ldrfy/heartale"


def open_url(url: str):
    launcher = Gtk.UriLauncher.new(url)
    launcher.launch(None, None, None)
