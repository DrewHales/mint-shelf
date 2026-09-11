"""Real X11 selection tests use a PRIVATE selection, never the user's clipboard."""
import time
import subprocess
import sys
import unittest
import uuid
from shelf.clipboard import Clipboard
from gi.repository import Gdk, GLib


def pump(predicate, timeout=2):
    end = time.monotonic() + timeout
    context = GLib.MainContext.default()
    while time.monotonic() < end:
        while context.pending():
            context.iteration(False)
        if predicate():
            return True
        time.sleep(0.005)
    return False


@unittest.skipUnless(Gdk.Display.get_default(), 'Requires a display')
class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.name = 'MINT_SHELF_TEST_' + uuid.uuid4().hex
        self.captured = []
        self.paused = False
        self.reader = Clipboard(self.captured.append, lambda: self.paused, self.name)
        self.writer = Clipboard(lambda _: None, selection=self.name)

    def test_unicode_html_and_capture(self):
        payload = {'UTF8_STRING': 'Test 🌿 café'.encode(), 'text/html': b'<b>Test</b>'}
        self.assertTrue(self.writer.restore(payload))
        self.assertTrue(pump(lambda: bool(self.captured)))
        self.assertEqual(self.captured[-1]['UTF8_STRING'], payload['UTF8_STRING'])
        self.assertEqual(self.captured[-1]['text/html'], payload['text/html'])
        self.assertTrue(self.reader.restore(payload))
        data = self.writer.clip.wait_for_contents(Gdk.Atom.intern('text/html', False))
        self.assertEqual(bytes(data.get_data()), b'<b>Test</b>')
        # Losing ownership must resume capture, including after a restore.
        pump(lambda: False, .05)
        self.writer.restore({'UTF8_STRING': b'next'})
        self.assertTrue(pump(lambda: any(p.get('UTF8_STRING') == b'next' for p in self.captured)))

    def test_capture_from_external_process(self):
        code = """
import sys
from shelf.clipboard import Clipboard
from gi.repository import GLib
writer = Clipboard(lambda _: None, selection=sys.argv[1])
writer.restore({'UTF8_STRING': b'External process', 'text/html': b'<i>External process</i>'})
loop = GLib.MainLoop()
GLib.timeout_add_seconds(5, loop.quit)
loop.run()
"""
        process = subprocess.Popen([sys.executable, '-c', code, self.name], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            self.assertTrue(pump(lambda: bool(self.captured), 3))
            self.assertEqual(self.captured[-1]['UTF8_STRING'], b'External process')
            self.assertEqual(self.captured[-1]['text/html'], b'<i>External process</i>')
        finally:
            process.terminate()
            _, stderr = process.communicate(timeout=2)
            self.assertEqual(stderr, b'')

    def test_file_cut_replayed_as_copy(self):
        self.writer.restore({'x-special/gnome-copied-files': b'cut\nfile:///tmp/test.txt', 'text/uri-list': b'file:///tmp/test.txt\r\n'})
        data = self.reader.clip.wait_for_contents(Gdk.Atom.intern('x-special/gnome-copied-files', False))
        self.assertEqual(bytes(data.get_data()), b'copy\nfile:///tmp/test.txt')

    def test_image_roundtrip(self):
        from gi.repository import GdkPixbuf
        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 12, 12)
        pixbuf.fill(0x26a69aff)
        ok, data = pixbuf.save_to_bufferv('png', [], [])
        self.writer.restore({'image/png': bytes(data)})
        self.assertTrue(pump(lambda: bool(self.captured)))
        self.assertEqual(self.captured[-1]['image/png'], bytes(data))
        result = self.reader.clip.wait_for_image()
        self.assertEqual((result.get_width(), result.get_height()), (12, 12))

    def test_private_and_paused(self):
        self.writer.restore({'UTF8_STRING': b'secret', 'x-kde-passwordManagerHint': b'secret'})
        pump(lambda: False, .1)
        self.assertEqual(self.captured, [])
        self.paused = True
        self.writer.restore({'UTF8_STRING': b'paused'})
        pump(lambda: False, .1)
        self.assertEqual(self.captured, [])
        self.paused = False
        self.writer.restore({'UTF8_STRING': b'public'})
        self.assertTrue(pump(lambda: bool(self.captured)))
        self.assertEqual(self.captured[-1]['UTF8_STRING'], b'public')

    def tearDown(self):
        self.writer.clip.clear()
        pump(lambda: False, .02)


if __name__ == '__main__':
    unittest.main()
