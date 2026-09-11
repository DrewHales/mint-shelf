"""Paste into the X11 window that was active before the shelf opened."""
import ctypes as C
import time
import gi

gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gdk, GdkX11, GLib


class ClassHint(C.Structure):
    _fields_ = [('res_name', C.c_void_p), ('res_class', C.c_void_p)]


class PasteController:
    def __init__(self):
        self.x = C.CDLL('libX11.so.6')
        self.xt = C.CDLL('libXtst.so.6')
        self.x.XOpenDisplay.argtypes = [C.c_char_p]
        self.x.XOpenDisplay.restype = C.c_void_p
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Mint Shelf requires an X11 display')
        self.x.XStringToKeysym.argtypes = [C.c_char_p]
        self.x.XStringToKeysym.restype = C.c_ulong
        self.x.XKeysymToKeycode.argtypes = [C.c_void_p, C.c_ulong]
        self.x.XKeysymToKeycode.restype = C.c_uint
        self.x.XQueryKeymap.argtypes = [C.c_void_p, C.c_void_p]
        self.x.XFlush.argtypes = [C.c_void_p]
        self.x.XGetClassHint.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(ClassHint)]
        self.x.XFree.argtypes = [C.c_void_p]
        self.xt.XTestFakeKeyEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
        self.target = None
        self.source = None

    def active(self):
        return Gdk.Screen.get_default().get_active_window()

    @staticmethod
    def xid(window):
        return window.get_xid() if window else None

    def cancel(self):
        if self.source:
            GLib.source_remove(self.source)
            self.source = None

    def remember(self):
        self.cancel()
        self.target = self.active()

    def keys_released(self):
        keys = C.create_string_buffer(32)
        self.x.XQueryKeymap(self.display, keys)
        # Wait for physical Enter, Win, mouse buttons, etc. to be released.
        pointer = Gdk.Display.get_default().get_default_seat().get_pointer()
        mask = Gdk.get_default_root_window().get_device_position(pointer)[-1]
        return not any(keys.raw) and not (mask & (Gdk.ModifierType.BUTTON1_MASK | Gdk.ModifierType.BUTTON2_MASK | Gdk.ModifierType.BUTTON3_MASK))

    def is_terminal(self, window):
        hint = ClassHint()
        if not self.x.XGetClassHint(self.display, self.xid(window), C.byref(hint)):
            return False
        try:
            names = [C.string_at(p).decode('utf-8', 'replace').lower() for p in (hint.res_name, hint.res_class) if p]
            terminals = ('terminal', 'terminator', 'tilix', 'kitty', 'alacritty', 'wezterm', 'konsole', 'urxvt', 'xterm', 'st-256color')
            return any(t in name for name in names for t in terminals)
        finally:
            for p in (hint.res_name, hint.res_class):
                if p:
                    self.x.XFree(p)

    def send_paste(self, terminal=False):
        names = [b'Control_L'] + ([b'Shift_L'] if terminal else []) + [b'v']
        codes = [self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(n)) for n in names]
        for code in codes:
            self.xt.XTestFakeKeyEvent(self.display, code, True, 0)
        for code in reversed(codes):
            self.xt.XTestFakeKeyEvent(self.display, code, False, 0)
        self.x.XFlush(self.display)

    def paste(self, owns_clipboard, failed=lambda: None):
        self.cancel()
        target = self.target
        started = time.monotonic()
        if not target:
            failed()
            return
        # Hiding the shelf lets Cinnamon restore its previous focused window.
        # Never force activation: if the user switched elsewhere, do not paste there.
        def ready():
            elapsed = time.monotonic() - started
            if not owns_clipboard():
                self.source = None
                return False
            if self.xid(self.active()) == self.xid(target) and elapsed >= .08 and self.keys_released():
                terminal = self.is_terminal(target)
                if self.xid(self.active()) == self.xid(target):
                    self.send_paste(terminal)
                    self.source = None
                    return False
            if elapsed > .8:
                self.source = None
                failed()
                return False
            return True
        self.source = GLib.timeout_add(20, ready)
