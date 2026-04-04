#!/usr/bin/env python3
"""finder-pane CLI — Finder-like file browser for macOS."""

import os
import sys

VERSION = "0.1.0"
DEFAULT_PORT = 8234

USAGE = f"""\
finder-pane {VERSION} — Finder-like file browser for macOS

Usage:
  finder-pane start [PORT]       Start the server (default port: {DEFAULT_PORT})
  finder-pane install-skill      Install Claude Code skill
  finder-pane uninstall-skill    Remove Claude Code skill
  finder-pane version            Show version
  finder-pane help               Show this help
"""

SKILL_DIR = os.path.join(os.path.expanduser("~"), ".claude", "skills", "finder-pane")


def cmd_start(args):
    port = DEFAULT_PORT
    if args:
        try:
            port = int(args[0])
        except ValueError:
            print(f"Invalid port: {args[0]}", file=sys.stderr)
            sys.exit(1)

    server_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    os.execvp(sys.executable, [sys.executable, server_py, str(port)])


def cmd_install_skill():
    project_root = os.path.dirname(os.path.abspath(__file__))
    skill_source = os.path.join(project_root, "skill")

    if not os.path.isdir(skill_source):
        print(f"Skill directory not found: {skill_source}", file=sys.stderr)
        sys.exit(1)

    skills_parent = os.path.dirname(SKILL_DIR)
    os.makedirs(skills_parent, exist_ok=True)

    if os.path.islink(SKILL_DIR):
        existing_target = os.readlink(SKILL_DIR)
        if existing_target == skill_source:
            print(f"Skill already installed: {SKILL_DIR} -> {skill_source}")
            return
        os.remove(SKILL_DIR)
        print(f"Replaced existing symlink: {existing_target}")

    if os.path.exists(SKILL_DIR):
        print(f"Path already exists (not a symlink): {SKILL_DIR}", file=sys.stderr)
        print("Remove it manually if you want to reinstall.", file=sys.stderr)
        sys.exit(1)

    os.symlink(skill_source, SKILL_DIR)
    print(f"Installed: {SKILL_DIR} -> {skill_source}")


def cmd_uninstall_skill():
    if os.path.islink(SKILL_DIR):
        os.remove(SKILL_DIR)
        print(f"Removed: {SKILL_DIR}")
    elif os.path.exists(SKILL_DIR):
        print(f"Not a symlink, skipping: {SKILL_DIR}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Skill not installed.")


def main():
    args = sys.argv[1:]

    if not args or args[0] == "help":
        print(USAGE)
        sys.exit(0)

    cmd = args[0]

    if cmd == "start":
        cmd_start(args[1:])
    elif cmd == "install-skill":
        cmd_install_skill()
    elif cmd == "uninstall-skill":
        cmd_uninstall_skill()
    elif cmd == "version":
        print(f"finder-pane {VERSION}")
    else:
        print(f"Unknown command: {cmd}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
