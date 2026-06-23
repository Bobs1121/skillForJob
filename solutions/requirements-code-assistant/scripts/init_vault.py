from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "vault"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    parser.add_argument("--project", default="Project")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    destination = Path(args.destination).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()) and not args.force:
        raise SystemExit(f"destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE, destination, dirs_exist_ok=True)
    for path in destination.rglob("*.md"):
        text = path.read_text(encoding="utf-8").replace(
            "{{PROJECT_NAME}}", args.project
        )
        path.write_text(text, encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

