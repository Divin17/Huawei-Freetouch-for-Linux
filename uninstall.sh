#!/usr/bin/env bash
# Remove Huawei Free Touch for Linux (the 'input' group membership is left alone).
set -euo pipefail
systemctl --user disable --now huawei-freetouch.service 2>/dev/null || true
rm -f "$HOME/.local/bin/huawei-freetouch" "$HOME/.local/bin/freetouchctl" \
      "$HOME/.config/systemd/user/huawei-freetouch.service"
systemctl --user daemon-reload
if [[ -e /etc/udev/rules.d/70-huawei-freetouch.rules ]]; then
    echo "Removing udev rule (needs sudo)"
    sudo rm -f /etc/udev/rules.d/70-huawei-freetouch.rules
    sudo udevadm control --reload
fi
echo "Uninstalled."
