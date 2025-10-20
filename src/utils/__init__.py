"""工具"""
from gi.repository import Gtk  # type: ignore

PACKAGE_URL = "https://github.com/ldrfy/heartale"


def open_url(url: str):
    """打开链接

    Args:
        url (str): _description_
    """
    launcher = Gtk.UriLauncher.new(url)
    launcher.launch(None, None, None)
