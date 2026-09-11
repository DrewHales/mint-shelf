"""Real X11 click/Enter/focus test. Uses a private clipboard and test destination."""
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shelf.app import ShelfWindow, Gtk, Gdk, Gio, GLib
from shelf.paste import PasteController, C
from shelf.clipboard import Clipboard
from shelf.store import Store

app = Gtk.Application(application_id='io.github.mintshelf.PasteTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
app.register(None)
tmp = tempfile.TemporaryDirectory()
app.store = Store(tmp.name)
app.paused = False
app.clipboard = Clipboard(lambda _: None, selection='MINT_SHELF_PASTE_TEST')
app.paster = PasteController()
app.toggle_pause = lambda: None
failures = []
app.paste_failed = lambda: failures.append('Unexpected fallback')
app.store.add({'UTF8_STRING': b'Single click paste works'})
destination = Gtk.Window(title='Mint Shelf paste test destination')
destination.set_default_size(500, 180)
entry = Gtk.Entry()
destination.add(entry)
pastes = []
def key(_, event):
    if event.keyval == Gdk.KEY_v and event.state & Gdk.ModifierType.CONTROL_MASK:
        pastes.append(app.clipboard.clip.wait_for_text())
        entry.set_text(pastes[-1])
        return True
    return False
entry.connect('key-press-event', key)
window = ShelfWindow(app)
p = app.paster
p.xt.XTestFakeMotionEvent.argtypes = [C.c_void_p, C.c_int, C.c_int, C.c_int, C.c_ulong]
p.xt.XTestFakeButtonEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]

def wait(predicate, timeout=2):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return True
        time.sleep(.005)
    return False

def press(name, down):
    code = p.x.XKeysymToKeycode(p.display, p.x.XStringToKeysym(name))
    p.xt.XTestFakeKeyEvent(p.display, code, down, 0)
    p.x.XFlush(p.display)

def open_shelf():
    destination.show_all()
    destination.present()
    entry.grab_focus()
    assert wait(lambda: destination.is_active())
    p.remember()
    window.show_all()
    window.present()
    window.search.grab_focus()
    assert wait(lambda: window.is_active())

try:
    open_shelf()
    destination.move(30, 60)
    wait(lambda: False, .1)
    _, dx, dy = destination.get_window().get_origin()
    p.xt.XTestFakeMotionEvent(p.display, -1, dx+60, dy+80, 0)
    p.xt.XTestFakeButtonEvent(p.display, 1, 1, 0)
    p.xt.XTestFakeButtonEvent(p.display, 1, 0, 0)
    p.x.XFlush(p.display)
    assert wait(lambda: destination.is_active()), 'Outside click did not focus destination'
    wait(lambda: False, .35)
    assert window.get_visible(), 'Shelf closed after clicking outside'
    print('PASS: outside click changes focus while the shelf stays visible')
    row = window.list.get_row_at_index(0)
    x, y = row.translate_coordinates(window, 100, 35)
    _, wx, wy = window.get_window().get_origin()
    p.xt.XTestFakeMotionEvent(p.display, -1, wx+x, wy+y, 0)
    p.xt.XTestFakeButtonEvent(p.display, 1, 1, 0)
    p.xt.XTestFakeButtonEvent(p.display, 1, 0, 0)
    p.x.XFlush(p.display)
    assert wait(lambda: len(pastes) == 1), (pastes, failures)
    assert entry.get_text() == 'Single click paste works'
    assert not window.get_visible()
    print('PASS: single click closes shelf, restores destination focus and pastes exactly once')
    open_shelf()
    press(b'Return', 1)
    assert wait(lambda: not window.get_visible())
    wait(lambda: False, .15)
    assert len(pastes) == 1, 'Pasted with Enter still held'
    press(b'Return', 0)
    assert wait(lambda: len(pastes) == 2), failures
    print('PASS: Enter activation waits for key release then pastes exactly once')
    # If the remembered destination is gone, never inject into another window.
    open_shelf()
    destination.destroy()
    window.choose(window.list.get_row_at_index(0))
    assert wait(lambda: bool(failures))
    assert len(pastes) == 2
    print('PASS: closed destination falls back without sending keys elsewhere')
finally:
    p.cancel()
    press(b'Return', 0)
    window.destroy()
    destination.destroy()
    app.store.db.close()
    tmp.cleanup()
