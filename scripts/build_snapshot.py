"""Create the portable workbook snapshot from a local copy of the source XLSX."""

from __future__ import annotations

import argparse
from pathlib import Path

from financing_analysis.workbook_io import save_snapshot, snapshot_from_xlsx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    save_snapshot(snapshot_from_xlsx(args.xlsx), args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
