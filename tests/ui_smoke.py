"""Native GTK smoke test with disposable history and a private clipboard."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shelf.app import ShelfWindow, CSS, Gtk, Gdk, Gio, GLib, GdkPixbuf
from shelf.store import Store
from shelf.clipboard import Clipboard

app = Gtk.Application(application_id='io.github.mintshelf.Smoke', flags=Gio.ApplicationFlags.NON_UNIQUE)
app.register(None)
tmp = tempfile.TemporaryDirectory()
app.store = Store(tmp.name)
app.paused = False
app.clipboard = Clipboard(lambda _: None, selection='MINT_SHELF_UI_TEST')
app.toggle_pause = lambda: None
from unittest.mock import Mock
app.paster = Mock()
app.paste_failed = lambda: None
provider = Gtk.CssProvider()
provider.load_from_data(CSS)
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
a = app.store.add({'UTF8_STRING': b'The little things, right where you left them.\nA place for ideas, snippets and everything in between.'})
app.store.pin(a)
app.store.add({'UTF8_STRING': b'https://www.linuxmint.com/'})
app.store.add({'UTF8_STRING': b'Shopping list\nCoffee beans, sourdough, tomatoes, olive oil'})
app.store.add({'x-special/gnome-copied-files': b'copy\nfile:///tmp/Project%20notes.pdf\nfile:///tmp/Design%20assets.zip'})
pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 160, 100)
pix.fill(0x279b8eff)
_, data = pix.save_to_bufferv('png', [], [])
app.store.add({'image/png': bytes(data)})
w = ShelfWindow(app)
w.dialog_open = True
w.show_all()
w.present()
errors = []
def verify():
    try:
        assert len(w.list.get_children()) == 5
        w.search.set_text('coffee')
        w.refresh()
        assert len(w.list.get_children()) == 1
        row = w.list.get_row_at_index(0)
        w.pin(row.clip_id)
        assert app.store.items('coffee')[0]['pinned'] == 1
        w.delete(row.clip_id)
        assert len(w.list.get_children()) == 0
        assert w.stack.get_visible_child_name() == 'empty'
        w.search.set_text('')
        w.refresh()
        w.choose(w.list.get_row_at_index(0))
        assert not w.get_visible()
        app.paster.paste.assert_called_once()
        app.paster.reset_mock()
        app.store.save_options({'auto_paste': False, 'compact': True})
        w.refresh()
        assert 'Ctrl+V' in w.instructions.get_text()
        assert w.list.get_style_context().has_class('shelf-compact')
        w.choose(w.list.get_row_at_index(0))
        app.paster.paste.assert_not_called()
        assert app.clipboard.clip.wait_for_text().startswith('The little things')
        w.show_all()
        w.present()
        w.search.grab_focus()
        GLib.timeout_add(300, screenshot)
    except Exception as e:
        errors.append(e)
        Gtk.main_quit()
    return False

def screenshot():
    window = w.get_window()
    image = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
    image.savev('/tmp/mint-shelf-ui.png', 'png', [], [])
    print('PASS: native window, search, pin, delete, empty state, clipboard restore and dismissal')
    Gtk.main_quit()
    return False
GLib.timeout_add(400, verify)
Gtk.main()
w.destroy()
app.store.db.close()
tmp.cleanup()
if errors:
    raise errors[0]
