import tempfile
import unittest
from unittest.mock import patch
from shelf.store import Store, describe


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_roundtrip_and_dedup(self):
        payload = {'UTF8_STRING': 'Héllo 🌿'.encode(), 'text/html': b'<b>Hello</b>'}
        a = self.store.add(payload)
        self.assertEqual(a, self.store.add(payload))
        self.assertEqual(self.store.payload(a), payload)
        self.assertEqual(len(self.store.items()), 1)
        self.assertEqual(len(self.store.items('HÉLLO')), 1)

    def test_types(self):
        self.assertEqual(describe({'UTF8_STRING': b'https://example.com/path'})[0], 'link')
        self.assertEqual(describe({'UTF8_STRING': b'https://example.com/with space'})[0], 'text')
        self.assertEqual(describe({'image/png': b'png'})[0], 'image')
        self.assertEqual(describe({'x-special/gnome-copied-files': b'cut\nfile:///tmp/Hello%20World.txt'})[:2], ('files', 'Hello World.txt'))

    def test_pinned_survive_eviction_and_clear(self):
        a = self.store.add({'UTF8_STRING': b'pinned'})
        self.store.pin(a)
        with patch('shelf.store.MAX_ITEMS', 3):
            for i in range(8):
                self.store.add({'UTF8_STRING': str(i).encode()})
        self.assertEqual(len(self.store.items()), 3)
        self.assertEqual(self.store.items()[0]['id'], a)
        self.store.clear()
        self.assertEqual(len(self.store.items()), 1)
        self.store.delete(a)
        self.assertEqual(self.store.items(), [])

    def test_size_budget_and_reject(self):
        with patch('shelf.store.MAX_ITEM', 10), patch('shelf.store.MAX_BYTES', 15):
            self.assertIsNone(self.store.add({'UTF8_STRING': b'x' * 11}))
            self.store.add({'UTF8_STRING': b'x' * 8})
            self.store.add({'UTF8_STRING': b'y' * 8})
            self.assertEqual(len(self.store.items()), 1)

    def test_malformed_link_is_plain_text(self):
        self.assertEqual(describe({'UTF8_STRING': b'https://[invalid'})[0], 'text')
        self.assertEqual(describe({'text/uri-list': b'https://[invalid'})[0], 'files')

    def test_permissions_and_persistence(self):
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
        self.store.set_setting('paused', '1')
        other = Store(self.temp.name)
        self.assertEqual(other.setting('paused'), '1')
        other.db.close()


if __name__ == '__main__':
    unittest.main()
