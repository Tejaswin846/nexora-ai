from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path.home() / ".software-sdk"
CONFIG_FILE = CONFIG_DIR / "config.json"


def save_api_key(api_key: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"api_key": api_key}, indent=2) + "\n", encoding="utf-8")


def configured_api_key() -> str:
    env_key = os.getenv("SOFTWARE_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(data.get("api_key", "")).strip()


def login(api_key: Optional[str]) -> int:
    clean_key = (api_key or os.getenv("SOFTWARE_API_KEY", "")).strip()
    if not clean_key:
        print("No API key saved. Set SOFTWARE_API_KEY=... or run: software login --api-key YOUR_KEY")
        return 0
    save_api_key(clean_key)
    print(f"Software SDK cloud API key saved to {CONFIG_FILE}")
    return 0


def status() -> int:
    if configured_api_key():
        print("Software SDK cloud mode is configured with an API key.")
    else:
        print("Software SDK local mode is ready. Cloud mode is optional and needs SOFTWARE_API_KEY or software login.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="software", description="Software SDK helper")
    subparsers = parser.add_subparsers(dest="command")
    login_parser = subparsers.add_parser("login", help="Save an optional cloud API key")
    login_parser.add_argument("--api-key", default=None, help="Cloud API key")
    subparsers.add_parser("status", help="Show local/cloud SDK configuration")
    args = parser.parse_args(argv)
    if args.command == "login":
        return login(args.api_key)
    if args.command == "status":
        return status()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
