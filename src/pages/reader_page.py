# -*- coding: utf-8 -*-

import gi
from gi.repository import Adw, Gtk

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


@Gtk.Template(resource_path="/cool/ldr/heartale/reader_page.ui")
class ReaderPage(Adw.NavigationPage):
    __gtype_name__ = "ReaderPage"

    split: Adw.OverlaySplitView = Gtk.Template.Child()
    title: Adw.WindowTitle = Gtk.Template.Child()
    text: Gtk.TextView = Gtk.Template.Child()
    toc: Gtk.ListView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # reader_page.py 内新增
    def get_current_text(self, selection_only: bool = True) -> str:
        buf = self.text.get_buffer()
        if selection_only and buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            return buf.get_text(start, end, False)
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, False)

    def bind_toc(self, string_list: Gtk.StringList):
        factory = Gtk.SignalListItemFactory()

        def setup(_f, li):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            lbl.set_margin_start(12)
            lbl.set_margin_end(12)
            li.set_child(lbl)

        def bind(_f, li):
            lbl: Gtk.Label = li.get_child()
            sobj: Gtk.StringObject = li.get_item()
            lbl.set_text(sobj.get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        self.toc.set_factory(factory)
        self.toc.set_model(Gtk.SingleSelection.new(string_list))
