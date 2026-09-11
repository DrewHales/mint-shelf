#!/usr/bin/env python3
"""Install Mint Shelf for the current user. No root privileges required."""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio
from shelf.preferences import autostart_path

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
DEST = HOME / '.local/lib/mint-shelf'
BIN = HOME / '.local/bin/mint-shelf'
DESKTOP = HOME / '.local/share/applications/io.github.mintshelf.Clipboard.desktop'
AUTOSTART = autostart_path()
SCHEMA = 'org.cinnamon.desktop.keybindings'
KEY = 'custom-mint-shelf'
CUSTOM_PATH = f'/org/cinnamon/desktop/keybindings/custom-keybindings/{KEY}/'


def desktop_quote(path):
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    settings = Gio.Settings.new(SCHEMA)
    custom = Gio.Settings.new_with_path(SCHEMA + '.custom-keybinding', CUSTOM_PATH)
    keys = settings.get_strv('custom-list')
    if args.uninstall:
        if BIN.exists():
            subprocess.run([str(BIN), '--quit'], check=False)
        if KEY in keys:
            settings.set_strv('custom-list', [k for k in keys if k != KEY])
            for key in ('name', 'command', 'binding'):
                custom.reset(key)
        Gio.Settings.sync()
        for file in (BIN, DESKTOP, AUTOSTART):
            file.unlink(missing_ok=True)
        if DEST.exists():
            shutil.rmtree(DEST)
        print('Uninstalled Mint Shelf. Your history is retained in ~/.local/share/mint-shelf.')
        return
    # Refuse to overwrite another action assigned to the requested shortcut.
    from gi.repository import Gtk
    wanted = Gtk.accelerator_parse('<Super>v')
    conflicts = []
    for schema_name in (SCHEMA, SCHEMA + '.wm', SCHEMA + '.media-keys', 'org.cinnamon.muffin.keybindings'):
        setting = Gio.Settings.new(schema_name)
        for key in setting.props.settings_schema.list_keys():
            value = setting.get_value(key)
            if value.get_type_string() == 'as':
                for accel in value.unpack():
                    if Gtk.accelerator_parse(accel) == wanted:
                        conflicts.append(f'{schema_name}: {key}')
    for key in keys:
        if key == KEY:
            continue
        other = Gio.Settings.new_with_path(SCHEMA + '.custom-keybinding', f'/org/cinnamon/desktop/keybindings/custom-keybindings/{key}/')
        if any(Gtk.accelerator_parse(a) == wanted for a in other.get_strv('binding')):
            conflicts.append(other.get_string('name'))
    if conflicts:
        raise SystemExit('Win+V is already assigned: ' + ', '.join(conflicts))
    for directory in (DEST, BIN.parent, DESKTOP.parent, AUTOSTART.parent):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'shelf', DEST / 'shelf', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'README.md', DEST / 'README.md')
    shutil.copy2(ROOT / 'LICENSE', DEST / 'LICENSE')
    BIN.write_text('#!/bin/sh\ncd ' + shlex.quote(str(DEST)) + ' || exit 1\nexec /usr/bin/python3 -m shelf.app "$@"\n')
    BIN.chmod(0o755)
    common = '[Desktop Entry]\nType=Application\nName=Mint Shelf\nComment=Search and reuse your clipboard history\nIcon=edit-paste\nTerminal=false\nCategories=Utility;GTK;\n'
    DESKTOP.write_text(common + 'Exec=' + desktop_quote(BIN) + '\nKeywords=clipboard;copy;paste;history;shelf;\nStartupNotify=false\n')
    if not AUTOSTART.exists():
        AUTOSTART.write_text(common + 'Exec=' + desktop_quote(BIN) + ' --background\nX-GNOME-Autostart-enabled=true\nOnlyShowIn=X-Cinnamon;\n')
    custom.set_string('name', 'Mint Shelf')
    custom.set_string('command', shlex.quote(str(BIN)))
    custom.set_strv('binding', ['<Super>v'])
    if KEY not in keys:
        settings.set_strv('custom-list', keys + [KEY])
    Gio.Settings.sync()
    subprocess.run(['update-desktop-database', str(DESKTOP.parent)], check=False)
    print('Installed Mint Shelf. Win+V opens the shelf; login startup follows your saved settings.')
    print('Launcher: ' + str(BIN))


if __name__ == '__main__':
    main()
