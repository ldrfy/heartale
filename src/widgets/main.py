#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
from gi.repository import GLib, Gtk, Pango

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from pg_tag_view import ParagraphTagController


# =========================
# Demo 窗口：展示如何联动控制
# =========================
class DemoWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Paragraph Tag Demo")
        self.set_default_size(900, 600)

        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )
        self.set_child(root)

        # 控制条
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(controls)

        # 字体大小
        controls.append(Gtk.Label(label="字体(pt):"))
        self.font_spin = Gtk.SpinButton.new_with_range(6, 72, 1)
        self.font_spin.set_value(14)
        controls.append(self.font_spin)

        # 行间距（像素）
        controls.append(Gtk.Label(label="行间距(px):"))
        self.line_spin = Gtk.SpinButton.new_with_range(0, 60, 1)
        self.line_spin.set_value(4)
        controls.append(self.line_spin)

        # 段前/段后 间距（像素）
        controls.append(Gtk.Label(label="段前(px):"))
        self.above_spin = Gtk.SpinButton.new_with_range(0, 80, 1)
        self.above_spin.set_value(6)
        controls.append(self.above_spin)

        controls.append(Gtk.Label(label="段后(px):"))
        self.below_spin = Gtk.SpinButton.new_with_range(0, 80, 1)
        self.below_spin.set_value(6)
        controls.append(self.below_spin)

        # 当前可视段
        self.visible_lbl = Gtk.Label(label="可视段: -")
        controls.append(self.visible_lbl)

        # 主区：ScrolledWindow + TextView
        self.scroller = Gtk.ScrolledWindow()
        root.append(self.scroller)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.scroller.set_child(self.textview)

        # 控制器
        self.controller = ParagraphTagController(self.textview, self.scroller)

        # 回调：点击高亮段（仅打印，不改变“可视段”逻辑）
        def on_click(idx, tag_name, s, e):
            print(f"[CLICK] idx={idx} tag={tag_name} range=({s},{e})")
        self.controller.set_on_paragraph_click(on_click)

        # 回调：滚动可视段变化 -> 顶部标签显示
        def on_visible(idx):
            self.visible_lbl.set_text(f"可视段: {idx}")
        self.controller.set_on_visible_paragraph_changed(on_visible)

        # 绑定控件 -> 实时生效
        self.font_spin.connect("value-changed", self._on_font_changed)
        self.line_spin.connect("value-changed", self._on_line_changed)
        self.above_spin.connect("value-changed", self._on_parasp_changed)
        self.below_spin.connect("value-changed", self._on_parasp_changed)

        # 加载示例段落
        sample = [
            "这是一段示例文本，用于展示段落索引与点击高亮的效果。",
            "第二段：点击任意位置将高亮所在段，但滚动不会改变高亮，只会在上方状态栏显示当前可视段。",
            "第三段：你可以通过上方控件动态调整字体大小、行间距与段前/段后间距。",
            "第四段：滚动时，控制器会取可视区域顶部附近的位置计算其 offset，并二分命中段索引。",
            "第五段：scroll_to_paragraph(idx, center=False) 与既有滚动代码兼容，内部使用 scroll_to_iter 与 idle 调度保证可靠性。",
            "第六段：layout_tag 通过 pixels_inside_wrap / pixels_above_lines / pixels_below_lines 控制行/段间距。",
            "第七段：字体大小通过 CSS Provider 统一设置 textview { font-size: Npt; }，随调随生效。",
            "第八段：需要更精细的样式时，你也可以为不同段单独创建 TextTag 并局部应用。",
            "第九段：如果你已有段落数据结构，直接调用 set_paragraphs(list[str]) 即可完成索引与标注。",
            "第十段：祝使用顺利。",
        ]
        self.controller.set_paragraphs(sample)

        # 初始应用一次控件值
        self._apply_all_style_from_controls()

    # 控件回调
    def _on_font_changed(self, spin):
        self.controller.set_font_size_pt(int(spin.get_value()))

    def _on_line_changed(self, spin):
        self.controller.set_line_spacing(int(spin.get_value()))

    def _on_parasp_changed(self, _spin):
        self.controller.set_paragraph_spacing(
            int(self.above_spin.get_value()),
            int(self.below_spin.get_value()),
        )

    def _apply_all_style_from_controls(self):
        self._on_font_changed(self.font_spin)
        self._on_line_changed(self.line_spin)
        self._on_parasp_changed(None)


# =========================
# Application 入口
# =========================
class DemoApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="cn.yuh.ParagraphTagDemo")

    def do_activate(self):
        win = DemoWindow(self)
        win.present()


def main():
    app = DemoApp()
    app.run()


if __name__ == "__main__":
    main()
