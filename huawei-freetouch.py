#!/usr/bin/python3
"""Huawei Free Touch for Linux.

Replicates the MateBook Windows touchpad edge sliders:
  - vertical slide on the RIGHT edge  -> volume up/down (native OSD)
  - vertical slide on the LEFT edge   -> brightness up/down (native OSD)

The touchpad firmware does the real work once FreeTouch is enabled over its
vendor HID collection (feature report 0x08 = [cmd, value], protocol decoded
from Huawei PC Manager): it detects the edge slide, plays a haptic tick and
sends a vendor report 51 97 <ts:4> <state> <gesture-id> for every tick.
Each tick becomes exactly one key press, so steps and ticks stay in lockstep
like a detented dial; the report's id gives the edge and its state the
direction. See docs/PROTOCOL.md.

If the hidraw node can't be opened (missing udev rule), falls back to
distance-based stepping without firmware ticks.

On exit (SIGTERM / Ctrl+C) FreeTouch is switched off again, so the edges
behave like a plain touchpad while the service is stopped.
"""

import argparse
import fcntl
import glob
import os
import select
import signal
import sys
import time

from evdev import InputDevice, UInput, ecodes as e

TOUCHPAD_NAME = "GXTP7863:00 27C6:01E0 Touchpad"
HID_NAME = "GXTP7863"

# FreeTouch settings sent to the firmware (Huawei defaults: 2 / 2).
SENSITIVITY = 2
EDGE_GESTURES = 0x06     # bit1 brightness (left edge), bit2 volume (right edge)
KNUCKLE_GESTURES = 0x00  # screenshot/recording off
REENABLE_AFTER_S = 30    # re-send settings on a new touch after this idle time
                         # (the pad forgets them across suspend)

# Fallback (no hidraw access): distance-based stepping.
EDGE_FRACTION = 0.08
STEP_UNITS = 110
DEADZONE_UNITS = 40

# Firmware tick report 51 97 <ts:4> <state> <id>: id says which edge,
# state 0 = finger moving up, 1 = moving down.
GESTURE_EDGE = {0x0B: "volume", 0x0A: "brightness"}

KEYS = {
    ("volume", -1): e.KEY_VOLUMEUP,
    ("volume", 1): e.KEY_VOLUMEDOWN,
    ("brightness", -1): e.KEY_BRIGHTNESSUP,
    ("brightness", 1): e.KEY_BRIGHTNESSDOWN,
}

args = None


def log(*parts):
    print(*parts, flush=True)


def debug(*parts):
    if args.debug:
        log(*parts)


def find_touchpad():
    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            dev = InputDevice(path)
        except OSError:
            continue
        if dev.name == TOUCHPAD_NAME:
            return dev
        dev.close()
    return None


def find_hidraw():
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(f"{node}/device/uevent") as f:
                if HID_NAME in f.read():
                    return "/dev/" + os.path.basename(node)
        except OSError:
            pass
    return None


def hidioc_sfeature(size):
    return (3 << 30) | (size << 16) | (ord("H") << 8) | 0x06


class FreeTouch:
    """Vendor-collection access: enable firmware gestures, read tick reports."""

    def __init__(self):
        self.fd = None

    def open(self):
        path = find_hidraw()
        if not path:
            log("touchpad hidraw node not found")
            return False
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except OSError as err:
            log(f"cannot open {path}: {err} (is the udev rule installed?)")
            return False
        self.enable()
        return True

    def cmd(self, c, v):
        fcntl.ioctl(self.fd, hidioc_sfeature(3), bytearray([0x08, c, v]))

    def enable(self):
        try:
            for c, v in ((0x6D, 1), (0x67, SENSITIVITY), (0x68, args.strength),
                         (0x6B, EDGE_GESTURES), (0x6C, KNUCKLE_GESTURES)):
                self.cmd(c, v)
            debug("FreeTouch enabled")
        except OSError as err:
            log(f"FreeTouch enable failed: {err}")

    def disable(self):
        if self.fd is None:
            return
        try:
            self.cmd(0x6D, 0)
            log("FreeTouch disabled")
        except OSError:
            pass

    def read_ticks(self):
        """Return the list of (state, gesture_id) tick reports waiting."""
        ticks = []
        while True:
            try:
                data = os.read(self.fd, 128)
            except BlockingIOError:
                return ticks
            if len(data) >= 8 and data[0] == 0x51 and data[1] == 0x97:
                ticks.append((data[6], data[7]))


def run(ft):
    dev = None
    while dev is None:
        dev = find_touchpad()
        if dev is None:
            time.sleep(2)

    absinfo = dict(dev.capabilities(absinfo=True)[e.EV_ABS])
    max_x = absinfo[e.ABS_X].max
    ui = UInput({e.EV_KEY: list(KEYS.values())}, name="huawei-freetouch-keys")

    firmware = ft.open()
    log("mode:", "firmware ticks" if firmware else "fallback distance stepping")

    def press(key):
        ui.write(e.EV_KEY, key, 1)
        ui.syn()
        ui.write(e.EV_KEY, key, 0)
        ui.syn()

    x = y = 0
    fingers = 0           # >0 while 2+ fingers are down
    last_touch_end = time.monotonic()
    # fallback state
    mode = None
    anchor_y = None
    moved = False

    fds = [dev.fd] + ([ft.fd] if firmware else [])
    while True:
        ready, _, _ = select.select(fds, [], [])

        if dev.fd in ready:
            for event in dev.read():
                if event.type == e.EV_ABS:
                    if event.code == e.ABS_X:
                        x = event.value
                    elif event.code == e.ABS_Y:
                        y = event.value
                elif event.type == e.EV_KEY:
                    if event.code == e.BTN_TOUCH:
                        if event.value:
                            if (firmware and
                                    time.monotonic() - last_touch_end > REENABLE_AFTER_S):
                                ft.enable()
                            mode = "pending"
                        else:
                            last_touch_end = time.monotonic()
                            mode = None
                            anchor_y = None
                    elif event.code in (e.BTN_TOOL_DOUBLETAP, e.BTN_TOOL_TRIPLETAP,
                                        e.BTN_TOOL_QUADTAP):
                        fingers = event.value
                        if event.value:
                            mode = "dead"
                elif event.type == e.EV_SYN and event.code == e.SYN_REPORT:
                    if not firmware:
                        if mode == "pending" and not fingers:
                            if x >= max_x * (1 - EDGE_FRACTION):
                                mode = "volume"
                            elif x <= max_x * EDGE_FRACTION:
                                mode = "brightness"
                            else:
                                mode = "dead"
                            anchor_y, moved = y, False
                        if mode in ("volume", "brightness"):
                            delta = y - anchor_y
                            if abs(delta) >= DEADZONE_UNITS or moved:
                                moved = True
                                while abs(delta) >= STEP_UNITS:
                                    d = -1 if delta < 0 else 1
                                    press(KEYS[(mode, d)])
                                    anchor_y += d * STEP_UNITS
                                    delta = y - anchor_y

        if firmware and ft.fd in ready:
            # The firmware reports the contact as lifted while it owns an edge
            # slide, so evdev state is useless here: trust the report alone.
            for state, gid in ft.read_ticks():
                edge = GESTURE_EDGE.get(gid)
                direction = -1 if state == 0 else 1
                debug(f"tick id={gid:#04x} state={state} -> {edge} {direction}")
                if edge:
                    press(KEYS[(edge, direction)])


def main():
    global args
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strength", type=int, default=2, choices=(1, 2, 3),
                        help="haptic tick strength: 1 low, 2 medium (default), 3 high")
    parser.add_argument("--debug", action="store_true",
                        help="log every firmware tick")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    ft = FreeTouch()
    try:
        run(ft)
    except KeyboardInterrupt:
        pass
    finally:
        ft.disable()


if __name__ == "__main__":
    main()
