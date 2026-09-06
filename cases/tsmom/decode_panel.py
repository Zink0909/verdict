#!/usr/bin/env python3
"""Decode the blob printed by `qc_export.py` into `data/panel.csv`.

    micromamba run -n verdict python cases/tsmom/decode_panel.py paste.txt

`paste.txt` is whatever you copied out of the notebook. The BEGIN/END markers,
the surrounding chatter and the line breaks inside the blob are all tolerated,
so paste generously rather than carefully.

If the notebook printed an md5, pass it with --md5 and the decode is checked
against it. That check is the whole reason the md5 is printed: a silently
truncated paste produces a shorter panel that still parses, and a case that
silently ran on nine years instead of sixteen would be worse than one that
failed loudly.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEGIN, END = "=== BEGIN PANEL BLOB ===", "=== END PANEL BLOB ==="


def extract(text: str) -> str:
    if BEGIN in text and END in text:
        text = text.split(BEGIN, 1)[1].split(END, 1)[0]
    return re.sub(r"[^A-Za-z0-9+/=]", "", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paste", help="file holding the pasted notebook output")
    ap.add_argument("--out", default=str(HERE / "data" / "panel.csv"))
    ap.add_argument("--md5", default=None, help="the md5 the notebook printed")
    args = ap.parse_args()

    blob = extract(Path(args.paste).read_text())
    if not blob:
        print("No base64 payload found in that file.")
        return 2
    try:
        payload = gzip.decompress(base64.b64decode(blob)).decode()
    except Exception as exc:
        print(f"Could not decode the blob ({type(exc).__name__}: {exc}).\n"
              f"The usual cause is a truncated paste — recopy from {BEGIN}.")
        return 2

    got = hashlib.md5(payload.encode()).hexdigest()
    if args.md5 and got != args.md5:
        print(f"md5 mismatch: notebook said {args.md5}, decoded {got}.\n"
              f"The paste is incomplete or altered. Nothing written.")
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload)

    header = [ln for ln in payload.splitlines() if ln.startswith("#")]
    rows = sum(1 for ln in payload.splitlines() if ln and not ln.startswith("#")) - 1
    print(f"wrote {out}  ({rows} month-end rows, md5 {got})")
    for ln in header:
        print(" ", ln.lstrip("# "))
    print("\nnext:  micromamba run -n verdict python cases/tsmom/run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
