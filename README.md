# sb0490-remote

Make the volume wheel and mute button of the **Creative Sound Blaster Live!
24-bit External (SB0490)** work on Linux.

No kernel patches, no driver rebuilds — just a small userspace daemon.

## The problem

On Linux the SB0490's controls misbehave in a very specific way:

- The **mute button only mutes** — pressing it again never brings the sound back.
- The **volume wheel does nothing at all**.

Both worked under Windows 7.

## Why it happens

The wheel and the mute button are **not** HID keys and they do not move any
standard USB Audio mixer control. The card sends Sound Blaster
**infrared remote-control codes** over the AudioControl interrupt endpoint:

```
06 80 xx yy 22 83      xx = key code, yy = one's complement of xx
```

| Control    | Code     |
|------------|----------|
| Mute       | `0x6e91` |
| Wheel up   | `0x629d` |
| Wheel down | `0x639c` |

The kernel decodes these packets (`snd_usb_soundblaster_remote_init()` in
`sound/usb/mixer_quirks.c`) and exposes them through an ALSA hwdep device
called **"SB remote control"** (`SNDRV_HWDEP_IFACE_SB_RC`, usually
`/dev/snd/hwC1D0`).

However:

- The in-kernel handler only reacts to the **mute** code, and only by
  re-reading the USB Audio Feature Unit mute control. The card sets that bit
  to *muted* on the first press and never clears it, so the mute latches.
- The **VOL+/VOL−** codes are simply published on the hwdep device and
  nothing in a normal desktop consumes them, so the wheel appears dead.

Windows' Creative driver did both jobs in software. This project does the
same on Linux.

## What it does

`sb0490-remote.py` reads the remote-control codes and maps them onto the
PipeWire default sink:

| Control    | Action                                                        |
|------------|---------------------------------------------------------------|
| Mute       | toggles the PipeWire sink mute **and** the hardware PCM switch |
| Wheel up   | volume +5 %                                                   |
| Wheel down | volume −5 %                                                   |

Volume is clamped to 100 %.

## Requirements

- Linux with ALSA and `snd-usb-audio`
- PipeWire + WirePlumber (`wpctl`), or adapt the script to `pactl`
- Python 3 (standard library only)
- `amixer` (alsa-utils)

The card must be supported by the in-kernel quirk above, which covers the
SB0490 (`041e:3040`) and the rebranded Toshiba SB-0500 (`041e:3048`).

## Install

```bash
git clone <this-repo> sb0490-remote
cd sb0490-remote
./install.sh
```

The installer copies:

- `sb0490-remote.py` → `~/.local/bin/`
- `sb0490-remote.service` → `~/.config/systemd/user/`

and enables the user service so it starts with your session and survives
re-plugging the card.

No root, no reboot. Test it by turning the wheel and pressing the button.

## Uninstall

```bash
./uninstall.sh
```

## Configuration

Edit the constants near the top of `sb0490-remote.py`:

```python
VOL_STEP   = "5%"    # volume change per wheel click
MAX_VOLUME = "1.0"   # upper clamp (e.g. "1.5" for 150 % headroom)
```

Then reinstall (`./install.sh`) or copy the file to `~/.local/bin/` and run
`systemctl --user restart sb0490-remote`.

## Verifying / troubleshooting

Check that the card exposes the remote-control device:

```bash
cat /proc/asound/hwdep
# 01-00: SB Live! 24-bit External remote control
```

Watch what the card is sending (press the button or turn the wheel):

```bash
cat /dev/snd/hwC1D0 | xxd      # card number may differ
```

Follow the daemon:

```bash
journalctl --user -u sb0490-remote -f
```

If the card is not plugged in when the service starts, the daemon waits and
picks it up automatically. If the card number changes after a replug, it
re-resolves it.

## Notes

- The hwdep device is exclusive: only one process can read it. Do not run
  `lircd` with the `alsa_usb` driver at the same time.
- Volume is adjusted on the PipeWire default sink, matching what Windows'
  driver did (system volume), not the card's internal attenuation.
- The mute state is tracked by the daemon. If you mute from the desktop
  applet and then press the hardware button, the first press can appear
  inverted; the next press re-syncs.

## License

MIT — see [LICENSE](LICENSE).
