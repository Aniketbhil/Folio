#!/usr/bin/env python3
"""Export OpenAPI JSON schema from the Folio FastAPI application.

Validates that every non-dev endpoint defines tags and a response_model.
"""

import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app


def export_openapi() -> None:
    schema = app.openapi()
    out_path = backend_dir / "openapi.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"OpenAPI schema successfully written to {out_path}")

    # Validate non-dev endpoints
    missing_tags = []
    missing_response_models = []

    for route in app.routes:
        if not hasattr(route, "endpoint"):
            continue
        path = getattr(route, "path", "")
        # Skip dev endpoints, swagger/redoc docs, and openapi schema route
        if (
            path.startswith("/dev")
            or path.startswith("/api/v1/dev")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path in ["/openapi.json"]
        ):
            continue

        tags = getattr(route, "tags", [])
        if not tags:
            missing_tags.append((path, route.name))

        response_model = getattr(route, "response_model", None)
        if not response_model:
            missing_response_models.append((path, route.name))

    errors = []
    if missing_tags:
        errors.append(f"Endpoints missing tags: {missing_tags}")
    if missing_response_models:
        errors.append(f"Endpoints missing response_model: {missing_response_models}")

    if errors:
        print("Schema validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"Schema validation passed: all {len(schema.get('paths', {}))} paths conform.")


if __name__ == "__main__":
    export_openapi()
