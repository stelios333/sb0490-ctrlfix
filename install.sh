#!/usr/bin/env bash
#
# Install the SB0490 remote-control helper for the current user.
#
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"
SCRIPT="$BIN_DIR/sb0490-remote.py"
UNIT="$UNIT_DIR/sb0490-remote.service"

die() { echo "error: $*" >&2; exit 1; }

# --- preconditions -----------------------------------------------------------

[ -f /proc/asound/hwdep ] || die "ALSA is not available (/proc/asound/hwdep missing)"
grep -qi "remote control" /proc/asound/hwdep 2>/dev/null || \
    echo "warning: no 'SB remote control' hwdep found; is the card plugged in?" >&2

for cmd in python3 systemctl wpctl amixer; do
    command -v "$cmd" >/dev/null 2>&1 || die "missing dependency: $cmd"
done

# --- install -----------------------------------------------------------------

install -Dm755 "$REPO_DIR/sb0490-remote.py" "$SCRIPT"
install -Dm644 "$REPO_DIR/systemd/sb0490-remote.service" "$UNIT"

systemctl --user daemon-reload
systemctl --user enable sb0490-remote.service
systemctl --user restart sb0490-remote.service

# --- report ------------------------------------------------------------------

echo
echo "Installed:"
echo "  $SCRIPT"
echo "  $UNIT"
echo
systemctl --user --no-pager --lines=0 status sb0490-remote.service || true
echo
echo "Turn the volume wheel or press the mute button to test."
echo "Logs: journalctl --user -u sb0490-remote -f"
