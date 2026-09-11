import tempfile
import time
import unittest
from pathlib import Path
from shelf.store import Store
from shelf.preferences import DEFAULTS, startup_enabled, set_startup


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_defaults_and_restart(self):
        for key, value in DEFAULTS.items():
            self.assertEqual(self.store.option(key), value)
        self.store.save_options({'auto_paste': False, 'compact': True, 'max_items': 100, 'retention_days': 7})
        other = Store(self.temp.name)
        self.assertFalse(other.option('auto_paste'))
        self.assertTrue(other.option('compact'))
        self.assertEqual(other.option('max_items'), 100)
        self.assertEqual(other.option('retention_days'), 7)
        other.db.close()

    def test_capture_types(self):
        image = self.store.add({'image/png': b'old image'})
        self.store.save_options({'capture_images': False, 'capture_files': False})
        self.assertIsNone(self.store.add({'image/png': b'new image'}))
        self.assertIsNone(self.store.add({'text/uri-list': b'file:///tmp/test.txt'}))
        self.assertIsNotNone(self.store.add({'UTF8_STRING': b'text'}))
        self.assertIsNotNone(self.store.add({'UTF8_STRING': b'https://example.com'}))
        self.assertTrue(self.store.payload(image))
        self.store.save_options({'capture_images': True})
        self.assertIsNotNone(self.store.add({'image/png': b'new image'}))

    def test_retention_and_reduced_limit_protect_pins(self):
        pinned = self.store.add({'UTF8_STRING': b'pin'})
        self.store.pin(pinned)
        old = self.store.add({'UTF8_STRING': b'old'})
        with self.store.db:
            self.store.db.execute('UPDATE clips SET created=?', (time.time() - 10 * 86400,))
        self.store.save_options({'retention_days': 7})
        self.assertFalse(self.store.payload(old))
        self.assertTrue(self.store.payload(pinned))
        for i in range(80):
            self.store.add({'UTF8_STRING': str(i).encode()})
        self.store.save_options({'max_items': 50})
        self.assertEqual(len(self.store.items()), 50)
        self.assertTrue(self.store.payload(pinned))
        with self.store.db:
            self.store.db.execute('UPDATE clips SET created=?', (time.time() - 10 * 86400,))
        self.store.prune()
        self.assertEqual(len(self.store.items()), 1)

    def test_invalid_save_is_atomic(self):
        for invalid in (0, 1001, '100'):
            with self.assertRaises(ValueError):
                self.store.save_options({'auto_paste': False, 'max_items': invalid})
            self.assertTrue(self.store.option('auto_paste'))
        self.store.set_setting('retention_days', 'corrupt')
        self.assertEqual(self.store.option('retention_days'), 0)

    def test_startup_toggle_preserves_desktop_entry(self):
        path = Path(self.temp.name) / 'startup.desktop'
        path.write_text('[Desktop Entry]\nType=Application\nName=Mint Shelf\nExec=/tmp/example --background\nX-GNOME-Autostart-enabled=true\n')
        self.assertTrue(startup_enabled(path))
        set_startup(False, path)
        self.assertFalse(startup_enabled(path))
        self.assertIn('Exec=/tmp/example --background', path.read_text())
        set_startup(True, path)
        self.assertTrue(startup_enabled(path))
