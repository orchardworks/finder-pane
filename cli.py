#!/usr/bin/env python3
"""finder-pane CLI — Finder-like file browser for macOS."""

import os
import sys

VERSION = "0.2.0"
DEFAULT_PORT = 8234
PORT_RANGE = 10

USAGE = f"""\
finder-pane {VERSION} — Finder-like file browser for macOS

Usage:
  finder-pane open [PATH]        Open PATH (default: cwd) in a cmux browser pane
  finder-pane start [PORT]       Start the server (default port: {DEFAULT_PORT})
  finder-pane stop               Stop the running server
  finder-pane restart             Stop and start the server
  finder-pane status             Check if the server is running
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

    server_py = os.path.join(os.path.dirname(os.path.realpath(__file__)), "server.py")
    os.execvp(sys.executable, [sys.executable, server_py, str(port)])


def _find_my_server():
    """Scan port range and return the port running this user's finder-pane, or None."""
    import json
    import urllib.request
    home = os.path.expanduser("~")
    for port in range(DEFAULT_PORT, DEFAULT_PORT + PORT_RANGE):
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
            data = json.loads(resp.read())
            if data.get("app") == "finder-pane" and data.get("home") == home:
                return port
        except Exception:
            continue
    return None


def _start_server_background():
    """Start the server (it will find an available port itself). Return the port or None."""
    import subprocess
    import time
    server_py = os.path.join(os.path.dirname(os.path.realpath(__file__)), "server.py")
    subprocess.Popen(
        [sys.executable, server_py, str(DEFAULT_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        time.sleep(0.25)
        port = _find_my_server()
        if port is not None:
            return port
    return None


def cmd_open(args):
    path = os.path.abspath(args[0]) if args else os.getcwd()

    port = _find_my_server()
    if port is None:
        print("Starting server...", file=sys.stderr)
        port = _start_server_background()
        if port is None:
            print("Failed to start server", file=sys.stderr)
            sys.exit(1)

    import subprocess
    url = f"http://localhost:{port}{path}"
    subprocess.run(["cmux", "browser", "open", url])


def _stop_server(port):
    """Send shutdown request to the server. Returns True if successful."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/shutdown",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def cmd_stop(args):
    port = _find_my_server()
    if port is None:
        print("not running")
        return
    if _stop_server(port):
        print(f"stopped (was on port {port})")
    else:
        print("failed to stop server", file=sys.stderr)
        sys.exit(1)


def cmd_restart(args):
    port = _find_my_server()
    if port is not None:
        _stop_server(port)
        import time
        # Wait for port to be released
        for _ in range(20):
            time.sleep(0.25)
            if _find_my_server() is None:
                break

    print("Starting server...", file=sys.stderr)
    port = _start_server_background()
    if port is None:
        print("Failed to start server", file=sys.stderr)
        sys.exit(1)
    print(f"running on port {port}")


def cmd_status(args):
    port = _find_my_server()
    if port is not None:
        print(f"running on port {port}")
    else:
        print("not running")
        sys.exit(1)


def cmd_install_skill():
    project_root = os.path.dirname(os.path.realpath(__file__))
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

    if cmd == "open":
        cmd_open(args[1:])
    elif cmd == "start":
        cmd_start(args[1:])
    elif cmd == "stop":
        cmd_stop(args[1:])
    elif cmd == "restart":
        cmd_restart(args[1:])
    elif cmd == "status":
        cmd_status(args[1:])
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
