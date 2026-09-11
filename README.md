# Mint Shelf

A lightweight clipboard shelf for Linux Mint Cinnamon. Press **Win+V**, find an item, and click it or press **Enter** to paste it directly into the application you opened the shelf from.

Built with Python 3, GTK 3 and Cinnamon's XApp tray integration. It follows your GTK theme, including light/dark themes and accent colours. It runs in the background and captures the explicit clipboard without polling or watching primary text selection.

The shelf stays open when you click elsewhere. Select an item, press Escape, press Win+V again, or use the close button to dismiss it.

## Features

- Text and link previews, image thumbnails, and file names.
- Live search and filters for text, images, links, files and pinned items.
- Rich HTML and supported image/file formats preserved alongside text.
- Pinned entries stay at the top; repeated copies are deduplicated.
- Arrow-key navigation, Enter to paste, Escape to dismiss, Ctrl+F to search, Ctrl+P to pin, Ctrl+Delete to delete.
- Tray access, pause/resume, clear unpinned history, and automatic startup at login.
- Single background instance, with instant activation through the Cinnamon shortcut.

## Install on Linux Mint Cinnamon (X11)

Developed on Linux Mint 22.3 Cinnamon using X11. Wayland is not supported.
Mint Shelf is an independent community project and is not affiliated with Linux Mint.

Install the system dependencies in a terminal:

```sh
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-xapp-1.0 libxtst6 desktop-file-utils
```

Download this repository using **Code → Download ZIP** on GitHub and extract it,
or clone it with Git. Open a terminal inside the extracted project folder (the
folder containing `install.py`), then run:

```sh
python3 install.py
~/.local/bin/mint-shelf --background
```

Updates preserve your login-startup preference. The installer creates a Cinnamon custom shortcut for Win+V, an application menu entry, and a login autostart entry. It checks for existing Win+V assignments and does not replace them. Installation is per user and does not require root. Re-run the installer after changes, then quit and restart the app.

Run directly from the source checkout with `./mint-shelf` or `./mint-shelf --background`. Stop the running instance with `./mint-shelf --quit` or the tray menu.

## Settings

Open **Settings…** from the shelf's menu or the tray's right-click menu. You can also run `mint-shelf --settings`. Press **Save** to apply changes immediately; **Cancel** leaves your preferences unchanged.

| Setting | Default | Options |
| --- | --- | --- |
| Paste when selecting an item | On | Turn off for copy-only selection |
| Compact shelf | Off | Smaller cards and one-line text previews |
| Start at login | On after installation | Enable or disable automatic startup |
| Save images / Save files | Both on | Choose which new copies are saved |
| History size | 200 | 50–1,000 entries |
| Keep unpinned items | Until full | 1, 7, 30 or 90 days, or until full |

Lowering a history limit removes older unpinned items when you save. Pinned items are always retained, even if they exceed your chosen entry limit; unpin or delete them to make room. Age is measured from the most recent capture of an item. Expiration runs at startup, when saving/capturing and once a minute while running. Turning off a capture type leaves existing history intact. The 64 MiB total payload and 16 MiB per-item limits remain in effect. Application preferences are saved in the local history database; login startup uses Cinnamon's autostart entry.

## History and privacy

History lives in `~/.local/share/mint-shelf/history.sqlite3` (or `$XDG_DATA_HOME/mint-shelf/history.sqlite3`) with a private directory and owner-only file permissions. It is not encrypted. The app makes no network requests or uploads, and does not fetch link previews.

By default, the shelf stores up to 200 items and 64 MiB of clipboard payload; base64/database overhead makes the database somewhat larger. Individual captures above 16 MiB are skipped. Old unpinned entries are evicted first; pinned entries consume the same budget. If pinned entries fill the budget, new captures cannot be kept until space is freed.

Recognised password-manager and private clipboard markers are ignored. Applications do not always mark sensitive content, so pause capture before copying anything you do not want saved. Pausing survives restarts and does not remove existing history. Delete individual pinned entries with their delete button; “Clear history” removes only unpinned entries. Clearing history leaves the current system clipboard unchanged.

Text cuts are captured like copies. Recalling a saved file cut restores it as a **copy**, to avoid moving original files from an old history entry. The original cut operation itself remains untouched until you select an item from history. File entries retain paths, not copies of the files; missing or moved source files cannot be pasted. Selecting an item closes the shelf, waits for Cinnamon to restore the previous window, and sends Ctrl+V (Ctrl+Shift+V for recognised terminal windows). It waits for held keys and mouse buttons to be released. If the previous window cannot regain focus, the item stays copied and a notification offers manual paste; it does not paste into a different window.

Capture begins when the app runs; previously copied items cannot be recovered. Unsupported application-specific binary formats are not retained. Supported targets are UTF-8 text, HTML, PNG/JPEG images, URI lists and GNOME/Nemo copied-file lists. X11 Cinnamon is the supported desktop; Wayland is not supported in this version.

## Verification

```sh
python3 -m unittest discover -s tests -v
python3 tests/ui_smoke.py
python3 tests/paste_smoke.py
python3 tests/settings_smoke.py
```

Storage tests cover Unicode, deduplication, filtering, bounds, persistence and pin retention. Clipboard integration tests use private X11 selections, leaving your real clipboard untouched; they cover text/HTML, images, file cuts, sensitive markers, pause and ownership changes. The GTK smoke test uses disposable history and a private selection to verify search, pin/delete, empty state and copying, and writes a temporary screenshot to `/tmp/mint-shelf-ui.png`. The paste smoke test opens a disposable destination window and verifies actual single-click paste, Enter release timing and safe fallback when the destination closes, using a private clipboard.

GTK clipboard implementation reference: [GTK 3 Clipboard](https://docs.gtk.org/gtk3/class.Clipboard.html). GTK's asynchronous clipboard APIs handle capture; a small typed `ctypes` bridge provides multi-target clipboard ownership because `gtk_clipboard_set_with_data` is not available through PyGObject.

## Uninstall

```sh
python3 install.py --uninstall
```

This removes the installed app, launcher, autostart and its shortcut while retaining history. To erase history too, remove the `mint-shelf` data directory described above after quitting the app.

## Contributing

Bug reports, feature suggestions and pull requests are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing and reporting guidance.
Use sample clipboard content when sharing screenshots or error reports.

## License

Mint Shelf is available under the [MIT license](LICENSE). Its system dependencies
remain covered by their respective licenses.
