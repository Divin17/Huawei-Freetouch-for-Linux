#!/usr/bin/env bash
# Install Huawei Free Touch for Linux for the current user.
#   ./install.sh            install + enable at login + start now
#   ./install.sh --no-start install only
set -euo pipefail
cd "$(dirname "$0")"

BIN=$HOME/.local/bin
UNIT_DIR=$HOME/.config/systemd/user
RULE=/etc/udev/rules.d/70-huawei-freetouch.rules

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

# 1. Dependency: python3-evdev
if ! python3 -c 'import evdev' 2>/dev/null; then
    say "python3-evdev is missing"
    if command -v apt-get >/dev/null; then echo "    sudo apt install python3-evdev"
    elif command -v dnf >/dev/null; then echo "    sudo dnf install python3-evdev"
    elif command -v pacman >/dev/null; then echo "    sudo pacman -S python-evdev"
    else echo "    pip install --user evdev"; fi
    exit 1
fi

# 2. Hardware check (warn only)
if ! grep -qs GXTP7863 /sys/class/hidraw/hidraw*/device/uevent; then
    say "warning: Goodix GXTP7863 touchpad not found - this was built for the"
    echo "    Huawei MateBook X Pro (MRGF-XX). Continuing anyway."
fi

# 3. Device permissions (needs root once)
if ! cmp -s udev/70-huawei-freetouch.rules "$RULE"; then
    say "Installing udev rule $RULE (needs sudo)"
    sudo install -m 644 udev/70-huawei-freetouch.rules "$RULE"
    sudo udevadm control --reload
    sudo udevadm trigger --subsystem-match=hidraw --subsystem-match=misc
fi
relogin=0
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
    say "Adding $USER to the 'input' group (needs sudo)"
    sudo usermod -aG input "$USER"
    relogin=1
fi

# 4. Program + control command + user service
say "Installing to $BIN and $UNIT_DIR"
install -Dm 755 huawei-freetouch.py "$BIN/huawei-freetouch"
install -Dm 755 freetouchctl "$BIN/freetouchctl"
install -Dm 644 systemd/huawei-freetouch.service "$UNIT_DIR/huawei-freetouch.service"
systemctl --user daemon-reload

if [[ ${1:-} == --no-start ]]; then
    say "Installed. Start with: freetouchctl enable"
elif (( relogin )); then
    systemctl --user enable huawei-freetouch.service
    say "Installed and enabled. Log out and back in once (new group membership),"
    echo "    then it starts automatically. Control it with: freetouchctl"
else
    systemctl --user enable huawei-freetouch.service
    systemctl --user restart huawei-freetouch.service   # pick up new permissions / program
    say "Running. Slide along the right edge for volume, left edge for brightness."
    echo "    Control it with: freetouchctl start|stop|status|enable|disable|logs"
fi
case ":$PATH:" in *":$BIN:"*) ;; *) say "note: add $BIN to your PATH to use freetouchctl";; esac
