import os
import signal
import sys
from datetime import datetime
from pathlib import Path
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf, Pango, XApp
from .store import Store
from .clipboard import Clipboard
from .paste import PasteController
from .settings import SettingsDialog

CSS = b'''
.shelf-root { padding: 18px; }
.shelf-title { font-size: 22px; font-weight: 700; }
.shelf-muted { opacity: 0.65; }
.shelf-small { font-size: 11px; }
.shelf-search { min-height: 36px; }
.shelf-list { background: transparent; }
.shelf-list row { border-radius: 9px; margin: 0 0 7px 0; padding: 0; }
.shelf-card { padding: 13px; border: 1px solid alpha(@theme_fg_color, 0.10); border-radius: 9px; background: alpha(@theme_fg_color, 0.035); }
.shelf-list row:selected .shelf-card { border-color: alpha(@theme_selected_bg_color, 0.7); background: alpha(@theme_selected_bg_color, 0.12); }
.shelf-type { font-size: 10px; font-weight: 700; letter-spacing: 1px; }
.shelf-preview { font-size: 13px; }
.shelf-icon { padding: 10px; border-radius: 8px; background: alpha(@theme_selected_bg_color, 0.14); color: @theme_selected_bg_color; }
.shelf-setting-title { font-weight: 600; }
.shelf-compact .shelf-card { padding: 7px 11px; }
.shelf-compact .shelf-icon { padding: 6px; }
.shelf-empty-title { font-size: 19px; font-weight: 600; }
'''


def label(text, css=None):
    widget = Gtk.Label(label=text, xalign=0)
    if css:
        for name in css.split():
            widget.get_style_context().add_class(name)
    return widget


def button(icon, tooltip, callback):
    b = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.set_tooltip_text(tooltip)
    b.connect('clicked', callback)
    return b


class ShelfWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Mint Shelf')
        self.app = app
        self.category = 'all'
        self.set_default_size(570, 690)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name('edit-paste')
        self.connect('delete-event', lambda *_: self.dismiss())
        self.connect('key-press-event', self.key)
        self.dialog_open = False
        header = Gtk.HeaderBar(show_close_button=True)
        header.set_title('Mint Shelf')
        self.set_titlebar(header)
        self.pause_button = button('media-playback-pause-symbolic', 'Pause clipboard capture', lambda *_: app.toggle_pause())
        header.pack_start(self.pause_button)
        menu = Gtk.MenuButton()
        menu.set_image(Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.BUTTON))
        menu.set_tooltip_text('Shelf options')
        popup = Gtk.Menu()
        for title, callback in [('Settings…', lambda *_: app.show_settings()), ('Clear unpinned history…', self.clear_history), ('About Mint Shelf', self.about), ('Quit Mint Shelf', lambda *_: app.quit())]:
            item = Gtk.MenuItem(label=title)
            item.connect('activate', callback)
            popup.append(item)
        popup.show_all()
        menu.set_popup(popup)
        header.pack_end(menu)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.get_style_context().add_class('shelf-root')
        self.add(root)
        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        intro.pack_start(label('Your clipboard, within reach.', 'shelf-title'), False, False, 0)
        self.instructions = label('', 'shelf-muted')
        intro.pack_start(self.instructions, False, False, 0)
        root.pack_start(intro, False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text='Search your clipboard…')
        self.search.get_style_context().add_class('shelf-search')
        self.search.connect('search-changed', lambda *_: self.refresh())
        root.pack_start(self.search, False, False, 0)
        filters = Gtk.Box(spacing=3)
        group = None
        for name, title in [('all', 'All'), ('text', 'Text'), ('image', 'Images'), ('link', 'Links'), ('files', 'Files'), ('pinned', 'Pinned')]:
            b = Gtk.RadioButton.new_with_label_from_widget(group, title)
            if group is None:
                group = b
            b.set_mode(False)
            b.connect('toggled', self.filter_changed, name)
            filters.pack_start(b, True, True, 0)
        root.pack_start(filters, False, False, 0)
        self.meta = label('', 'shelf-muted shelf-small')
        root.pack_start(self.meta, False, False, 0)
        self.stack = Gtk.Stack()
        root.pack_start(self.stack, True, True, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.set_activate_on_single_click(True)
        self.list.get_style_context().add_class('shelf-list')
        self.list.connect('row-activated', lambda _, row: self.choose(row))
        scroll.add(self.list)
        self.stack.add_named(scroll, 'items')
        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=13)
        empty.set_valign(Gtk.Align.CENTER)
        empty.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name('edit-paste-symbolic', Gtk.IconSize.DIALOG)
        icon.set_pixel_size(52)
        icon.get_style_context().add_class('shelf-muted')
        empty.pack_start(icon, False, False, 0)
        self.empty_title = label('A fresh start', 'shelf-empty-title')
        self.empty_title.set_xalign(0.5)
        empty.pack_start(self.empty_title, False, False, 0)
        self.empty_body = label('Copy some text, an image or a link.\nIt will be waiting here when you press Win+V.', 'shelf-muted')
        self.empty_body.set_justify(Gtk.Justification.CENTER)
        empty.pack_start(self.empty_body, False, False, 0)
        self.stack.add_named(empty, 'empty')
        root.pack_start(Gtk.Separator(), False, False, 0)
        foot = Gtk.Box()
        self.status = label('', 'shelf-muted shelf-small')
        foot.pack_start(self.status, True, True, 0)
        self.keys_hint = label('', 'shelf-muted shelf-small')
        foot.pack_end(self.keys_hint, False, False, 0)
        root.pack_start(foot, False, False, 0)
        self.refresh()

    def filter_changed(self, widget, category):
        if widget.get_active():
            self.category = category
            if hasattr(self, 'list'):
                self.refresh()

    def refresh(self):
        auto_paste = self.app.store.option('auto_paste')
        compact = self.app.store.option('compact')
        self.instructions.set_text('Choose an item to paste into your previous window.' if auto_paste else 'Choose an item to copy it. Paste with Ctrl+V.')
        self.keys_hint.set_text('↑↓ Navigate   ↵ ' + ('Paste' if auto_paste else 'Copy') + '   Esc Close')
        context = self.list.get_style_context()
        (context.add_class if compact else context.remove_class)('shelf-compact')
        selected = self.list.get_selected_row()
        selected_id = selected.clip_id if selected else None
        for row in self.list.get_children():
            self.list.remove(row)
        items = self.app.store.items(self.search.get_text(), self.category)
        for item in items:
            row = Gtk.ListBoxRow()
            row.clip_id = item['id']
            card = Gtk.Box(spacing=13)
            card.get_style_context().add_class('shelf-card')
            row.add(card)
            icons = {'text': 'text-x-generic-symbolic', 'link': 'web-browser-symbolic', 'files': 'folder-symbolic', 'image': 'image-x-generic-symbolic'}
            visual = Gtk.Image.new_from_icon_name(icons[item['kind']], Gtk.IconSize.DND)
            visual.set_pixel_size(24)
            visual.get_style_context().add_class('shelf-icon')
            visual.set_valign(Gtk.Align.START)
            if item['kind'] == 'image':
                try:
                    payload = self.app.store.payload(item['id'])
                    raw = next(v for k, v in payload.items() if k.startswith('image/'))
                    loader = GdkPixbuf.PixbufLoader.new()
                    loader.set_size(42, 36) if compact else loader.set_size(74, 62)
                    loader.write(raw)
                    loader.close()
                    visual.set_from_pixbuf(loader.get_pixbuf())
                except (GLib.Error, StopIteration):
                    pass
            card.pack_start(visual, False, False, 0)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            content.set_hexpand(True)
            top = Gtk.Box(spacing=8)
            top.pack_start(label(item['kind'].upper(), 'shelf-type shelf-muted'), False, False, 0)
            if item['pinned']:
                top.pack_start(label('• Pinned', 'shelf-small shelf-muted'), False, False, 0)
            date = datetime.fromtimestamp(item['created'])
            stamp = date.strftime('%H:%M') if date.date() == datetime.now().date() else date.strftime('%d %b')
            top.pack_end(label(stamp, 'shelf-small shelf-muted'), False, False, 0)
            content.pack_start(top, False, False, 0)
            preview = label(item['text'][:450].replace('\x00', ''), 'shelf-preview')
            preview.set_line_wrap(True)
            preview.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            preview.set_lines(1 if compact else 2)
            preview.set_ellipsize(Pango.EllipsizeMode.END)
            preview.set_max_width_chars(43)
            content.pack_start(preview, False, False, 0)
            detail = label(item['detail'], 'shelf-muted shelf-small')
            detail.set_ellipsize(Pango.EllipsizeMode.END)
            content.pack_start(detail, False, False, 0)
            card.pack_start(content, True, True, 0)
            actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            actions.pack_start(button('starred-symbolic' if item['pinned'] else 'non-starred-symbolic', 'Unpin item' if item['pinned'] else 'Pin item', lambda _, i=item['id']: self.pin(i)), False, False, 0)
            actions.pack_start(button('edit-delete-symbolic', 'Delete item', lambda _, i=item['id']: self.delete(i)), False, False, 0)
            card.pack_end(actions, False, False, 0)
            self.list.add(row)
            if row.clip_id == selected_id:
                self.list.select_row(row)
        self.list.show_all()
        if not self.list.get_selected_row() and items:
            self.list.select_row(self.list.get_row_at_index(0))
        self.stack.set_visible_child_name('items' if items else 'empty')
        total = len(self.app.store.items())
        self.meta.set_text(f'{len(items)} item' + ('s' if len(items) != 1 else '') + ('  ·  Pinned items stay at the top' if items else '  ·  Ready when you are'))
        filtered = bool(self.search.get_text() or self.category != 'all')
        self.empty_title.set_text('No matching items' if filtered else ('Capture is paused' if self.app.paused else 'A fresh start'))
        self.empty_body.set_text('Try another search or choose a different filter.' if filtered else ('Resume capture using the play button above.' if self.app.paused else 'Copy some text, an image or a link.\nIt will be waiting here when you press Win+V.'))
        self.status.set_text('Capture paused' if self.app.paused else f'●  Listening  ·  {total}/{self.app.store.option("max_items")} saved locally')
        self.pause_button.set_image(Gtk.Image.new_from_icon_name('media-playback-start-symbolic' if self.app.paused else 'media-playback-pause-symbolic', Gtk.IconSize.BUTTON))
        self.pause_button.set_tooltip_text('Resume clipboard capture' if self.app.paused else 'Pause clipboard capture')

    def pin(self, clip_id):
        self.app.store.pin(clip_id)
        self.refresh()

    def delete(self, clip_id):
        self.app.store.delete(clip_id)
        self.refresh()

    def choose(self, row):
        if row and self.app.clipboard.restore(self.app.store.payload(row.clip_id)):
            self.hide()
            if self.app.store.option('auto_paste'):
                self.app.paster.paste(lambda: self.app.clipboard.owned, self.app.paste_failed)

    def dismiss(self):
        self.hide()
        return True

    def key(self, _, event):
        key = event.keyval
        control = event.state & Gdk.ModifierType.CONTROL_MASK
        if key == Gdk.KEY_Escape:
            return self.dismiss()
        if control and key in (Gdk.KEY_f, Gdk.KEY_l):
            self.search.grab_focus()
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and (self.search.has_focus() or self.list.has_focus() or isinstance(self.get_focus(), Gtk.ListBoxRow)):
            self.choose(self.list.get_selected_row())
            return True
        if key in (Gdk.KEY_Down, Gdk.KEY_Up):
            row = self.list.get_selected_row()
            index = row.get_index() if row else -1
            target = self.list.get_row_at_index(max(0, index + (1 if key == Gdk.KEY_Down else -1)))
            if target:
                self.list.select_row(target)
                target.grab_focus()
            return True
        if control and key in (Gdk.KEY_p, Gdk.KEY_Delete):
            row = self.list.get_selected_row()
            if row:
                (self.pin if key == Gdk.KEY_p else self.delete)(row.clip_id)
            return True
        return False

    def clear_history(self, *_):
        self.dialog_open = True
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE, text='Clear clipboard history?')
        dialog.format_secondary_text('All unpinned items will be removed from this PC. Pinned items and the current clipboard are kept.')
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Clear history', Gtk.ResponseType.OK)
        result = dialog.run()
        dialog.destroy()
        self.dialog_open = False
        if result == Gtk.ResponseType.OK:
            self.app.store.clear()
            self.refresh()

    def about(self, *_):
        self.dialog_open = True
        dialog = Gtk.AboutDialog(transient_for=self, modal=True, program_name='Mint Shelf', version='1.0.0', logo_icon_name='edit-paste', comments='A quiet home for your clipboard.\n\nWin+V opens the shelf. Click an item or press Enter to paste.\nCtrl+P pins an item; Ctrl+Delete removes it.\n\nHistory stays on this PC, within your chosen limits / 64 MiB.\nItems over 16 MiB are skipped. Pause for private copying.\nRecognised password-manager formats are skipped.\nSaved file cuts are restored as copies.\nHistory is local and is not encrypted.', copyright='Mint Shelf · Built for Cinnamon')
        dialog.run()
        dialog.destroy()
        self.dialog_open = False


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.mintshelf.Clipboard', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.preferences_window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()
        self.store = Store(Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'mint-shelf')
        self.store.prune()
        GLib.timeout_add_seconds(60, self.expire_history)
        self.paused = self.store.setting('paused') == '1'
        self.clipboard = Clipboard(self.capture, lambda: self.paused)
        self.paster = PasteController()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.tray = XApp.StatusIcon()
        self.tray.set_name('Mint Shelf')
        self.tray.set_icon_name('edit-paste-symbolic')
        self.tray.set_tooltip_text('Mint Shelf · Win+V')
        self.tray.connect('activate', lambda *_: self.toggle())
        menu = Gtk.Menu()
        for title, action in [('Open clipboard shelf', lambda *_: self.toggle()), ('Pause / resume capture', lambda *_: self.toggle_pause()), ('Settings…', lambda *_: self.show_settings()), ('Quit', lambda *_: self.quit())]:
            item = Gtk.MenuItem(label=title)
            item.connect('activate', action)
            menu.append(item)
        menu.show_all()
        self.tray.set_secondary_menu(menu)
        self.update_tray()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.stop)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.stop)

    def stop(self):
        self.quit()
        return False

    def do_command_line(self, command):
        if '--quit' in command.get_arguments():
            self.quit()
        elif '--settings' in command.get_arguments():
            self.show_settings()
        elif '--background' not in command.get_arguments():
            self.toggle()
        return 0

    def do_activate(self):
        self.toggle()

    def toggle(self):
        if self.preferences_window:
            self.preferences_window.present()
            return
        if not self.window:
            self.window = ShelfWindow(self)
        if self.window.get_visible():
            self.window.hide()
        else:
            self.paster.remember()
            self.window.search.set_text('')
            self.window.refresh()
            self.window.show_all()
            self.window.present_with_time(Gdk.CURRENT_TIME)
            self.window.search.grab_focus()

    def show_settings(self):
        if self.preferences_window:
            self.preferences_window.present()
            return
        parent = self.window if self.window and self.window.get_visible() else None
        if parent:
            parent.dialog_open = True
        self.paster.cancel()
        self.preferences_window = SettingsDialog(self, parent)
        self.preferences_window.set_application(self)
        def closed(*_):
            self.preferences_window = None
            if parent:
                parent.dialog_open = False
                parent.present()
        self.preferences_window.connect('destroy', closed)
        self.preferences_window.present()

    def expire_history(self):
        before = self.store.db.total_changes
        self.store.prune()
        if self.store.db.total_changes != before and self.window and self.window.get_visible():
            self.window.refresh()
        return True

    def paste_failed(self):
        notification = Gio.Notification.new('Item copied to clipboard')
        notification.set_body('The previous window was not ready. Press Ctrl+V in your destination to paste.')
        self.send_notification('paste-fallback', notification)

    def capture(self, payload):
        self.store.add(payload)
        if self.window and self.window.get_visible():
            self.window.refresh()

    def update_tray(self):
        self.tray.set_tooltip_text('Mint Shelf · ' + ('Capture paused' if self.paused else 'Win+V to open'))
        self.tray.set_icon_name('media-playback-pause-symbolic' if self.paused else 'edit-paste-symbolic')

    def toggle_pause(self):
        self.paused = not self.paused
        self.store.set_setting('paused', '1' if self.paused else '0')
        self.update_tray()
        if self.window:
            self.window.refresh()


def main():
    os.umask(0o077)
    return Application().run(sys.argv)


if __name__ == '__main__':
    raise SystemExit(main())
