#!/usr/bin/env python3
"""Send a message to a live Claude Code session that uses a different config directory.

    peer_bridge.py --config-dir ~/.claude-other --list
    peer_bridge.py --config-dir ~/.claude-other --to my-peer --from-name me "hello"

Claude Code lists only peers that share your config directory. This reads the target's
session record and key file from the config directory you name, then writes the same two
lines Claude Code's own client writes to the target's Unix socket: an auth line and one
cross-session-message line. Format read from Claude Code 2.1.317; it is undocumented and
can change in any release.
"""
import argparse
import hashlib
import json
import os
import socket
import sys
import uuid

TAG = "cross-session-message"
MODES = ("acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan")


def live_sessions(sessions_dir: str) -> list[dict]:
    found = []
    for f in sorted(os.listdir(sessions_dir)):
        if not (f.endswith(".json") and f[:-5].isdigit()):
            continue
        with open(os.path.join(sessions_dir, f)) as fh:
            rec = json.load(fh)
        if os.path.exists(f"/proc/{rec['pid']}") and rec.get("messagingSocketPath"):
            found.append(rec)
    return found


def peer_token(sessions_dir: str, rec: dict) -> str:
    digest = hashlib.sha256(rec["messagingSocketPath"].encode()).hexdigest()
    with open(os.path.join(sessions_dir, f"{rec['pid']}.{digest}.key")) as fh:
        return json.load(fh)["peerToken"]


def frame(body: str, from_name: str, from_mode: str) -> dict:
    # The receiver rebuilds the wrapper and drops the message if it differs, so a body
    # that contains the tag must be escaped the way the client escapes it.
    body = body.replace(f"<{TAG}", f"<\\{TAG}").replace(f"</{TAG}", f"<\\/{TAG}")
    content = f'<{TAG} from-name="{from_name}" from-mode="{from_mode}">\n{body}\n</{TAG}>'
    return {
        "msgV": 1,
        "msg_id": str(uuid.uuid4()),
        "type": "user",
        "message": {"role": "user", "content": content},
        "priority": "next",
    }


def send(sock_path: str, token: str, msg: dict) -> None:
    payload = json.dumps({"type": "auth", "token": token}) + "\n" + json.dumps(msg) + "\n"
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(5)
        s.connect(sock_path)
        s.sendall(payload.encode())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--config-dir", required=True, help="the target session's Claude config dir")
    p.add_argument("--list", action="store_true", help="list live sessions in that config dir")
    p.add_argument("--to", help="target session name")
    p.add_argument("--from-name", default="peer-bridge", help="sender name shown to the target")
    p.add_argument("--from-mode", default="default", choices=MODES, help="sender permission mode label")
    p.add_argument("message", nargs="?", help="message text")
    a = p.parse_args()

    sessions_dir = os.path.join(os.path.expanduser(a.config_dir), "sessions")
    sessions = live_sessions(sessions_dir)
    if a.list:
        for rec in sessions:
            print(rec.get("name", "?"), rec["pid"], rec.get("status", "?"), rec.get("cwd", ""))
        return
    if not a.to or a.message is None:
        p.error("--to and a message are required unless --list is given")
    match = [r for r in sessions if r.get("name") == a.to]
    if not match:
        sys.exit(f"no live session named {a.to} in {sessions_dir}")
    rec = match[0]
    msg = frame(a.message, a.from_name, a.from_mode)
    send(rec["messagingSocketPath"], peer_token(sessions_dir, rec), msg)
    print(f"sent {msg['msg_id']} to {a.to} (pid {rec['pid']})")


if __name__ == "__main__":
    main()
