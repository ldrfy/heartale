"""main"""
import argparse
import shutil
import subprocess
import sys
import time
from gettext import gettext as _

from .entity import LibraryDB
from .entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from .entity.time_read import TIME_READ_WAY_LISTEN
from .servers.legado import (LegadoServer, get_legado_sync_book_n,
                             get_legado_sync_config,
                             get_legado_sync_url, sync_legado_books)
from .servers.txt import TxtServer
from .tts.server_android import TtsSA


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

    if cli_args.gui:
        from .gui_app import run_gui_app
        return run_gui_app(version, app_id, remaining_argv)

    return _run_cli(cli_args)


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
