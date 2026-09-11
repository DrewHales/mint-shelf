"""Native settings dialog. Changes apply together when the user presses Save."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from .preferences import startup_enabled, set_startup


class SettingsDialog(Gtk.Dialog):
    def __init__(self, app, parent=None):
        super().__init__(title='Mint Shelf Settings', transient_for=parent, modal=True, destroy_with_parent=True)
        self.app = app
        self.set_default_size(540, 560)
        self.set_resizable(False)
        self.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Save', Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.get_widget_for_response(Gtk.ResponseType.OK).get_style_context().add_class('suggested-action')
        area = self.get_content_area()
        area.set_border_width(18)
        area.set_spacing(14)
        tabs = Gtk.Notebook()
        area.pack_start(tabs, True, True, 0)
        general = self.page(tabs, 'General')
        history = self.page(tabs, 'History')
        self.controls = {}
        self.add_switch(general, 'auto_paste', 'Paste when selecting an item', 'Return to the previous window and paste.\nWhen off, selecting an item only copies it.')
        self.add_switch(general, 'compact', 'Compact shelf', 'Smaller cards with one-line text previews.')
        self.startup = Gtk.Switch(active=startup_enabled())
        self.row(general, 'Start at login', 'Keep the clipboard shelf ready after signing in.', self.startup)
        shortcut = Gtk.Label(label='Win+V', xalign=1)
        self.row(general, 'Open the shelf', 'Your Cinnamon keyboard shortcut.', shortcut)
        self.add_switch(history, 'capture_images', 'Save images', 'Include new image copies in history.')
        self.add_switch(history, 'capture_files', 'Save files', 'Include new file copies and cuts in history.')
        count = Gtk.SpinButton.new_with_range(50, 1000, 50)
        count.set_value(app.store.option('max_items'))
        count.set_numeric(True)
        self.controls['max_items'] = count
        self.row(history, 'History size', 'Older unpinned items are removed first.', count)
        retention = Gtk.ComboBoxText()
        for key, name in [('0', 'Until full'), ('1', '1 day'), ('7', '7 days'), ('30', '30 days'), ('90', '90 days')]:
            retention.append(key, name)
        retention.set_active_id(str(app.store.option('retention_days')))
        self.controls['retention_days'] = retention
        self.row(history, 'Keep unpinned items', 'Automatically remove older history.', retention)
        note = Gtk.Label(label='Lower limits remove older unpinned items when you save.\nPinned items are always kept, even above your chosen limit.\nTurning off a type only affects new copies.\nStorage: 64 MiB total, 16 MiB per item. Local, not encrypted.', xalign=0)
        note.get_style_context().add_class('shelf-muted')
        history.pack_start(note, False, False, 5)
        self.error = Gtk.Label(xalign=0)
        self.error.set_line_wrap(True)
        area.pack_start(self.error, False, False, 0)
        self.connect('response', self.respond)
        self.show_all()

    @staticmethod
    def page(tabs, title):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_border_width(18)
        tabs.append_page(page, Gtk.Label(label=title))
        return page

    @staticmethod
    def row(page, title, description, control):
        row = Gtk.Box(spacing=18)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        label = Gtk.Label(label=title, xalign=0)
        label.get_style_context().add_class('shelf-setting-title')
        text.pack_start(label, False, False, 0)
        detail = Gtk.Label(label=description, xalign=0)
        detail.get_style_context().add_class('shelf-muted')
        text.pack_start(detail, False, False, 0)
        row.pack_start(text, True, True, 0)
        control.set_valign(Gtk.Align.CENTER)
        row.pack_end(control, False, False, 0)
        page.pack_start(row, False, False, 0)

    def add_switch(self, page, key, title, description):
        switch = Gtk.Switch(active=self.app.store.option(key))
        self.controls[key] = switch
        self.row(page, title, description, switch)

    def respond(self, _, response):
        if response == Gtk.ResponseType.OK:
            values = {k: w.get_active() for k, w in self.controls.items() if isinstance(w, Gtk.Switch)}
            values['max_items'] = self.controls['max_items'].get_value_as_int()
            values['retention_days'] = int(self.controls['retention_days'].get_active_id())
            try:
                if self.startup.get_active() != startup_enabled():
                    set_startup(self.startup.get_active())
                self.app.store.save_options(values)
            except (OSError, GLib.Error, ValueError) as error:
                self.error.set_text('Could not save settings: ' + str(error))
                return
            if self.app.window:
                self.app.window.refresh()
        self.destroy()
