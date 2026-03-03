"""GTK application entry."""
import sys
import threading
from datetime import datetime
from gettext import gettext as _


def run_gui_app(version, app_id, argv) -> int:
    """Run the GTK application."""
    try:
        from gi.repository import Adw, Gio, GLib  # type: ignore
        from .preferences import PreferencesDialog
        from .utils import PACKAGE_URL
        from .utils.check_update import main as check_update
        from .utils.debug_gtk import get_gtk_msg
        from .utils.gui import open_url
        from .window import HeartaleWindow
    except Exception as exc:  # pylint: disable=broad-except
        print(_("GTK UI dependencies are unavailable: {error}").format(error=exc))
        return 1

    class HeartaleApplication(Adw.Application):
        """The main application singleton class."""

        def __init__(self, version_, app_id_):
            super().__init__(application_id=app_id_,
                             flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                             resource_base_path='/cool/ldr/heartale')
            self.version = version_
            self.win = None
            self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
            self.create_action('about', self.on_about_action)
            self.create_action('preferences', self.on_preferences_action)
            self.create_action('find_update', self.find_update)
            self.find_update()

        def do_activate(self):
            self.win = self.props.active_window
            if not self.win:
                self.win = HeartaleWindow(application=self)
            self.win.present()

        def on_about_action(self, *_args):
            year = datetime.now().year

            about = Adw.AboutDialog(
                application_name='heartale',
                application_icon='cool.ldr.heartale',
                developer_name='yuhldr',
                version=self.version,
                designers=[f'yuh <yuhldr@qq.com>, 2025-{year}'],
                documenters=[f'yuh <yuhldr@qq.com>, 2025-{year}'],
                developers=[f'yuh <yuhldr@qq.com>, 2025-{year}'],
                copyright=f'© 2025 -{year} yuh',
                debug_info=get_gtk_msg(self.version),
            )
            about.set_translator_credits(_('translator-credits'))
            about.present(self.props.active_window)

        def on_preferences_action(self, _widget, _):
            dialog = PreferencesDialog()
            dialog.present(self.props.active_window)

        def create_action(self, name, callback, shortcuts=None):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if shortcuts:
                self.set_accels_for_action(f"app.{name}", shortcuts)

        def update_app(self, update_msg, title=None):
            if title is None:
                title = _("New version available")

            dlg = Adw.MessageDialog(
                transient_for=self.win,
                modal=True,
                heading=title,
                body=update_msg,
            )
            dlg.add_response("cancel", _("Cancel"))
            dlg.add_response("ok", _("Update"))
            dlg.set_default_response("ok")
            dlg.set_close_response("cancel")

            def _on_resp(_d, resp):
                if resp == "ok":
                    open_url(PACKAGE_URL)

            dlg.connect("response", _on_resp)
            dlg.present()

        def find_update(self, widget_no_auto=None, _w=None):
            def fu():
                update_msg = check_update(self.version)
                if update_msg is not None:
                    GLib.idle_add(self.update_app, update_msg)
                elif widget_no_auto:
                    s = _("There is no new version."
                          "\nThe current version is {version}."
                          "\nYou can go to {url} to view the beta version.") \
                        .format(self.version, PACKAGE_URL)
                    GLib.idle_add(self.update_app, s, _("No new version found"))

            threading.Thread(target=fu, daemon=True).start()

    app = HeartaleApplication(version, app_id)
    print(version)
    return app.run([sys.argv[0], *argv])
