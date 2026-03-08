"""main"""
import argparse
import sys
from gettext import gettext as _
from pathlib import Path

from .cli_reader import run_read_book_cli
from .entity import LibraryDB
from .entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from .servers.legado import (get_legado_sync_book_n, get_legado_sync_config,
                             get_legado_sync_url, sync_legado_books)
from .servers.txt import (TXT_PARSE_PRESETS, get_txt_parse_config, path2book,
                          set_txt_parse_config)
from .tts import THS
from .tts.backends import (apply_active_tts_overrides,
                           build_active_tts_override_kwargs,
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
            "Print current saved settings (TTS/Legado/TXT/Reader) and exit "
            "unless reading is requested."
        ),
    )
    parser.add_argument(
        "--txt-import",
        nargs="+",
        dest="txt_import",
        default=[],
        help=_("Import one or more TXT files into the local bookshelf."),
    )
    parser.add_argument(
        "--txt-volume-pattern",
        type=str,
        default="",
        help=_("Primary TXT volume pattern used for chapter parsing."),
    )
    parser.add_argument(
        "--txt-chapter-pattern",
        type=str,
        default="",
        help=_("Primary TXT chapter pattern used for chapter parsing."),
    )
    parser.add_argument(
        "--txt-parse-language",
        type=str,
        default="",
        help=_("Use a built-in TXT parse preset by language code (e.g. zh_CN, en_US)."),
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

    code = _persist_txt_parse_overrides_cli(cli_args)
    if code != 0:
        return code

    if cli_args.legado_sync:
        code = _run_sync_legado_cli(cli_args)
        if code != 0:
            return code

    if cli_args.txt_import:
        code = _run_import_txt_cli(cli_args.txt_import)
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


def _has_txt_parse_overrides(cli_args) -> bool:
    """判断是否传入了 TXT 解析规则覆盖项。

    Args:
        cli_args: 命令行参数对象

    Returns:
        bool: 是否传入了 TXT 解析规则覆盖项
    """
    return bool(
        cli_args.txt_parse_language.strip()
        or cli_args.txt_volume_pattern.strip()
        or cli_args.txt_chapter_pattern.strip()
    )


def _build_txt_parse_override_kwargs(cli_args) -> dict:
    """构造 TXT 解析规则覆盖参数。

    Args:
        cli_args: 命令行参数对象

    Returns:
        dict: TXT 解析规则覆盖参数
    """
    kwargs = {}
    preset = cli_args.txt_parse_language.strip()
    if preset:
        kwargs.update(TXT_PARSE_PRESETS[preset])

    if cli_args.txt_volume_pattern.strip():
        kwargs["volume_pattern"] = cli_args.txt_volume_pattern.strip()
    if cli_args.txt_chapter_pattern.strip():
        kwargs["chapter_pattern"] = cli_args.txt_chapter_pattern.strip()
    return kwargs


def _persist_txt_parse_overrides_cli(cli_args) -> int:
    """保存命令行传入的 TXT 解析规则覆盖项。

    Args:
        cli_args: 命令行参数对象

    Returns:
        int: 命令行退出码
    """
    preset = cli_args.txt_parse_language.strip()
    if preset and preset not in TXT_PARSE_PRESETS:
        print(
            _("Invalid TXT parse language: {value}. Available presets: {presets}").format(
                value=preset,
                presets=", ".join(TXT_PARSE_PRESETS.keys()),
            )
        )
        return 1

    if not _has_txt_parse_overrides(cli_args):
        return 0
    try:
        set_txt_parse_config(**_build_txt_parse_override_kwargs(cli_args))
    except Exception as exc:  # pylint: disable=broad-except
        print(_("Invalid TXT parse config: {error}").format(error=exc))
        return 1
    return 0


def _run_import_txt_cli(paths: list[str]) -> int:
    """导入命令行指定的 TXT 文件。

    Args:
        paths (list[str]): 待导入的文件路径列表

    Returns:
        int: 命令行退出码
    """
    books = []
    errors = []
    for raw_path in paths:
        try:
            books.append(path2book(raw_path))
        except (FileNotFoundError, OSError, ValueError, IndexError) as exc:
            errors.append(
                _("{name}: {error}").format(
                    name=Path(raw_path).name,
                    error=exc,
                )
            )

    if books:
        db = LibraryDB()
        try:
            for book in books:
                db.save_book(book)
        finally:
            db.close()
        print(_("Books imported successfully"))

    if errors:
        print(_("Import partially failed"))
        for error in errors:
            print(error)
        return 1

    return 0


def _print_settings_cli():
    tts = create_active_tts_backend()
    tts.reload_config()
    tts_cfg = tts.get_config()
    legado_cfg = get_legado_sync_config()
    txt_cfg = get_txt_parse_config()

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
    print(_("TXT:"))
    print(_("  volume_pattern: {value}").format(
        value=txt_cfg.get("volume_pattern", "")))
    print(_("  chapter_pattern: {value}").format(
        value=txt_cfg.get("chapter_pattern", "")))
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
