"""GTK 图形应用入口。"""

import sys
import threading
from collections.abc import Callable
from datetime import datetime
from gettext import gettext as _
from importlib import import_module
from typing import Any, NamedTuple


class GuiDeps(NamedTuple):
    """GTK 运行时依赖集合。"""

    adw: Any
    gio: Any
    glib: Any
    preferences_dialog_class: Any
    package_url: str
    check_update_func: Callable[[str], str | None]
    get_gtk_msg_func: Callable[[str], str]
    open_url_func: Callable[[str], None]
    heartale_window_class: Any


class _HeartaleApplicationMixin:
    """Heartale GTK 应用共用逻辑。"""

    def _init_application(self, version: str, app_id: str, gui_deps: GuiDeps):
        """初始化应用实例。

        Args:
            version (str): 当前应用版本
            app_id (str): GTK 应用标识
            gui_deps (GuiDeps): GTK 运行时依赖集合
        """
        super().__init__(
            application_id=app_id,
            flags=gui_deps.gio.ApplicationFlags.DEFAULT_FLAGS,
            resource_base_path="/cool/ldr/heartale",
        )
        self.version = version
        self.win = None
        self._gui = gui_deps
        self.create_action("quit", lambda *_: self.quit(), ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("preferences", self.on_preferences_action)
        self.create_action("find_update", self.find_update)
        self.find_update()

    def _do_activate(self):
        """激活应用并展示主窗口。"""
        self.win = self.props.active_window
        if not self.win:
            self.win = self._gui.heartale_window_class(application=self)
        self.win.present()

    def on_about_action(self, *_args):
        """打开关于对话框。"""
        year = datetime.now().year
        about = self._gui.adw.AboutDialog(
            application_name="heartale",
            application_icon="cool.ldr.heartale",
            developer_name="yuhldr",
            version=self.version,
            designers=[f"yuh <yuhldr@qq.com>, 2025-{year}"],
            documenters=[f"yuh <yuhldr@qq.com>, 2025-{year}"],
            developers=[f"yuh <yuhldr@qq.com>, 2025-{year}"],
            copyright=f"© 2025 -{year} yuh",
            debug_info=self._gui.get_gtk_msg_func(self.version),
        )
        about.set_translator_credits(_("translator-credits"))
        about.present(self.props.active_window)

    def on_preferences_action(self, _widget, _):
        """打开偏好设置对话框。"""
        dialog = self._gui.preferences_dialog_class()
        dialog.present(self.props.active_window)

    def create_action(self, name, callback, shortcuts=None):
        """注册应用级动作。

        Args:
            name (str): 动作名称
            callback (Callable): 动作回调
            shortcuts (list[str] | None): 动作快捷键列表
        """
        action = self._gui.gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

    def _open_package_url(self, _dialog, response: str):
        """在确认更新时打开项目页面。

        Args:
            _dialog: 消息对话框实例
            response (str): 用户响应标识
        """
        if response == "ok":
            self._gui.open_url_func(self._gui.package_url)

    def update_app(self, update_msg: str, title: str | None = None):
        """显示版本更新提示。

        Args:
            update_msg (str): 更新说明文本
            title (str | None): 对话框标题
        """
        if title is None:
            title = _("New version available")

        dialog = self._gui.adw.MessageDialog(
            transient_for=self.win,
            modal=True,
            heading=title,
            body=update_msg,
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ok", _("Update"))
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._open_package_url)
        dialog.present()

    def _show_no_update_message(self):
        """显示当前没有新版本的提示。"""
        message = _(
            "There is no new version."
            "\nThe current version is {version}."
            "\nYou can go to {url} to view the beta version."
        ).format(version=self.version, url=self._gui.package_url)
        self._gui.glib.idle_add(self.update_app, message, _("No new version found"))

    def find_update(self, widget_no_auto=None, _w=None):
        """异步检查新版本。

        Args:
            widget_no_auto: 手动触发更新检查时的控件对象
            _w: 保留的信号参数
        """

        def worker():
            update_msg = self._gui.check_update_func(self.version)
            if update_msg is not None:
                self._gui.glib.idle_add(self.update_app, update_msg)
            elif widget_no_auto:
                self._show_no_update_message()

        threading.Thread(target=worker, daemon=True).start()


def _load_gui_deps() -> tuple[GuiDeps | None, Exception | None]:
    """加载 GTK 运行时依赖。

    Returns:
        tuple[GuiDeps | None, Exception | None]: 成功时返回依赖对象，失败时返回异常
    """
    try:
        gi_repository = import_module("gi.repository")
        preferences_module = import_module(".preferences", __package__)
        utils_module = import_module(".utils", __package__)
        check_update_module = import_module(".utils.check_update", __package__)
        debug_gtk_module = import_module(".utils.debug_gtk", __package__)
        gui_utils_module = import_module(".utils.gui", __package__)
        window_module = import_module(".window", __package__)
    except Exception as exc:  # pylint: disable=broad-except
        return None, exc

    return GuiDeps(
        adw=gi_repository.Adw,
        gio=gi_repository.Gio,
        glib=gi_repository.GLib,
        preferences_dialog_class=preferences_module.PreferencesDialog,
        package_url=utils_module.PACKAGE_URL,
        check_update_func=check_update_module.main,
        get_gtk_msg_func=debug_gtk_module.get_gtk_msg,
        open_url_func=gui_utils_module.open_url,
        heartale_window_class=window_module.HeartaleWindow,
    ), None


def _build_heartale_application_class(gui_deps: GuiDeps):
    """创建绑定 GTK 基类的应用类。

    Args:
        gui_deps (GuiDeps): GTK 运行时依赖集合

    Returns:
        type: 绑定 GTK Application 基类后的应用类
    """

    class HeartaleApplication(_HeartaleApplicationMixin, gui_deps.adw.Application):
        """主 GTK 应用类。"""

        def __init__(self, version: str, app_id: str, app_gui_deps: GuiDeps):
            """初始化主 GTK 应用类。

            Args:
                version (str): 当前应用版本
                app_id (str): GTK 应用标识
                app_gui_deps (GuiDeps): GTK 运行时依赖集合
            """
            self._init_application(version, app_id, app_gui_deps)

        def do_activate(self):
            """激活应用并展示主窗口。"""
            self._do_activate()

    return HeartaleApplication


def run_gui_app(version: str, app_id: str, argv: list[str]) -> int:
    """运行 GTK 图形应用。

    Args:
        version (str): 当前应用版本
        app_id (str): GTK 应用标识
        argv (list[str]): 启动参数

    Returns:
        int: 应用退出码
    """
    gui_deps, error = _load_gui_deps()
    if error is not None:
        print(_("GTK UI dependencies are unavailable: {error}").format(error=error))
        return 1

    app_class = _build_heartale_application_class(gui_deps)
    app = app_class(version, app_id, gui_deps)
    print(version)
    return app.run([sys.argv[0], *argv])
