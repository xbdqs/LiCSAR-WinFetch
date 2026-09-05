#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path


def main() -> int:
    payload = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.replace("\n", " "),
        "python_executable": str(Path(sys.executable).name),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
