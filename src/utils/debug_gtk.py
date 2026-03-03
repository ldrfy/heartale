"""GTK debug helpers."""
import platform

from gi.repository import Adw, Gtk  # type: ignore

from .debug import get_log_handler, get_os_release


def get_gtk_msg(version):
    """Build GTK debug info text."""
    s = f"Version: {version}"
    s += f"\nSystem: {platform.system()}"
    s += f"\nRelease: {platform.release()}"

    gvs = Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()
    s += f"\nGTK Version: {gvs[0]}.{gvs[1]}.{gvs[2]}"

    avs = Adw.get_major_version(), Adw.get_minor_version(), Adw.get_micro_version()
    s += f"\nAdwaita Version: {avs[0]}.{avs[1]}.{avs[2]}"

    s += "\n\n******* debug log *******\n"
    s += get_log_handler().get_logs()

    s += "\n\n******* other *******\n"
    s += get_os_release()
    return s
