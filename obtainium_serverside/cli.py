from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .http import HttpClient
from .models import AppDefinition, InstalledApp
from .planner import plan_updates


def _read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_app_definitions(path: Path) -> list[AppDefinition]:
    payload = _read_json_file(path)
    if not isinstance(payload, dict):
        raise ValueError("configuration JSON must be an object with an apps array")
    apps = payload.get("apps")
    if not isinstance(apps, list):
        raise ValueError("configuration JSON must include an apps array")
    return [AppDefinition.from_dict(item) for item in apps]


def _load_installed_apps(path: Path) -> list[InstalledApp]:
    payload = _read_json_file(path)
    if isinstance(payload, list):
        apps = payload
    elif isinstance(payload, dict):
        apps = payload.get("installed_apps") or payload.get("apps") or []
    else:
        raise ValueError(
            "installed apps JSON must be a list or an object containing installed_apps"
        )

    if not isinstance(apps, list):
        raise ValueError("installed apps JSON must contain a list")
    return [InstalledApp.from_dict(item) for item in apps]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Server-side Obtainium-style artifact resolver")
    parser.add_argument("--config", required=True, help="Path to the app configuration JSON file")
    parser.add_argument(
        "--installed",
        required=True,
        help="Path to the installed apps JSON file containing app_id/version entries",
    )
    parser.add_argument(
        "--download-dir",
        required=False,
        help="Optional directory where artifacts for updates will be downloaded",
    )
    parser.add_argument(
        "--github-token",
        required=False,
        help=(
            "Optional GitHub API token for release checks. If omitted, "
            "DEPENDENCY_UPDATE_GITHUB_TOKEN, GITHUB_TOKEN, or GH_TOKEN is used when set."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    app_definitions = _load_app_definitions(Path(args.config))
    installed_apps = _load_installed_apps(Path(args.installed))
    result = plan_updates(
        app_definitions,
        installed_apps,
        download_dir=Path(args.download_dir) if args.download_dir else None,
        http_client=HttpClient(github_token=args.github_token),
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0
