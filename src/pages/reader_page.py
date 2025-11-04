"""Reader page."""

import copy
import threading
import time
import traceback

from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity import LibraryDB
from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from ..servers import Server
from ..servers.legado import LegadoServer
from ..servers.txt import TxtServer
from ..utils.debug import get_logger
from ..widgets.pg_tag_view import ParagraphTagController


@Gtk.Template(resource_path="/cool/ldr/heartale/reader_page.ui")
class ReaderPage(Adw.NavigationPage):
    """Navigation page that displays the reader view."""
    __gtype_name__ = "ReaderPage"

    btn_prev_chap: Gtk.Button = Gtk.Template.Child()
    btn_next_chap: Gtk.Button = Gtk.Template.Child()

    # These IDs must match the ones defined in the .ui files
    title: Adw.WindowTitle = Gtk.Template.Child()
    gtv_text: Gtk.TextView = Gtk.Template.Child()
    gsw_text: Gtk.ScrolledWindow = Gtk.Template.Child()

    toc: Gtk.ListView = Gtk.Template.Child()
    gse_toc: Gtk.SearchEntry = Gtk.Template.Child()
    btn_show_search: Gtk.ToggleButton = Gtk.Template.Child()

    stack: Adw.ViewStack = Gtk.Template.Child()

    spinner_sync: Gtk.Spinner = Gtk.Template.Child()

    aos_reader: Adw.OverlaySplitView = Gtk.Template.Child()
    page_error: Adw.StatusPage = Gtk.Template.Child()
    page_loading: Adw.StatusPage = Gtk.Template.Child()

    ga_f: Gtk.Adjustment = Gtk.Template.Child()
    ga_l: Gtk.Adjustment = Gtk.Template.Child()
    ga_p: Gtk.Adjustment = Gtk.Template.Child()

    glb_chap_txt_n: Gtk.Label = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, **kwargs):
        super().__init__(**kwargs)

        self._nav = nav
        self.t = 0
        self._toc_sel: Gtk.SingleSelection = None
        self.chap_ns = []

        self._search_debounce_id = 0

        self._server: Server = None

        self._build_factory()

        self.ptc = ParagraphTagController(self.gtv_text, self.gsw_text)
        self.ptc.set_on_paragraph_click(self._on_click_paragraph)
        self.ptc.set_on_visible_paragraph_changed(self._set_read_jd)

    def clear_data(self):
        """Reset cached server data and show the loading page."""
        self._server = None
        self._toc_sel = None
        self.chap_ns = []
        self.ptc.clear()
        self.stack.set_visible_child(self.page_loading)

    def set_data(self, book: Book):
        """Load ``book`` data in a worker thread and update the UI."""
        self.t = time.time()
        self._search_debounce_id = 0

        self.btn_prev_chap.set_sensitive(True)
        self.btn_next_chap.set_sensitive(True)
        self._on_set_default()
        self._on_search_toc_stop()

        self.title.set_title(book.name or "")
        self.title.set_subtitle(book.get_jd_str())

        self.clear_data()

        def update_ui(_b: Book, err: Exception):
            """Handle worker errors on the main thread."""
            if _b.md5 != self._server.book.md5:
                get_logger().info("Book switched, ignoring error display")
                return False
            self.show_error(
                _(
                    "Unable to open this book or its table of contents."
                    "\n{title}: {path}"
                    "\n\nTry again or go back:\n{error}"
                ).format(title=_b.name, path=_b.get_path(), error=err)
            )
            return False

        def worker(_book: Book):
            try:

                db = LibraryDB()
                book = db.get_book_by_md5(_book.md5)
                db.close()

                self._server = self._get_server(book.fmt)
                self._server.initialize(book)

                if time.time() - self.t < 0.5:
                    time.sleep(0.5 - (time.time() - self.t))
                GLib.idle_add(self._on_data_ready, _book,
                              priority=GLib.PRIORITY_DEFAULT)
            except Exception as e:  # pylint: disable=broad-except
                s = f"Failed to load book: {e}\n{traceback.format_exc()}"
                get_logger().error(s)
                if time.time() - self.t < 0.5:
                    time.sleep(0.5 - (time.time() - self.t))
                GLib.idle_add(update_ui, _book, s,
                              priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, args=(book,), daemon=True).start()

    def _get_server(self, fmt: str):

        if fmt == BOOK_FMT_LEGADO:
            return LegadoServer()
        if fmt == BOOK_FMT_TXT:
            return TxtServer()

        raise ValueError(f"Unsupported book format {fmt}")

    def _locate_toc(self, chap_n: int):
        """Select the chapter ``chap_n`` in the table of contents."""
        if not self._toc_sel:
            return
        self._toc_sel.set_selected(chap_n)
        self.toc.scroll_to(chap_n, Gtk.ListScrollFlags.FOCUS,
                           Gtk.ScrollInfo())

    def _on_data_ready(self, _b: Book):
        """Bind the table of contents and chapter text on the main thread."""

        if _b.md5 != self._server.book.md5:
            get_logger().info("Book switched, ignoring error display")
            return False

        self.stack.set_visible_child(self.aos_reader)

        self._apply_search()

        self.set_chap_text()

        def sel_chap_name():
            """Select the current chapter in the table of contents."""
            self._locate_toc(self._server.get_chap_n())

        GLib.timeout_add(500, sel_chap_name)

        return False

    def show_error(self, des=None):
        """Show the error page with ``des`` as the description."""
        if des is None:
            des = _("Unable to open this book or its table of contents. Please try again or go back.")
        self.stack.set_visible_child(self.page_error)
        self.page_error.set_description(des)

    def set_chap_text(self, _chap_n=-1):
        """Update the reader with chapter ``_chap_n``.

        Args:
            chap_n (int): Chapter index
        """

        self.btn_prev_chap.set_sensitive(False)
        self.btn_next_chap.set_sensitive(False)

        self.spinner_sync.start()

        def _ui_update(chap_name):
            self.title.set_subtitle(
                f"{chap_name} ({self._server.book.chap_n}/{self._server.book.chap_all})")

            self.ptc.set_paragraphs(self._server.bd.chap_txts)
            self.ptc.scroll_to_paragraph(self._server.bd.chap_txt_n)
            self.ptc.highlight_paragraph(self._server.bd.chap_txt_n)
            self.spinner_sync.stop()

            self.glb_chap_txt_n.set_text(f"{self._server.bd.chap_txt_n + 1}/{len(self._server.bd.chap_txts)}")

            self.btn_prev_chap.set_sensitive(True)
            self.btn_next_chap.set_sensitive(True)

        def worker(chap_n):
            if chap_n > 0:
                # Skip updates during the initial load
                self._server.save_read_progress(chap_n, 0)

            chap_name = self._server.get_chap_name(chap_n)

            self._server.bd.update_chap_txts(
                self._server.get_chap_txt(chap_n),
                self._server.book.chap_txt_pos)

            GLib.idle_add(_ui_update, chap_name,
                          priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, args=(_chap_n,), daemon=True).start()

    def get_current_text(self, selection_only: bool = True) -> str:
        """Return the current text selection or the entire chapter.

        Args:
            selection_only (bool, optional): Whether to prefer the selection. Defaults to True.

        Returns:
            str: Extracted text
        """
        buf = self.gtv_text.get_buffer()
        if selection_only and buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            return buf.get_text(start, end, False)
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, False)

    def _build_factory(self):
        """Initialise the list factory once."""
        factory = Gtk.SignalListItemFactory()

        def setup(_f, li):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            lbl.set_margin_start(12)
            lbl.set_margin_end(12)
            lbl.set_ellipsize(3)
            li.set_child(lbl)

        def bind(_f, li):
            lbl: Gtk.Label = li.get_child()
            sobj: Gtk.StringObject = li.get_item()
            lbl.set_text(sobj.get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)

        self.toc.set_factory(factory)

        def on_activate(_listview, position):
            self._on_toc_chapter_activated(int(position))

        self.toc.connect("activate", on_activate)

    def _on_toc_chapter_activated(self, i: int):
        """Handle a chapter activation from the table of contents."""
        try:
            self.set_chap_text(self.chap_ns[i])
            # Optionally update the title/subtitle
        except Exception as e:  # pylint: disable=broad-except
            get_logger().error("Failed to switch chapter: %s", e)
            self.show_error(_("Failed to switch chapter: {error}").format(error=e))

    def _on_click_paragraph(self, idx: int, *_args):
        """Handle a paragraph click inside the reader.

        Args:
            idx (int): Paragraph index
            tag_name (str): Paragraph tag name
            start_off (int): Paragraph start offset
            end_off (int): Paragraph end offset
        """
        self._set_read_jd(idx, False)

        self.ptc.highlight_paragraph(idx)

    def _set_read_jd(self, idx, add=True):
        """Update reading progress with the current paragraph index.

        Args:
            idx (_type_): Paragraph index
        """

        if self._server.bd.chap_txt_n > idx and add:
            # Auto-scrolling to the previous position keeps firing for a few seconds
            # This prevents saving progress when the user scrolls backwards
            return

        def worker():
            self.glb_chap_txt_n.set_text(f"{idx + 1}/{len(self._server.bd.chap_txts)}")
            self._server.set_chap_txt_n(idx)
            self._server.save_read_progress(self._server.get_chap_n(),
                                            self._server.get_chap_txt_pos())

        threading.Thread(target=worker, daemon=True).start()

    @Gtk.Template.Callback()
    def _on_read_aloud(self, *_args):
        text = self.get_current_text(selection_only=True)
        if not text:
            text = self.get_current_text(selection_only=False)
        # Print for now; can be replaced with real TTS later
        print("[TTS] Reading content:")
        # Truncate to avoid flooding the console
        print(text[:400])

    @Gtk.Template.Callback()
    def _on_cancel_load_book(self, *_args):
        self._nav.pop()  # Return to the bookshelf page

    @Gtk.Template.Callback()
    def _on_retry_load(self, *_args):
        self.set_data(self._server.book)  # Retry loading the current book

    @Gtk.Template.Callback()
    def _on_next_chap(self, *_args):
        if self._server.book.chap_n + 1 >= len(self._server.chap_names):
            self.get_root().toast_msg(_("You have reached the last chapter."))
            return
        self._server.book.chap_n += 1
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self._on_toc_chapter_activated(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_last_chap(self, *_args):
        if self._server.book.chap_n - 1 <= 0:
            self.get_root().toast_msg(_("You are already at the first chapter."))
            return
        self._server.book.chap_n -= 1
        self._server.book.chap_txt_pos = 0
        self._server.bd.chap_txt_n = 0
        self._on_toc_chapter_activated(self._server.book.chap_n)
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_fontsize_changed(self, b) -> None:
        """Adjust font size.

        Args:
            spin (Adw.SpinRow): Spin row
            value (_type_): New value
        """
        if isinstance(b, Adw.SpinRow):
            v = b.get_value()
        else:
            v = b
        self.ptc.set_font_size_pt(v)

    @Gtk.Template.Callback()
    def _on_paragraph_space_changed(self, b) -> None:
        """Adjust paragraph spacing.

        Args:
            spin (Adw.SpinRow): Spin row
            value (_type_): New value
        """
        if isinstance(b, Adw.SpinRow):
            v = b.get_value()
        else:
            v = b
        self.ptc.set_paragraph_spacing(0, v)

    @Gtk.Template.Callback()
    def _on_line_space_changed(self, b) -> None:
        """Adjust line spacing.

        Args:
            spin (Adw.SpinRow): Spin row
            value (_type_): New value
        """
        if isinstance(b, Adw.SpinRow):
            v = b.get_value()
        else:
            v = b
        self.ptc.set_line_spacing(int(v))

    @Gtk.Template.Callback()
    def _on_click_title(self, *_args) -> None:
        """Scroll the table of contents to the current chapter.

        Args:
            spin (Adw.SpinRow): Spin row
            value (_type_): New value
        """
        self._locate_toc(self._server.get_chap_n())

    @Gtk.Template.Callback()
    def _on_search_toc_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
        self._search_debounce_id = GLib.timeout_add(500, self._apply_search,
                                                    entry.get_text().strip())

    @Gtk.Template.Callback()
    def _on_search_toc_stop(self, *_) -> None:
        self.gse_toc.set_text("")
        self.btn_show_search.set_active(False)

        if not self._server:
            return

        self._apply_search()

    def _apply_search(self, kw_=""):

        def update_ui():
            self.toc.set_model(self._toc_sel)
            return False

        def worker(kw):
            self._search_debounce_id = 0
            kw = kw.strip()
            if kw:
                self.chap_ns = []
                chap_names = []
                for i, name in enumerate(self._server.chap_names):
                    if kw not in name:
                        continue
                    self.chap_ns.append(i)
                    chap_names.append(name)
            else:
                chap_names = copy.deepcopy(self._server.chap_names)
                self.chap_ns = range(len(chap_names))

            self._toc_sel = Gtk.SingleSelection.new(
                Gtk.StringList.new(chap_names))

            GLib.idle_add(update_ui, priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, args=(kw_,), daemon=True).start()

        return False

    @Gtk.Template.Callback()
    def _on_show_search_toc(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            GLib.idle_add(self.gse_toc.grab_focus)

    @Gtk.Template.Callback()
    def _on_set_default(self, *_args) -> None:
        """Restore default reader settings."""
        self._on_fontsize_changed(14)
        self._on_line_space_changed(8)
        self._on_paragraph_space_changed(24)

        self.ga_f.set_value(14)
        self.ga_l.set_value(8)
        self.ga_p.set_value(24)
