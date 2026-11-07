#!/usr/bin/env python3
"""Codex の SessionStart に SDLC の現在状態を渡す。"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import _common as hook

try:
    hook.prepare(hook.read_input())
    if hook.sdlc_project(hook.PROJECT_DIR):
        from sdlc_lib.config import resolve_body_file

        sdlc = resolve_body_file("bin/sdlc", hook.PROJECT_DIR)
        if sdlc:
            result = subprocess.run([sys.executable, str(sdlc), "status"], cwd=hook.PROJECT_DIR,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=15, env=dict(os.environ, PYTHONUTF8="1"))
            if result.returncode == 0 and result.stdout.strip():
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": result.stdout.strip() + "\n\n続きから進めるには $sdlc を指定してください。",
                }}, ensure_ascii=False))
except (OSError, ValueError, subprocess.TimeoutExpired):
    pass
