"""main"""
import argparse
import sys
from gettext import gettext as _

from .cli_reader import run_read_book_cli
from .entity import LibraryDB
from .entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from .servers.legado import (get_legado_sync_book_n, get_legado_sync_config,
                             get_legado_sync_url, sync_legado_books)
from .tts import THS
from .tts.backends import (apply_active_tts_overrides, build_active_tts_override_kwargs,
                           create_active_tts_backend)


def main(version, app_id):
    """The application's entry point."""
    argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description=_("heartale CLI options"),
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help=_("Start GTK UI mode."),
    )

    parser.add_argument(
        "--list-books",
        action="store_true",
        help=_("Print bookshelf list in CLI mode."),
    )

    parser.add_argument("--read-book", type=int, default=0,
                        help=_("Read the Nth book from bookshelf (1-based index)."))

    parser.add_argument(
        "--preview-chars",
        type=int,
        default=12,
        help=_("Preview character count shown for each paragraph while reading."),
    )

    parser.add_argument(
        "--legado-sync",
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
        "--tts-android-url",
        type=str,
        dest="tts_android_url",
        default="",
        help=_("Android TTS API URL (e.g. http://192.168.1.34:1221/api/tts)."),
    )
    parser.add_argument(
        "--tts-android-engine",
        type=str,
        dest="tts_android_engine",
        default="",
        help=_("Android TTS engine name (e.g. com.xiaomi.mibrain.speech)."),
    )
    parser.add_argument(
        "--tts-android-rate",
        type=int,
        dest="tts_android_rate",
        default=None,
        help=_("Android TTS speaking rate, range 0-100."),
    )
    parser.add_argument(
        "--tts-android-pitch",
        type=int,
        dest="tts_android_pitch",
        default=None,
        help=_("Android TTS pitch, range 0-100."),
    )
    parser.add_argument(
        "--show-settings",
        action="store_true",
        help=_(
            "Print current saved settings (TTS/Legado/Reader) and exit "
            "unless reading is requested."
        ),
    )

    if not argv:
        parser.print_help()
        return 0

    cli_args, remaining_argv = parser.parse_known_args(argv)

    if cli_args.gui:
        # GTK UI is imported lazily so CLI-only usage does not require GUI startup.
        # pylint: disable=import-outside-toplevel
        from .gui_app import run_gui_app
        return run_gui_app(version, app_id, remaining_argv)

    return _run_cli(cli_args)


def _run_cli(cli_args) -> int:
    preview_chars = max(1, int(cli_args.preview_chars))

    code = _persist_tts_overrides_cli(cli_args)
    if code != 0:
        return code

    if cli_args.legado_sync:
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

    if read_index > 0:
        return run_read_book_cli(read_index, preview_chars, cli_args, _print_bookshelf_cli)

    return 0


def _run_sync_legado_cli(cli_args) -> int:
    url = cli_args.legado_url.strip() or get_legado_sync_url()
    if not url:
        print(_("Legado URL is empty. Set one in preferences or use --legado-url"))
        return 2

    book_n = int(
        cli_args.legado_book_n) if cli_args.legado_book_n > 0 else get_legado_sync_book_n()
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


def _apply_tts_overrides(tts: THS, cli_args) -> None:
    apply_active_tts_overrides(tts, cli_args)


def _has_tts_overrides(cli_args) -> bool:
    return bool(build_active_tts_override_kwargs(cli_args))


def _persist_tts_overrides_cli(cli_args) -> int:
    if not _has_tts_overrides(cli_args):
        return 0
    tts = create_active_tts_backend()
    tts.reload_config()
    try:
        _apply_tts_overrides(tts, cli_args)
    except Exception as exc:  # pylint: disable=broad-except
        print(_("Invalid TTS config: {error}").format(error=exc))
        return 1
    return 0


def _print_settings_cli():
    tts = create_active_tts_backend()
    tts.reload_config()
    tts_cfg = tts.get_config()
    legado_cfg = get_legado_sync_config()

    db = LibraryDB()
    try:
        reader_cfg = db.get_config("reader_page", {})
    finally:
        db.close()

    print(_("Current settings:"))
    print(_("TTS-Android:"))
    print(_("  url_base: {value}").format(value=tts_cfg.get("url_base", "")))
    print(_("  engine: {value}").format(value=tts_cfg.get("engine", "")))
    print(_("  rate: {value}").format(value=tts_cfg.get("rate", "")))
    print(_("  pitch: {value}").format(value=tts_cfg.get("pitch", "")))
    print(_("Legado:"))
    print(_("  url_base: {value}").format(
        value=legado_cfg.get("url_base", "")))
    print(_("  book_n: {value}").format(value=legado_cfg.get("book_n", "")))
    print(_("Reader:"))
    if isinstance(reader_cfg, dict) and reader_cfg:
        print(_("  font_size: {value}").format(
            value=reader_cfg.get("font_size", "")))
        print(_("  paragraph_space: {value}").format(
            value=reader_cfg.get("paragraph_space", "")))
        print(_("  line_space: {value}").format(
            value=reader_cfg.get("line_space", "")))
    else:
        print(_("  (not set)"))
