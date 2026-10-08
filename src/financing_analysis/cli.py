"""Command-line interface for the project checkout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .excel_engine import WorkbookEngine, summarize_verification
from .workbook_io import load_snapshot, save_snapshot, snapshot_from_xlsx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recalculate and analyze the academic financing workbook"
    )
    parser.add_argument(
        "command", choices=["run", "verify", "import-excel"], nargs="?", default="run"
    )
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--excel", type=Path, help="Original workbook; needed only for import-excel"
    )
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    if args.command == "import-excel":
        if args.excel is None:
            parser.error("import-excel requires --excel")
        destination = args.output_dir
        if destination is None:
            parser.error("import-excel requires --output-dir for a separate snapshot directory")
        destination.mkdir(parents=True, exist_ok=True)
        snapshot_path = destination / "workbook_snapshot.json"
        save_snapshot(snapshot_from_xlsx(args.excel), snapshot_path)
        print(f"Imported snapshot: {snapshot_path}")
        return 0
    if args.command == "verify":
        rows = WorkbookEngine(load_snapshot(root / "data/source/workbook_snapshot.json")).verify()
        summary = summarize_verification(rows)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return int(summary["mismatches"] != 0)
    from .pipeline import run_analysis

    result = run_analysis(root, args.output_dir)
    print(json.dumps(result["verification_summary"], ensure_ascii=False, indent=2))
    print(f"Report: {result['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
