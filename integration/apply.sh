#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
host=$(CDPATH= cd -- "${1:?usage: apply.sh /path/to/HoofTTY}" && pwd)
# Never reset or overwrite user modifications. git apply checks all hunks first.
if git -C "$host" apply --reverse --check "$root/integration/hooftty-v0.1.1.patch" 2>/dev/null; then
    echo 'HoofTTY interface patch already applied'
else
    git -C "$host" apply --check "$root/integration/hooftty-v0.1.1.patch"
    git -C "$host" apply "$root/integration/hooftty-v0.1.1.patch"
fi
if [ -e "$host/apps/tpd.c" ]; then
    cmp "$root/src/tpd.c" "$host/apps/tpd.c" || {
        echo 'apps/tpd.c differs: preserve/reconcile it before integration' >&2; exit 1;
    }
else
    cp "$root/src/tpd.c" "$host/apps/tpd.c"
fi
cmp "$root/src/abi.h" "$host/apps/abi.h"
echo 'TPD integrated; run make iso check in HoofTTY'
