"""Export or verify the committed OpenAPI artifact.

The executable specification remains ``app.routes.openapi.openapi_spec``.
The JSON artifact gives language-specific generators a stable local input and
``--check`` prevents it from drifting from that source.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND_ROOT / "openapi.json"
sys.path.insert(0, str(BACKEND_ROOT))

from app.routes.openapi import openapi_spec  # noqa: E402


def rendered_spec() -> str:
    return json.dumps(openapi_spec(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed artifact differs instead of overwriting it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = rendered_spec()
    output = args.output.resolve()
    if args.check:
        actual = output.read_text(encoding="utf-8") if output.exists() else None
        if actual != expected:
            print(f"OpenAPI artifact is stale: {output}")
            print("Run: python scripts/export_openapi.py")
            return 1
        print(f"OpenAPI artifact is current: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
