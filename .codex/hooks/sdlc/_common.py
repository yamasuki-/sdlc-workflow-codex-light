"""Codex フックの入力・対象プロジェクト・拒否応答を扱う。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # <base>/.codex/hooks/sdlc
BASE = HERE.parents[1]                           # <base>/.codex
PROJECT_DIR = Path.cwd().resolve()
LOCAL_INSTALL = False
sys.path.insert(0, str(BASE / "sdlc" / "lib"))


def hook_root(data: dict) -> Path:
    from sdlc_lib.config import main_root

    tool_input = data.get("tool_input")
    workdir = tool_input.get("workdir") if isinstance(tool_input, dict) else None
    cwd = Path(data.get("cwd") or os.getcwd())
    start = (cwd / workdir) if workdir else cwd
    return main_root(start) or start.resolve()


# Windows でも Codex とのやり取り（JSON・メッセージ）を UTF-8 で行う
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def read_input() -> dict:
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except ValueError:
        return {}


def deny(msg: str):
    print(f"[SDLC ガード] {msg}", file=sys.stderr)
    sys.exit(2)


def allow():
    sys.exit(0)


def maintenance() -> bool:
    """人が SDLC_MAINTENANCE=1 で Codex を起動した場合のみワークフロー本体の編集を許可する。"""
    return os.environ.get("SDLC_MAINTENANCE") == "1"


def sdlc_project(root) -> bool:
    """この hook が工程の検査をすべきプロジェクトか。"""
    from sdlc_lib.config import is_sdlc_project
    return (LOCAL_INSTALL and Path(root).resolve() == PROJECT_DIR) or is_sdlc_project(root)


def _probably_sdlc() -> bool:
    try:
        return sdlc_project(PROJECT_DIR)
    except Exception:  # noqa: BLE001
        return True


def prepare(data: dict):
    global PROJECT_DIR, LOCAL_INSTALL
    PROJECT_DIR = hook_root(data)
    LOCAL_INSTALL = (PROJECT_DIR / ".codex").resolve() == BASE


def run(fn):
    """ガード本体を実行する。SDLC プロジェクトでの内部エラーは拒否に倒す。"""
    try:
        data = read_input()
        prepare(data)
        fn(data)
    except SystemExit:
        raise
    except Exception as e:
        if not _probably_sdlc():
            allow()
        deny(f"ガードの内部エラーのため拒否しました: {type(e).__name__}: {e}\n"
             "依存関係（pip install -r requirements.txt）と project.yaml を確認してください。")
