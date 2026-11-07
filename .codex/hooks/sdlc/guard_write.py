#!/usr/bin/env python3
"""Codex の apply_patch / Edit / Write に対してゲート・受入結果・本体を保護する。"""
from __future__ import annotations

import os
import re
from pathlib import Path

from _common import allow, deny, maintenance, run, sdlc_project

from sdlc_lib import gates
from sdlc_lib.config import (GATES_DIR, RESULTS_FILE, is_protected, is_user_body_path, load_project,
                             main_root, phase_of_path, project_problems, under, worktree_root)

MAINT_HINT = "変更が必要なら人が編集するか、SDLC_MAINTENANCE=1 で Codex を起動してください。"
RESULTS_FILES = (RESULTS_FILE, RESULTS_FILE[:-3] + ".xlsx")


PATCH_FILE = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.MULTILINE)


def target_paths(data: dict) -> list[Path]:
    tool_input = data.get("tool_input") or {}
    if isinstance(tool_input, str):
        paths = PATCH_FILE.findall(tool_input)
        workdir = None
    else:
        patch = tool_input.get("command") or tool_input.get("patch") or tool_input.get("input")
        if isinstance(patch, str):
            paths = PATCH_FILE.findall(patch)
        else:
            path = tool_input.get("file_path") or tool_input.get("path")
            paths = [path] if path else []
        workdir = tool_input.get("workdir")
    base = Path(data.get("cwd") or os.getcwd())
    if workdir:
        base /= workdir
    return [Path(os.path.realpath(base / Path(p.strip()).expanduser())) for p in paths]


def check(data: dict):
    paths = target_paths(data)
    if not paths and data.get("tool_name") == "apply_patch":
        deny("パッチの変更先を判定できません。")
    for path in paths:
        check_path(path)
    allow()


def check_path(path: Path):
    if not maintenance() and is_user_body_path(path):
        deny(f"{path} はユーザ配置の SDLC ワークフロー本体または Codex 設定です。{MAINT_HINT}")
    wroot = worktree_root(path)
    if wroot is None:
        return
    try:
        rel = path.relative_to(wroot).as_posix()
    except ValueError:
        return
    mroot = main_root(wroot) or wroot
    if not sdlc_project(mroot):
        return

    if under(rel, GATES_DIR):
        deny("state/gates/ への書き込みは禁止です。承認は人が端末で `scripts/approve <工程>` を実行して記録します。")
    if is_protected(rel) and not maintenance():
        deny(f"{rel} はワークフロー本体（ゲートの強制機構）のため編集できません。{MAINT_HINT}")
    if rel in RESULTS_FILES:
        deny(f"{rel} は受入確認の結果シートです。結果は人が記入します（Codex は記入しない）。"
             "TC の反映は `scripts/sdlc testitems sheet`、再確認は `scripts/sdlc testitems reset` を使ってください。")

    proj = load_project(mroot) or load_project(wroot)
    if project_problems(proj):
        if rel.startswith(("docs/", "input/")):
            deny("project.yaml が未作成・不完全です。先に $sdlc-init を実行してください。")
        return

    phase = phase_of_path(rel, proj)
    if phase is None:
        return

    files = gates.list_files(mroot)
    bad = gates.prerequisites(mroot, proj, phase, files)
    if bad:
        lines = "\n".join(f"  ✘ {s['phase']}: {s['reason']}" for s in bad)
        deny(f"{rel} は工程 {phase} の成果物です。前の人間ゲートが有効でないため書き込めません:\n{lines}\n"
             "人による承認（scripts/approve）を待つか、承認後の変更なら $change（仕様の変更）で扱ってください。")
    own = gates.gate_status(mroot, proj, phase, files)
    if own["valid"]:
        deny(f"{rel} は人が承認済みの工程 {phase} の成果物です。仕様を変えるなら $change、"
             "作り間違いなら $defect でやり直しを開始してから変更してください。")


if __name__ == "__main__":
    run(check)
