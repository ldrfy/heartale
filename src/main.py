"""main"""
import argparse
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from gettext import gettext as _

from gi.repository import Adw, Gio, GLib  # type: ignore

from .entity import LibraryDB
from .entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from .entity.time_read import TIME_READ_WAY_LISTEN
from .preferences import PreferencesDialog
from .servers.legado import (LegadoServer, get_legado_sync_book_n,
                             get_legado_sync_config,
                             get_legado_sync_url, sync_legado_books)
from .servers.txt import TxtServer
from .tts.server_android import TtsSA
from .utils import PACKAGE_URL, open_url
from .utils.check_update import main as check_update
from .utils.debug import get_gtk_msg
from .window import HeartaleWindow


class HeartaleApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self, version, app_id):
        super().__init__(application_id=app_id,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/cool/ldr/heartale')
        self.version = version
        self.win = None
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)
        self.create_action('find_update', self.find_update)
        self.find_update()

    def do_activate(self):
        """Called when the application is activated.
        We raise the application's main window, creating it if
        necessary.

        Raises:
            the: _description_
        """
        self.win = self.props.active_window
        if not self.win:
            self.win = HeartaleWindow(application=self)
        self.win.present()

    def on_about_action(self, *_args):
        """Callback for the app.about actio
        """
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
        """Open the preferences dialog."""
        dialog = PreferencesDialog()
        dialog.present(self.props.active_window)

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

    def update_app(self, update_msg, title=None):
        """Display update information to the user."""

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
        """Check whether a new application version is available."""

        def fu():
            """Worker thread that checks for updates."""
            update_msg = check_update(self.version)
            if update_msg is not None:
                GLib.idle_add(self.update_app, update_msg)
            elif widget_no_auto:
                # Manual update request
                s = _("There is no new version."
                      "\nThe current version is {version}."
                      "\nYou can go to {url} to view the beta version.") \
                    .format(self.version, PACKAGE_URL)
                GLib.idle_add(self.update_app, s, _("No new version found"))

        threading.Thread(target=fu, daemon=True).start()


def main(version, app_id):
    """The application's entry point."""
    argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description=_("heartale CLI options"),
    )

    parser.add_argument(
        "--read-first",
        action="store_true",
        help=_("Read the first book in the bookshelf (same as --read-book 1)."),
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=12,
        help=_("Preview character count shown for each paragraph while reading."),
    )

    parser.add_argument(
        "--list-books",
        action="store_true",
        help=_("Print bookshelf list in CLI mode."),
    )
    parser.add_argument("--read-book", type=int, default=0,
                        help=_("Read the Nth book from bookshelf (1-based index)."))

    parser.add_argument(
        "--sync-legado",
        action="store_true",
        help=_("Sync books from Legado into local bookshelf."),
    )
    parser.add_argument(
        "--legado-url",
        type=str,
        default="",
        help=_("Legado server URL used for sync (e.g. http://192.168.1.34:1221)."),
    )
    parser.add_argument(
        "--legado-book-n",
        type=int,
        default=0,
        help=_("How many books to sync from Legado; 0 means use saved setting."),
    )

    parser.add_argument(
        "--tts-url",
        type=str,
        default="",
        help=_("TTS API URL (e.g. http://192.168.1.34:1221/api/tts)."),
    )
    parser.add_argument(
        "--tts-engine",
        type=str,
        default="",
        help=_("TTS engine name (e.g. com.xiaomi.mibrain.speech)."),
    )
    parser.add_argument(
        "--tts-rate",
        type=int,
        default=None,
        help=_("TTS speaking rate, range 0-100."),
    )
    parser.add_argument(
        "--tts-pitch",
        type=int,
        default=None,
        help=_("TTS pitch, range 0-100."),
    )
    parser.add_argument(
        "--show-settings",
        action="store_true",
        help=_("Print current saved settings (TTS/Legado/Reader) and exit unless reading is requested."),
    )

    cli_args, remaining_argv = parser.parse_known_args(argv)

    if argv:
        return _run_cli(cli_args)

    app = HeartaleApplication(version, app_id)
    print(version)
    return app.run([sys.argv[0], *remaining_argv])


def _run_cli(cli_args) -> int:
    preview_chars = max(1, int(cli_args.preview_chars))

    code = _persist_tts_overrides_cli(cli_args)
    if code != 0:
        return code

    if cli_args.sync_legado:
        code = _run_sync_legado_cli(cli_args)
        if code != 0:
            return code

    if cli_args.show_settings:
        _print_settings_cli()

    if cli_args.list_books:
        _print_bookshelf_cli()

    read_index = 0
    if cli_args.read_book > 0:
        read_index = cli_args.read_book
    elif cli_args.read_first:
        read_index = 1

    if read_index > 0:
        return _run_read_book_cli(read_index, preview_chars, cli_args)

    return 0


def _run_sync_legado_cli(cli_args) -> int:
    url = cli_args.legado_url.strip() or get_legado_sync_url()
    if not url:
        print(_("Legado URL is empty. Set one in preferences or use --legado-url"))
        return 2

    book_n = int(cli_args.legado_book_n) if cli_args.legado_book_n > 0 else get_legado_sync_book_n()
    sync_ok, s_error = sync_legado_books(book_n=book_n, url_base=url)
    print(_("Legado sync URL: {url}").format(url=url))
    print(_("Legado sync count: {count}").format(count=book_n))
    if s_error.strip():
        print(s_error.strip())
    return 0 if sync_ok else 2


def _print_bookshelf_cli():
    db = LibraryDB()
    try:
        books = list(db.iter_books())
    finally:
        db.close()

    if not books:
        print(_("No books found in library"))
        return

    print(_("Bookshelf:"))
    for idx, book in enumerate(books, start=1):
        print(
            _("{idx}. [{fmt}] {name} - {author} (chapter {chap_n}/{chap_all})").format(
                idx=idx,
                fmt=_fmt_name(book),
                name=book.name,
                author=book.author,
                chap_n=book.chap_n + 1,
                chap_all=book.chap_all,
            )
        )


def _fmt_name(book: Book) -> str:
    if book.fmt == BOOK_FMT_LEGADO:
        return "legado"
    if book.fmt == BOOK_FMT_TXT:
        return "txt"
    return str(book.fmt)


def _get_book_by_index(idx: int) -> Book | None:
    db = LibraryDB()
    try:
        books = list(db.iter_books())
        if idx < 1 or idx > len(books):
            return None
        selected = books[idx - 1]
        return db.get_book_by_md5(selected.md5) or selected
    finally:
        db.close()


def _apply_tts_overrides(tts: TtsSA, cli_args) -> None:
    kwargs = {}
    if cli_args.tts_url:
        kwargs["url_base"] = cli_args.tts_url
    if cli_args.tts_engine:
        kwargs["engine"] = cli_args.tts_engine
    if cli_args.tts_rate is not None:
        kwargs["rate"] = cli_args.tts_rate
    if cli_args.tts_pitch is not None:
        kwargs["pitch"] = cli_args.tts_pitch
    if kwargs:
        tts.update_config(**kwargs)


def _has_tts_overrides(cli_args) -> bool:
    return any([
        bool(cli_args.tts_url),
        bool(cli_args.tts_engine),
        cli_args.tts_rate is not None,
        cli_args.tts_pitch is not None,
    ])


def _persist_tts_overrides_cli(cli_args) -> int:
    if not _has_tts_overrides(cli_args):
        return 0
    tts = TtsSA()
    tts.reload_config()
    try:
        _apply_tts_overrides(tts, cli_args)
    except Exception as exc:  # pylint: disable=broad-except
        print(_("Invalid TTS config: {error}").format(error=exc))
        return 1
    return 0


def _print_settings_cli():
    tts = TtsSA()
    tts.reload_config()
    tts_cfg = tts.get_config()
    legado_cfg = get_legado_sync_config()

    db = LibraryDB()
    try:
        reader_cfg = db.get_config("reader_page", {})
    finally:
        db.close()

    print(_("Current settings:"))
    print(_("TTS:"))
    print(_("  url_base: {value}").format(value=tts_cfg.get("url_base", "")))
    print(_("  engine: {value}").format(value=tts_cfg.get("engine", "")))
    print(_("  rate: {value}").format(value=tts_cfg.get("rate", "")))
    print(_("  pitch: {value}").format(value=tts_cfg.get("pitch", "")))
    print(_("Legado:"))
    print(_("  url_base: {value}").format(value=legado_cfg.get("url_base", "")))
    print(_("  book_n: {value}").format(value=legado_cfg.get("book_n", "")))
    print(_("Reader:"))
    if isinstance(reader_cfg, dict) and reader_cfg:
        print(_("  font_size: {value}").format(value=reader_cfg.get("font_size", "")))
        print(_("  paragraph_space: {value}").format(
            value=reader_cfg.get("paragraph_space", "")))
        print(_("  line_space: {value}").format(value=reader_cfg.get("line_space", "")))
    else:
        print(_("  (not set)"))


def _run_read_book_cli(book_idx: int, preview_chars: int, cli_args) -> int:
    if not shutil.which("paplay"):
        print(_("paplay is not installed."))
        return 1

    book = _get_book_by_index(book_idx)
    if book is None:
        print(_("Book index out of range: {index}").format(index=book_idx))
        _print_bookshelf_cli()
        return 1

    if book.fmt == BOOK_FMT_LEGADO:
        server = LegadoServer()
    elif book.fmt == BOOK_FMT_TXT:
        server = TxtServer()
    else:
        print(_("Unsupported book format: {fmt}").format(fmt=book.fmt))
        return 1

    try:
        server.initialize(book)
    except Exception as exc:  # pylint: disable=broad-except
        print(_("Failed to initialize book: {error}").format(error=exc))
        return 1

    tts = TtsSA()
    tts.reload_config()
    try:
        _apply_tts_overrides(tts, cli_args)
        tts.reload_config()
    except Exception as exc:  # pylint: disable=broad-except
        print(_("Invalid TTS config: {error}").format(error=exc))
        return 1

    print(_("Book[{index}]: {name}").format(index=book_idx, name=server.book.name))
    print(_("Chapter: {chapter}").format(chapter=server.get_chap_name(server.get_chap_n())))

    while True:
        chap_txts = server.bd.chap_txts
        start_idx = max(0, min(server.bd.chap_txt_n, len(chap_txts) - 1)) if chap_txts else 0

        intro_texts = [
            (server.book.name or "").strip(),
            (server.get_chap_name(server.get_chap_n()) or "").strip(),
        ]
        for intro_text in intro_texts:
            if not intro_text:
                continue
            audio_path = tts.download(intro_text)
            if not audio_path:
                print(_("Read aloud failed. Remote TTS service may be unavailable."))
                return 2
            code = subprocess.run(["paplay", str(audio_path)], check=False).returncode
            if code != 0:
                print(_("Audio playback failed"))
                return 2

        for idx in range(start_idx, len(chap_txts)):
            text = (chap_txts[idx] or "").strip()
            if not text:
                continue

            compact_text = " ".join(text.split())
            preview = compact_text[:preview_chars]
            if len(compact_text) > preview_chars:
                preview += "..."
            print(_("[{current}/{total}] {preview}").format(
                current=idx + 1, total=len(chap_txts), preview=preview))

            audio_path = tts.download(text)
            if not audio_path:
                print(_("Read aloud failed. Remote TTS service may be unavailable."))
                return 2

            play_start = time.time()
            code = subprocess.run(["paplay", str(audio_path)], check=False).returncode
            play_seconds = max(0.0, time.time() - play_start)

            server.set_chap_txt_n(idx)
            server.save_read_progress(
                server.get_chap_n(),
                server.get_chap_txt_pos(),
                way=TIME_READ_WAY_LISTEN,
                seconds_override=play_seconds,
            )

            if code != 0:
                print(_("Audio playback failed"))
                return 2

        next_chap_n = server.book.chap_n + 1
        if next_chap_n >= len(server.chap_names):
            print(_("Finished all chapters"))
            return 0

        server.book.chap_n = next_chap_n
        server.book.chap_txt_pos = 0
        server.bd.chap_txt_n = 0
        server.bd.update_chap_txts(server.get_chap_txt(next_chap_n), 0)
        print(_("Chapter: {chapter}").format(chapter=server.get_chap_name(next_chap_n)))
