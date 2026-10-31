"""Write the FastAPI OpenAPI document that the frontend client types are generated from.

    python scripts/export_openapi.py [OUTPUT]   # default frontend/lib/api/openapi.json
"""

import json
import sys
from pathlib import Path

from citehop.api.main import app

DEFAULT = Path(__file__).resolve().parents[1] / "frontend" / "lib" / "api" / "openapi.json"

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out}")
