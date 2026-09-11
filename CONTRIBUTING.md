# Contributing to Mint Shelf

Bug reports, documentation improvements and code contributions are welcome.
Mint Shelf currently targets Linux Mint Cinnamon on X11.

## Reporting a bug

Open an issue in this repository with your Linux Mint and Cinnamon versions,
whether you use X11, the steps to reproduce the problem, and what you expected
to happen. Include any relevant terminal error output.

Use invented clipboard content in examples and screenshots. Do not attach your
history database, passwords, tokens or personal file paths.

## Working on the code

Fork the repository into your GitHub account, then clone your fork. Install the
system dependencies listed in the README and run `./mint-shelf` from the checkout.
Quit any installed instance first so you are testing the changed code.
Running from source normally uses your regular Mint Shelf history; the tests
below use temporary data and private clipboard selections instead.

Create a branch for your change, keep it focused, and explain the problem and
resulting behaviour in a pull request. For larger changes, open an issue first
to discuss the approach.

Run the automated tests from the project directory:

```sh
/usr/bin/python3 -m unittest discover -s tests -v
```

On a Cinnamon X11 desktop, also run the relevant smoke checks:

```sh
/usr/bin/python3 tests/ui_smoke.py
/usr/bin/python3 tests/settings_smoke.py
/usr/bin/python3 tests/paste_smoke.py
```

The paste check opens and focuses test windows; let it finish before interacting
with the desktop. Changes involving shortcuts, tray integration or installation
also need manual verification on Linux Mint Cinnamon. GitHub's automated tests
use a virtual X11 display and do not verify the full Cinnamon desktop experience.

Contributions are provided under the project's [MIT license](LICENSE).
