"""Writes contracts/openapi.json, the contract the web client is generated from.

Run after any API change:  uv run python -m app.export_openapi
"""

import json

from app.core.config import REPO_ROOT
from app.core.logging import configure_logging, get_logger
from app.main import create_app

CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi.json"


def render_contract() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    configure_logging()
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(render_contract())
    get_logger("contract").info("Wrote %s", CONTRACT_PATH)


if __name__ == "__main__":
    main()
