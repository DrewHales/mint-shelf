#!/usr/bin/env bash
# Run as your normal desktop user, never with sudo.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ ${1:-} == --help ]]; then
    echo 'Usage: bash install.sh [--check | --uninstall]'
    echo 'Installs Mint Shelf for your account on Linux Mint Cinnamon (X11).'
    echo '--check checks the desktop and dependencies without changing anything.'
    exit 0
fi
if [[ $# -gt 1 || ( $# -eq 1 && $1 != --check && $1 != --uninstall ) ]]; then
    echo 'Unknown option. Use bash install.sh --help.' >&2
    exit 2
fi
if [[ $EUID -eq 0 ]]; then
    echo 'Run this installer as your normal user, without sudo.' >&2
    exit 1
fi
if [[ ${XDG_SESSION_TYPE:-x11} != x11 || -z ${DISPLAY:-} ]]; then
    echo 'Mint Shelf requires a Cinnamon X11 desktop session. Wayland is not supported.' >&2
    exit 1
fi
if ! command -v gsettings >/dev/null || ! gsettings list-schemas | grep -x 'org.cinnamon.desktop.keybindings' >/dev/null; then
    echo 'Cinnamon desktop settings were not found. Use Linux Mint Cinnamon on X11.' >&2
    exit 1
fi

packages=(python3 python3-gi gir1.2-gtk-3.0 gir1.2-xapp-1.0 "libxtst6:$(dpkg --print-architecture)" desktop-file-utils)
missing=()
for package in "${packages[@]}"; do
    if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) != 'install ok installed' ]]; then
        missing+=("$package")
    fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Required system packages: ${missing[*]}"
    if [[ ${1:-} == --check ]]; then exit 1; fi
    echo 'Your administrator password may be requested to install these packages.'
    sudo apt-get update
    sudo apt-get install -- "${missing[@]}"
fi
if [[ ${1:-} == --check ]]; then
    echo 'Desktop and dependencies are ready.'
    exit 0
fi
if [[ ${1:-} == --uninstall ]]; then
    exec /usr/bin/python3 install.py --uninstall
fi
/usr/bin/python3 install.py
# Restart an older instance so upgrades use the newly installed code.
"$HOME/.local/bin/mint-shelf" --quit
nohup "$HOME/.local/bin/mint-shelf" --background >/dev/null 2>&1 </dev/null &
echo 'Mint Shelf is ready. Press Win+V, or open Mint Shelf from the application menu.'
