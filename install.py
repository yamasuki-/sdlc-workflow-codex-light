#!/usr/bin/env python3
"""SDLC ワークフロー（軽量版）本体のインストーラ（人が実行する）。

  python3 install.py --user               # ~/.codex/ に置く（全プロジェクト共通。既定）
  python3 install.py --project <dir>      # <dir>/.codex/ に置く（そのプロジェクト単体で使う／~/.codex 版を上書き）
  python3 install.py --user --uninstall   # 取り除く（--project も同様）
  Windows では PowerShell / コマンドプロンプトで py -3 install.py ...（または python install.py ...）
  オプション: --dry-run（何をするか表示するだけ）

配置先は Codex の設定・本体（.codex または CODEX_HOME）とスキル（.agents/skills）。
既存の hooks.json には SDLC のハンドラを追記し、他のハンドラを保持します。
インストール後は USAGE.md の初期化手順と Codex CLI の /hooks での信頼設定に従います。

更新は 1 ファイルずつ行い、置いたファイルとそのハッシュを sdlc/.install-manifest.json に記録する。
インストール後に変更されたファイル・インストーラが置いていないファイル（プロジェクトでの上書きなど）は
変更・削除せずに報告する（--force で置き換える）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC / ".codex" / "sdlc" / "lib"))

from sdlc_lib.config import BODY_DIRS, BODY_FILES, user_codex_dir, utf8_stdio  # noqa: E402

utf8_stdio()

HOOKS = [
    ("PreToolUse", "^(apply_patch|Edit|Write)$", "guard_write.py", 60),
    ("PreToolUse", "^Bash$", "guard_bash.py", 60),
    ("SessionStart", "^(startup|resume)$", "session_start.py", 30),
]
MANIFEST = "sdlc/.install-manifest.json"
MARK = "/hooks/sdlc/run"


def hook_commands(scope: str, script: str) -> tuple[str, str]:
    if scope == "project":
        path = f".codex{MARK}"
        return (f'bash "$(git rev-parse --show-toplevel)/{path}" {script}',
                f"bash ((git rev-parse --show-toplevel) + '/{path}') {script}")
    path = (user_codex_dir() / MARK.lstrip("/")).as_posix()
    win_path = path.replace("'", "''")
    return f"bash {shlex.quote(path)} {script}", f"bash '{win_path}' {script}"


def merged_hooks(settings: dict, scope: str, remove: bool = False) -> dict:
    result = json.loads(json.dumps(settings))
    hooks = result.setdefault("hooks", {})
    for event in dict.fromkeys(e for e, *_ in HOOKS):
        groups = []
        for group in hooks.get(event, []):
            handlers = [h for h in group["hooks"] if MARK not in h.get("command", "")]
            if handlers:
                groups.append({**group, "hooks": handlers})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if not remove:
        for event, matcher, script, timeout in HOOKS:
            command, command_windows = hook_commands(scope, script)
            hooks.setdefault(event, []).append({"matcher": matcher, "hooks": [{
                "type": "command", "command": command, "commandWindows": command_windows, "timeout": timeout,
            }]})
    if not hooks:
        result.pop("hooks", None)
    return result


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source_files() -> dict[str, Path]:
    """配置先のルートからの相対パス → ソースのファイル。"""
    out = {}
    for d in BODY_DIRS:
        for p in sorted((SRC / d).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                out[p.relative_to(SRC).as_posix()] = p
    for f in BODY_FILES:
        if (SRC / f).is_file():
            out[f] = SRC / f
    return out


def sync(root: Path, config_dir: Path, uninstall: bool, force: bool, dry: bool) -> dict:
    """ファイル単位で配置・更新・削除する。変更されたファイルは force でなければ残す。"""
    def destination(rel: str) -> Path:
        return config_dir / rel.removeprefix(".codex/") if rel.startswith(".codex/") else root / rel

    mp = config_dir / MANIFEST
    manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    src = {} if uninstall else source_files()
    new_manifest, report = {}, {"placed": [], "updated": [], "removed": [], "kept": []}
    for rel in sorted(set(src) | set(manifest)):
        dst = destination(rel)
        installed = manifest.get(rel)
        user_changed = dst.exists() and (installed is None or sha(dst) != installed)
        if rel in src:
            if dst.exists() and sha(dst) == sha(src[rel]):
                new_manifest[rel] = sha(dst)
                continue
            if user_changed and not force:
                report["kept"].append(rel)
                if installed:
                    new_manifest[rel] = installed  # 変更前の記録を残し、次回も変更ありとして扱う
                continue
            report["updated" if dst.exists() else "placed"].append(rel)
            if not dry:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src[rel].read_bytes())
                dst.chmod(src[rel].stat().st_mode & 0o777)
            new_manifest[rel] = sha(src[rel])
        elif dst.exists():  # ソースから無くなった・アンインストール
            if user_changed and not force:
                report["kept"].append(rel)
                new_manifest[rel] = installed
                continue
            report["removed"].append(rel)
            if not dry:
                dst.unlink()
    if not dry:
        if new_manifest:
            mp.parent.mkdir(parents=True, exist_ok=True)
            mp.write_text(json.dumps(new_manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        elif mp.exists():
            mp.unlink()
        for d in sorted({destination(r).parent for r in set(manifest) | set(src)}, key=lambda p: -len(p.parts)):
            while d not in (root, config_dir) and d.exists() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--user", action="store_true", help="~/.codex/ に置く（既定）")
    g.add_argument("--project", metavar="DIR", help="DIR/.codex/ に置く")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--force", action="store_true", help="インストール後に変更されたファイルも置き換える・削除する")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    scope = "project" if a.project else "user"
    root = Path(a.project).resolve() if a.project else Path.home()
    config_dir = root / ".codex" if a.project else user_codex_dir()
    if root.resolve() == SRC or config_dir == SRC / ".codex":
        sys.exit("エラー: ソースリポジトリ自身にはインストールできません（既にこの配置です）。")
    if a.project and not (root / ".git").exists():
        sys.exit("エラー: --project には Git リポジトリのルートを指定してください。")
    sp = config_dir / "hooks.json"
    settings = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    new = merged_hooks(settings, scope, remove=a.uninstall)
    print(f"{'アンインストール' if a.uninstall else 'インストール'}先: {config_dir} と {root / '.agents'}（{scope}）")
    rep = sync(root, config_dir, a.uninstall, a.force, a.dry_run)
    for key, label in (("placed", "配置"), ("updated", "更新"), ("removed", "削除")):
        if rep[key]:
            print(f"  {label}: {len(rep[key])} ファイル")
    if rep["kept"]:
        print("  次のファイルはインストール後に変更された（またはインストーラが置いていない）ため、そのままにしました"
              "（置き換えるなら --force）:")
        for r in rep["kept"]:
            print(f"    {r}")
    if new != settings:
        print("  更新: hooks.json（SDLC フック）")
        if not a.dry_run:
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.dry_run:
        print("（--dry-run のため変更していません）")
    elif not a.uninstall:
        print("\n次の手順: USAGE.md の初期化手順を実行し、Codex CLI の /hooks でフックを確認・信頼してください。")


if __name__ == "__main__":
    main()
