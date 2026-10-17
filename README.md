# Huawei Free Touch for Linux

Brings the Huawei MateBook **Free Touch** edge sliders to Linux, haptics included:

- slide along the **right edge** of the touchpad → **volume** up / down
- slide along the **left edge** → **screen brightness** up / down
- every step is a **haptic tick** from the touchpad, and every tick is exactly
  one step, so a long slide works like a detented dial
- uses your desktop's own volume/brightness keys, so you get the normal on-screen display

It works by switching on the touchpad firmware's FreeTouch mode (the same
command Huawei PC Manager sends on Windows) and turning the firmware's gesture
ticks into media-key presses. The protocol is documented in
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## Tested on

| | |
|---|---|
| Laptop | **Huawei MateBook X Pro 2022**, model **MRGF-XX** (BIOS 1.39) |
| Touchpad | Goodix `GXTP7863` (`27C6:01E0`) |
| OS | Ubuntu 26.04 LTS, kernel 7.0, GNOME on Wayland |

Other Huawei laptops with a Free Touch pad may work if they use the same
touchpad; check with:

```bash
grep -l GXTP7863 /sys/class/hidraw/hidraw*/device/uevent
```

## Install

Requirements: Python 3, `python3-evdev`, systemd, and a desktop that reacts to
the volume/brightness keys (GNOME, KDE, …).

```bash
sudo apt install python3-evdev      # Fedora: python3-evdev, Arch: python-evdev
git clone https://github.com/Divin17/Huawei-Freetouch-for-Linux.git
cd Huawei-Freetouch-for-Linux
./install.sh
```

The installer:

1. installs a udev rule (`/etc/udev/rules.d/70-huawei-freetouch.rules`) so members
   of the `input` group can use `/dev/uinput` and the touchpad's `hidraw` node
   (this step asks for `sudo` once)
2. adds you to the `input` group if needed. In that case, **log out and back in once**
3. installs `huawei-freetouch` and `freetouchctl` into `~/.local/bin`
4. installs and enables the systemd **user** service `huawei-freetouch.service`,
   which starts with your graphical session

## Start / stop at any time

```bash
freetouchctl start      # turn it on now
freetouchctl stop       # turn it off now (edges behave like a normal touchpad again)
freetouchctl status     # is it running?
freetouchctl enable     # start automatically at every login (and start now)
freetouchctl disable    # don't start at login (and stop now)
freetouchctl restart
freetouchctl logs       # follow the log
freetouchctl debug      # run in the foreground, printing every firmware tick
```

Plain systemd works too: `systemctl --user start|stop|enable|disable huawei-freetouch`.

Stopping the service also switches FreeTouch off in the touchpad firmware, so
nothing is left running in the background.

## Configuration

- **Haptic strength:** `huawei-freetouch --strength 1|2|3` (low / medium / high,
  default 2). To make it permanent, run `systemctl --user edit huawei-freetouch` and add:

  ```ini
  [Service]
  ExecStart=
  ExecStart=%h/.local/bin/huawei-freetouch --strength 3
  ```

  Only strength 2 has been tested on hardware so far.
- **Step size:** each tick is one volume/brightness key press. On GNOME the
  volume step is a desktop setting:
  `gsettings set org.gnome.settings-daemon.plugins.media-keys volume-step 3`

## Troubleshooting

| Symptom | Fix |
|---|---|
| `freetouchctl logs` says `fallback distance stepping` | The touchpad's hidraw node isn't accessible. Check `ls -l /dev/hidraw*` shows group `input`, and that you logged out/in after the installer added you to `input`. Sliders still work in this mode, but without haptic ticks. |
| No ticks after waking from sleep | The pad forgets its settings over suspend. The service re-sends them on your first touch after 30 s of idle. If it still fails, run `freetouchctl restart`. |
| Volume changes but no on-screen display | Your desktop doesn't handle the media keys; test with `xev`/`wev`. |

## Uninstall

```bash
./uninstall.sh
```

## How it was made

The FreeTouch commands were recovered by disassembling Huawei PC Manager's
`FreeTouchPlugin.dll` / `FreeTouchHidAPI.dll`, then confirmed on the pad under
Linux by watching its vendor HID reports. No Huawei code is included.

## License

MIT, see [LICENSE](LICENSE).
