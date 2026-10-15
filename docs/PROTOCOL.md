# Huawei FreeTouch protocol (Goodix GXTP7863, `27C6:01E0`)

Reverse-engineered from Huawei PC Manager on Windows (`FreeTouchHidAPI.dll`,
`FreeTouchPlugin.dll`) and checked against the hardware under Linux. The pad
is a normal I2C-HID precision touchpad; the FreeTouch features live behind its
vendor collection (usage page `0xFF00`), reachable on Linux through `hidraw`.

## Commands: feature report `0x08`

Every setting is a 3-byte SET_FEATURE: `08 <command> <value>`.

| Command | Meaning | Huawei default |
|---|---|---|
| `6d` | FreeTouch enable: `01` on, `00` off. PC Manager sends `01` at start-up. | `01` |
| `67` | Sensitivity | `02` |
| `68` | Haptic ("shock") strength; the Windows UI offers low / mid / high | `02` |
| `6b` | Edge gestures bitmask: bit0 seek, bit1 brightness (left edge), bit2 volume (right edge), bit3 minimize, bit4 close | `1f` |
| `6c` | Knuckle gestures bitmask: bit0 screenshot, bit1 screen recording | `03` |
| `7c` | Fire one haptic pulse (`01`) | — |

The pad answers each command with input report `0x16`: `16 <command> <status> 00`.
Settings are not persistent: the pad forgets them across suspend/resume.

## Gesture ticks: input report `0x51`, sub-type `0x97`

While FreeTouch is enabled and a finger slides along an enabled edge, the
firmware plays a haptic tick and sends, for every tick (~every 80–100 ms on a
steady slide):

```
51 97 <timestamp: uint32 LE, ms> <state> <gesture id>
```

| Gesture id | Edge |
|---|---|
| `0x0b` | right edge (volume) |
| `0x0a` | left edge (brightness) |

`state` is the direction: `0` = finger moving up, `1` = moving down.

While the firmware owns an edge slide, the regular multitouch stream reports
the contact as **lifted**, so tick handling must not depend on evdev touch state.

## Other bits seen in the Windows code

- `ShockFreeTouch()` first tries feature report `0x1a`
  (`1a 8d 3c 00 1e 00 …`, 18 bytes). That report does not exist on this pad,
  so it falls back to `08 7c 01`.
- `51 96 …` (26 bytes) and `51 98 …` are force-press and "big data"
  statistics reports; not needed here.
- Output report `0x15` (1030 bytes) looks like firmware-update traffic. Never send it.
- Other pads in Huawei's list (Elan `04f3:3114/3184/3160`, FocalTech
  `2808:0101`, `347d:7853`) use the same API but are untested.
