"""Validated preferences and Cinnamon login startup integration."""
import os
from pathlib import Path

DEFAULTS = {
    'auto_paste': True,
    'compact': False,
    'capture_images': True,
    'capture_files': True,
    'max_items': 200,
    'retention_days': 0,
}


def validate(key, value):
    if key not in DEFAULTS:
        raise ValueError('Unknown preference: ' + key)
    if isinstance(DEFAULTS[key], bool):
        if type(value) is not bool:
            raise ValueError(key + ' must be a boolean')
    elif key == 'max_items':
        if type(value) is not int or not 50 <= value <= 1000:
            raise ValueError('History size must be between 50 and 1000')
    elif type(value) is not int or value not in (0, 1, 7, 30, 90):
        raise ValueError('Choose a supported retention period')
    return value


def autostart_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart/mint-shelf.desktop'


def startup_enabled(path=None):
    from gi.repository import GLib
    path = path or autostart_path()
    if not path.exists():
        return False
    keyfile = GLib.KeyFile()
    try:
        keyfile.load_from_file(str(path), GLib.KeyFileFlags.NONE)
        keys = keyfile.get_keys('Desktop Entry')[0]
        if 'Hidden' in keys and keyfile.get_boolean('Desktop Entry', 'Hidden'):
            return False
        return 'X-GNOME-Autostart-enabled' not in keys or keyfile.get_boolean('Desktop Entry', 'X-GNOME-Autostart-enabled')
    except GLib.Error:
        return False


def set_startup(enabled, path=None):
    from gi.repository import GLib
    path = path or autostart_path()
    keyfile = GLib.KeyFile()
    if path.exists():
        keyfile.load_from_file(str(path), GLib.KeyFileFlags.KEEP_COMMENTS)
    else:
        launcher = Path.home() / '.local/bin/mint-shelf'
        if not launcher.exists():
            raise OSError('Install Mint Shelf before enabling login startup.')
        for key, value in {'Type': 'Application', 'Name': 'Mint Shelf', 'Exec': '"' + str(launcher).replace('"', '\\"') + '" --background', 'OnlyShowIn': 'X-Cinnamon;', 'Icon': 'edit-paste'}.items():
            keyfile.set_string('Desktop Entry', key, value)
    keyfile.set_boolean('Desktop Entry', 'Hidden', False)
    keyfile.set_boolean('Desktop Entry', 'X-GNOME-Autostart-enabled', enabled)
    path.parent.mkdir(parents=True, exist_ok=True)
    keyfile.save_to_file(str(path))
