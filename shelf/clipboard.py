"""Asynchronous GTK selection capture and multi-format X11 clipboard ownership."""
import ctypes as C
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from .store import MAX_ITEM

FORMATS = ('UTF8_STRING', 'text/plain;charset=utf-8', 'text/plain', 'text/html', 'image/png', 'image/jpeg', 'text/uri-list', 'x-special/gnome-copied-files')
SENSITIVE = {'x-kde-passwordManagerHint', 'application/x-keepassxc', 'application/x-keepass', 'x-codex-shelf-private'}


class Target(C.Structure):
    _fields_ = [('target', C.c_char_p), ('flags', C.c_uint), ('info', C.c_uint)]


class Clipboard:
    def __init__(self, on_capture, paused=lambda: False, selection='CLIPBOARD'):
        self.selection = selection
        self.clip = Gtk.Clipboard.get(Gdk.Atom.intern(selection, False))
        self.on_capture, self.paused = on_capture, paused
        self.generation = 0
        self.owned = False
        self.payload = {}
        # gtk_clipboard_set_with_data is not exposed by PyGObject. Keep callbacks
        # and payload alive for exactly as long as this service owns the selection.
        self.lib = C.CDLL('libgtk-3.so.0')
        self.gdk = C.CDLL('libgdk-3.so.0')
        self.gdk.gdk_atom_intern.argtypes = [C.c_char_p, C.c_int]
        self.gdk.gdk_atom_intern.restype = C.c_void_p
        self.lib.gtk_clipboard_get.argtypes = [C.c_void_p]
        self.lib.gtk_clipboard_get.restype = C.c_void_p
        self.get_cb_type = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint, C.c_void_p)
        self.clear_cb_type = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)
        self.get_cb = self.get_cb_type(self._provide)
        self.clear_cb = self.clear_cb_type(self._clear)
        self.lib.gtk_clipboard_set_with_data.argtypes = [C.c_void_p, C.POINTER(Target), C.c_uint, self.get_cb_type, self.clear_cb_type, C.c_void_p]
        self.lib.gtk_clipboard_set_with_data.restype = C.c_int
        self.lib.gtk_selection_data_set.argtypes = [C.c_void_p, C.c_void_p, C.c_int, C.c_void_p, C.c_int]
        self.clip.connect('owner-change', self._changed)

    def _clear(self, *_):
        self.owned = False

    def _provide(self, clipboard, data, info, user):
        name = self.names[info]
        value = self.payload[name]
        atom = self.gdk.gdk_atom_intern(name.encode(), False)
        self.lib.gtk_selection_data_set(data, atom, 8, value, len(value))

    def restore(self, payload):
        if not payload:
            return False
        payload = dict(payload)
        # Historic file cuts are replayed as copies; a stale move could remove a
        # source unexpectedly. Ordinary text cuts are indistinguishable from copies.
        if 'x-special/gnome-copied-files' in payload:
            data = payload['x-special/gnome-copied-files']
            if data.startswith(b'cut\n'):
                payload['x-special/gnome-copied-files'] = b'copy\n' + data[4:]
        if 'UTF8_STRING' in payload:
            payload.setdefault('text/plain;charset=utf-8', payload['UTF8_STRING'])
            payload.setdefault('text/plain', payload['UTF8_STRING'])
        names = list(payload)
        targets = (Target * len(names))(*(Target(n.encode(), 0, i) for i, n in enumerate(names)))
        pointer = self.lib.gtk_clipboard_get(self.gdk.gdk_atom_intern(self.selection.encode(), False))
        self.generation += 1
        # The old clear callback can run synchronously during this call.
        ok = self.lib.gtk_clipboard_set_with_data(pointer, targets, len(names), self.get_cb, self.clear_cb, None)
        if ok:
            self.names, self.payload, self.owned = names, payload, True
        return bool(ok)

    def _changed(self, *_):
        self.generation += 1
        if self.owned or self.paused():
            return
        generation = self.generation
        self.clip.request_targets(self._targets, generation)

    def _targets(self, clipboard, targets, n_targets, generation):
        if generation != self.generation or self.paused() or not targets:
            return
        names = {a.name() for a in targets}
        if names & SENSITIVE:
            return
        wanted = [n for n in FORMATS if n in names]
        # Avoid storing duplicate encodings of the same text and image.
        if 'UTF8_STRING' in wanted:
            wanted = [n for n in wanted if not n.startswith('text/plain')]
        if 'image/png' in wanted and 'image/jpeg' in wanted:
            wanted.remove('image/jpeg')
        payload = {}
        def receive(index):
            if generation != self.generation or self.paused():
                return
            if index == len(wanted):
                if payload:
                    self.on_capture(payload)
                return
            name = wanted[index]
            def got(clip, data, *args):
                if generation != self.generation:
                    return
                raw = data.get_data()
                if raw and data.get_format() == 8:
                    payload[name] = bytes(raw)
                if sum(map(len, payload.values())) <= MAX_ITEM:
                    receive(index + 1)
            clipboard.request_contents(Gdk.Atom.intern(name, False), got)
        receive(0)
