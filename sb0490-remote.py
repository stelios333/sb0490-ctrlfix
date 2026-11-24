#!/usr/bin/env python3
"""
Creative Sound Blaster Live! 24-bit External (SB0490) remote-control helper.

Why this exists
---------------
The SB0490's volume wheel and mute button are *not* HID keys and they do not
move any standard USB Audio mixer control.  They are delivered as
Sound Blaster infrared remote-control codes over the AudioControl interrupt
endpoint; the kernel decodes them and exposes them through the ALSA hwdep
device "SB remote control" (SNDRV_HWDEP_IFACE_SB_RC), see
snd_usb_soundblaster_remote_init() in sound/usb/mixer_quirks.c.

The in-kernel handler only reacts to the MUTE code (by re-reading the Feature
Unit mute control).  Nothing consumes the VOL+/VOL- codes, which is why the
wheel appears dead, and the mute state latch is left to userspace, which is
why the button only ever mutes.

This daemon reads the codes and maps them onto the PipeWire default sink:
    MUTE    -> toggle sink mute + hardware PCM mute switch
    VOL+    -> sink volume +5%
    VOL-    -> sink volume -5%

No kernel changes required.
"""

import os
import re
import select
import shutil
import struct
import subprocess
import sys
import time

# Key codes: the low byte is the actual button code, the high byte is its
# one's complement (e.g. mute = 0x6e91).
KEY_MUTE = 0x91
KEY_VOL_UP = 0x9D
KEY_VOL_DOWN = 0x9C

VOL_STEP = "5%"
MAX_VOLUME = "1.0"  # clamp at 100%; wpctl's relative steps do not clamp by default
HWDEP_PATTERN = re.compile(r"^(\d+)-00: .*remote control", re.MULTILINE)

WPCTL = shutil.which("wpctl") or "/usr/bin/wpctl"
AMIXER = shutil.which("amixer") or "/usr/bin/amixer"
SINK = "@DEFAULT_AUDIO_SINK@"


def log(msg):
    print(f"sb0490-remote: {msg}", file=sys.stderr, flush=True)


def find_card():
    """Return the ALSA card index that owns the SB remote hwdep, or None."""
    try:
        with open("/proc/asound/hwdep", "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    m = HWDEP_PATTERN.search(text)
    return int(m.group(1)) if m else None


def run(argv):
    try:
        subprocess.run(argv, check=False, timeout=3,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"{argv[0]} failed: {exc}")


def is_muted():
    try:
        out = subprocess.run([WPCTL, "get-volume", SINK],
                             capture_output=True, text=True, timeout=3).stdout
        return "[MUTED]" in out
    except (OSError, subprocess.SubprocessError):
        return False


def apply_mute(muted, card):
    # Drive both layers: the USB Audio Feature Unit mute (hardware) and the
    # PipeWire sink mute (software).  Setting the ALSA switch also makes
    # WirePlumber's saved route state follow along.
    run([AMIXER, "-c", str(card), "cset",
         "name=PCM Playback Switch", "off" if muted else "on"])
    run([WPCTL, "set-mute", SINK, "1" if muted else "0"])
    log("muted" if muted else "unmuted")


def change_volume(delta):
    run([WPCTL, "set-volume", "-l", MAX_VOLUME, SINK, f"{VOL_STEP}{delta}"])
    log(f"volume {delta}")


def drain(fd):
    """Discard codes queued before we started (e.g. from an earlier press)."""
    while True:
        r, _, _ = select.select([fd], [], [], 0)
        if not r:
            return
        try:
            if not os.read(fd, 4):
                return
        except (BlockingIOError, OSError):
            return


def main():
    muted = None  # unknown until first initialization

    while True:
        card = find_card()
        if card is None:
            time.sleep(2)
            continue

        path = f"/dev/snd/hwC{card}D0"
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            time.sleep(2)
            continue

        log(f"listening on {path}")
        drain(fd)
        if muted is None:
            muted = is_muted()

        try:
            while True:
                r, _, _ = select.select([fd], [], [], 2.0)
                if not r:
                    # Detect unplug / renumbering.
                    if find_card() != card:
                        log("device disappeared")
                        break
                    continue
                try:
                    data = os.read(fd, 4)
                except BlockingIOError:
                    continue
                except OSError:
                    break
                if len(data) < 4:
                    continue

                code = struct.unpack("<I", data)[0]
                key = code & 0xFF

                if key == KEY_MUTE:
                    muted = not muted
                    apply_mute(muted, card)
                elif key == KEY_VOL_UP:
                    change_volume("+")
                elif key == KEY_VOL_DOWN:
                    change_volume("-")
                else:
                    log(f"ignored code {code:#010x}")
        finally:
            os.close(fd)

        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
