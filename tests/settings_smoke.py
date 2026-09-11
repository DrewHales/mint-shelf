"""Exercise the settings dialog against temporary data and startup config."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shelf.app import Gtk, Gdk, GLib, Gio, CSS
from shelf.store import Store
from shelf.settings import SettingsDialog
from shelf.preferences import autostart_path, startup_enabled

temp = tempfile.TemporaryDirectory()
os.environ['XDG_CONFIG_HOME'] = temp.name
path = autostart_path()
path.parent.mkdir(parents=True)
path.write_text('[Desktop Entry]\nType=Application\nName=Mint Shelf\nExec=/tmp/example --background\nX-GNOME-Autostart-enabled=true\n')
app = Gtk.Application(application_id='io.github.mintshelf.SettingsTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
app.register(None)
app.store = Store(Path(temp.name) / 'data')
app.window = None
provider = Gtk.CssProvider()
provider.load_from_data(CSS)
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
d = SettingsDialog(app)
d.controls['auto_paste'].set_active(False)
d.response(Gtk.ResponseType.CANCEL)
assert app.store.option('auto_paste')
d = SettingsDialog(app)
d.controls['auto_paste'].set_active(False)
d.controls['compact'].set_active(True)
d.controls['max_items'].set_value(100)
d.controls['retention_days'].set_active_id('7')
d.startup.set_active(False)
d.response(Gtk.ResponseType.OK)
assert not app.store.option('auto_paste')
assert app.store.option('compact')
assert app.store.option('max_items') == 100
assert app.store.option('retention_days') == 7
assert not startup_enabled()
d = SettingsDialog(app)
assert not d.controls['auto_paste'].get_active()
assert not d.startup.get_active()
d.present()
def screenshot():
    window = d.get_window()
    pix = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
    pix.savev('/tmp/mint-shelf-settings.png', 'png', [], [])
    tabs = d.get_content_area().get_children()[0]
    tabs.set_current_page(1)
    GLib.timeout_add(200, history_screenshot)
    return False
def history_screenshot():
    window = d.get_window()
    pix = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
    pix.savev('/tmp/mint-shelf-settings-history.png', 'png', [], [])
    d.response(Gtk.ResponseType.CANCEL)
    Gtk.main_quit()
    return False
GLib.timeout_add(300, screenshot)
Gtk.main()
app.store.db.close()
temp.cleanup()
print('PASS: settings Save, Cancel, reopen, startup toggle and native rendering')
