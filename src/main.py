"""main"""
import sys
from gettext import gettext as _

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version("GObject", "2.0")


from gi.repository import Adw, Gio  # type: ignore pylint: disable=C0413

from .window import HeartaleWindow  # pylint: disable=C0413


class HeartaleApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='cool.ldr.heartale',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/cool/ldr/heartale')
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)

    def do_activate(self):
        """Called when the application is activated.
        We raise the application's main window, creating it if
        necessary.

        Raises:
            the: _description_
        """
        win = self.props.active_window
        if not win:
            win = HeartaleWindow(application=self)
        win.present()

    def on_about_action(self, *_args):
        """Callback for the app.about actio
        """
        about = Adw.AboutDialog(application_name='heartale',
                                application_icon='cool.ldr.heartale',
                                developer_name='Unknown',
                                version='0.1.0',
                                developers=['Unknown'],
                                copyright='© 2025 Unknown')
        about.set_translator_credits(_('translator-credits'))
        about.present(self.props.active_window)

    def on_preferences_action(self, _widget, _):
        """Callback for the app.preferences action.

        Args:
            _widget (_type_): _description_
            _ (_type_): _description_
        """        """"""
        print('app.preferences action activated')

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = HeartaleApplication()
    print(version)
    return app.run(sys.argv)
