"""GTK-related utility helpers."""
import os

from gi.repository import Gio, Gtk  # type: ignore


def open_url(url: str):
    """Open an URL with Gtk.UriLauncher."""
    launcher = Gtk.UriLauncher.new(url)
    launcher.launch(None, None, None)


def open_folder(folder_path: str):
    """Open a folder or a file's containing folder."""
    if os.path.isfile(folder_path):
        folder_path = os.path.dirname(folder_path)
    uri = f"file://{folder_path}"
    print(f"Opening folder: {uri}")
    Gio.AppInfo.launch_default_for_uri(uri, None)
