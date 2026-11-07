#!/usr/bin/env python3
"""PreToolUse(Bash|PowerShell): シェル経由での承認・ゲート記録・結果シート・ワークフロー本体の改変を検出して拒否する。

Windows では Codex が PowerShell ツールでコマンドを実行することがあるため、PowerShell の書式も検査する。
シェルの完全な解析はできないためヒューリスティックである。すり抜けた改変も、
人が承認した成果物はゲートのハッシュ不一致で検知され、承認は scripts/approve（人が端末で実行）でしか記録できない。
人間ゲートの無い工程も、前提となる承認が無効な間は検査する。
"""
from __future__ import annotations

import re

from _common import allow, deny, hook_root, maintenance, run, sdlc_project

from sdlc_lib import gates
from sdlc_lib.config import (PROTECTED_PATHS, RESULTS_FILE, load_project, phase_areas, project_problems,
                             user_codex_dir)

SEP = r"(?:^|[;&|(\n{]|\$\()\s*"   # コマンドの区切り（ここから次のコマンドが始まる）
WRITE_PATTERNS = [
    # bash
    r"(?<![0-9&<>-])>{1,2}(?!&)",                    # リダイレクト（2>&1 等は除外）
    r"\btee\b", r"\bsed\b[^|;&]*\s-i", r"\bperl\b[^|;&]*\s-[a-z]*i", r"\bcp\b", r"\bmv\b", r"\brm\b",
    r"\btouch\b", r"\bln\b", r"\bchmod\b", r"\btruncate\b", r"\bdd\b", r"\brsync\b",
    SEP + r"(?:sudo\s+)?install\s",                  # install コマンド（install.py 等の名前は対象外）
    r"\bgit\s+(checkout|restore|reset|rm|mv|apply|stash|clean|revert|cherry-pick)\b",
    r"\bpatch\b", r"\bunzip\b", r"\btar\b[^|;&]*\s-?x",
    # PowerShell / cmd
    r"(?i)\b(set-content|add-content|out-file|new-item|remove-item|move-item|copy-item|rename-item|clear-content"
    r"|set-item|expand-archive)\b",
    r"(?i)" + SEP + r"(?:del|erase|copy|xcopy|robocopy|move|ren|rename|rd|rmdir|sc|ac|ni|ri|mi|cpi|rni)\s",
    r"(?i)\[(?:system\.)?io\.file\]::",
]
NULL_REDIRECTS = re.compile(r"(?i)\d?>{1,2}\s*(?:/dev/null|\$null|nul\b)|\d>&\d|&>\s*/dev/null|\|\s*out-null")
# approve の呼び出し。コマンドの位置にあるもの、または承認の引数（工程番号・オプション）付きのもの
# （cmd /c・Start-Process・script -c 等で間接的に呼ぶ場合も拾う。文字列中の単なる言及は対象外）
APPROVE_CALL = re.compile(
    SEP + r"(?:&\s*)?(?:(?:sudo|env|exec|nohup|python3?|py|bash|sh|cmd(?:\.exe)?\s+/c)\s+)*"
    r"['\"]?(?:\S*/)?approve(?:\.cmd|\.ps1|\.bat)?['\"]?(?:\s|$|[;&|)])"
    r"|(?:\S*/)?approve(?:\.cmd|\.ps1|\.bat)?['\"]?\s+(?:-|\d)", re.IGNORECASE)
# ワークフロー本体のインストーラ（~/.codex や .codex/ を書き換える）。他の install.py と区別するためオプションで判定
INSTALL_CALL = re.compile(r"(?:\S*/)?install\.py\b[^;&|\n]*--(user|project|uninstall)\b")
# ~/.codex 配下の本体と設定（どのプロジェクトからでも保護する）
HOME_FORMS = (r"(?:~|\$HOME|\$\{HOME\}|\$env:(?:USERPROFILE|HOME)|%USERPROFILE%|/root|/home/[^/\s]+"
              r"|[a-z]:/users/[^/\s]+|/[a-z]/users/[^/\s]+)")
USER_BODY = re.compile(r"(?:" + HOME_FORMS + r"/|(?:\$CODEX_HOME|\$\{CODEX_HOME\}|\$env:CODEX_HOME)/)"
                       + r"(?:" + "|".join(re.escape(p) for p in PROTECTED_PATHS if p.startswith("."))
                       + r"|(?:sdlc|hooks/sdlc|config\.toml|hooks\.json|agents/[^/\s]+\.toml))(?=/|[\s'\";|]|$)", re.IGNORECASE)
RESULTS = re.compile(re.escape(RESULTS_FILE[:-3]) + r"\.(md|xlsx)\b|\bresults\.(md|xlsx)\b")


def writes(cmd: str) -> bool:
    c = NULL_REDIRECTS.sub(" ", cmd)
    return any(re.search(p, c) for p in WRITE_PATTERNS)


def mentions(cmd: str, prefix: str) -> bool:
    return bool(prefix) and re.search(r"(^|[\s'\"=/:(])(\./)?" + re.escape(prefix) + r"(/|\b|$)", cmd) is not None


def check(data: dict):
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") or ""
    cmd = (" ".join(command) if isinstance(command, list) else str(command)).replace("\\", "/")  # Windows の区切りを統一
    shell = data.get("tool_name") or "Bash"
    if not maintenance():
        if INSTALL_CALL.search(cmd):
            deny("ワークフロー本体のインストール・更新（install.py）は人が実行してください。")
        if writes(cmd) and (USER_BODY.search(cmd) or any(
                mentions(cmd, (user_codex_dir() / p.removeprefix(".codex/")).as_posix())
                for p in PROTECTED_PATHS if p.startswith(".codex/"))):
            deny(f"~/.codex の設定ファイルと SDLC ワークフロー本体は {shell} から変更できません。")
    root = hook_root(data)
    if not sdlc_project(root):
        allow()
    if APPROVE_CALL.search(cmd):
        deny("scripts/approve は人が端末で実行する承認スクリプトです。Codex は実行できません。"
             "承認が必要な旨を人に伝えて停止してください。")
    if re.search(r"\btestitems\s+(?:import|export)\b", cmd):
        deny("Excel の出力・取り込みは人が端末で実行してください。")
    if not writes(cmd):
        allow()
    if re.search(r"state/gates", cmd):
        deny(f"state/gates/ は {shell} から変更できません（承認は人が scripts/approve で記録します）。")
    if RESULTS.search(cmd):
        deny(f"受入確認の結果シートは {shell} から変更できません（結果は人が記入します。"
             "TC の反映・再確認・Excel の取り込みは scripts/sdlc testitems を使ってください）。")
    if not maintenance():
        for p in PROTECTED_PATHS:
            if mentions(cmd, p):
                deny(f"{p} はワークフロー本体のため {shell} から変更できません。")
    proj = load_project(root)
    if project_problems(proj):
        areas = ["docs/01-specification", "input"]
    else:
        areas = [area for pid, paths in phase_areas(proj).items()
                 if pid in proj["gates"] or gates.prerequisites(root, proj, pid)
                 for area in paths]
    for a in areas:
        if mentions(cmd, a):
            deny(f"人間ゲートで保護される成果物（{a}/）を {shell} で変更しようとしています。ゲートの検査を通すため "
                 "apply_patch を使ってください（参照・git merge・テスト実行は可）。")
    allow()


if __name__ == "__main__":
    run(check)
