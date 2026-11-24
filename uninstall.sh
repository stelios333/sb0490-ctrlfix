#!/usr/bin/env bash
#
# Remove the SB0490 remote-control helper for the current user.
#
set -euo pipefail

SCRIPT="$HOME/.local/bin/sb0490-remote.py"
UNIT="$HOME/.config/systemd/user/sb0490-remote.service"

systemctl --user disable --now sb0490-remote.service 2>/dev/null || true
rm -f "$UNIT" "$SCRIPT"
systemctl --user daemon-reload

echo "Removed $SCRIPT and $UNIT"
