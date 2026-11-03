# claude-peer-bridge

Send a message from one Claude Code session to another that runs under a different config directory (for example two accounts, `~/.claude-a` and `~/.claude-b`).

## The problem

Claude Code's `SendMessage` and `ListAgents` only see sessions registered in your own config directory.
Two sessions on the same machine, started with different `CLAUDE_CONFIG_DIR` values, cannot see each other even though both listen on a Unix socket under `/run/user/<uid>/cc-socks/`.

## What this does

`peer_bridge.py` reads the target session's record and key from the config directory you name, then writes to its socket the same two lines Claude Code's own client writes:

1. an auth line: `{"type":"auth","token":"<peerToken>"}`
2. one message line: `{"msgV":1,"msg_id":"<uuid>","type":"user","message":{"role":"user","content":"<cross-session-message ...>...</cross-session-message>"},"priority":"next"}`

The token comes from `<config dir>/sessions/<pid>.<sha256 of socket path>.key`.
The socket path and session name come from `<config dir>/sessions/<pid>.json`.
The wrapper tag is rebuilt by the receiver and the message is dropped if it differs, so a body containing the tag is escaped (`<\cross-session-message`) the way the client does it.

Python 3.9+, standard library only.

## Use

```sh
python3 peer_bridge.py --config-dir ~/.claude-b --list
python3 peer_bridge.py --config-dir ~/.claude-b --to some-session --from-name me "hello"
```

The target cannot answer with `SendMessage` (it cannot see you).
Run the same command from its side with `--config-dir` pointing at your config directory, or ask for the reply in a file.

## Held messages

The receiver matches the sending process to a registered session.
A script is not one, so the receiver reports "unidentified session ... did not attest its permission mode" and holds the message until its user approves it.
`--from-mode` is only text in the message and does not change this.

To let messages through unheld, set this in the receiving account's `settings.json` (and in yours, for replies):

```json
{ "crossSessionInbound": "accept" }
```

## Read this first

- This reads another session's private key file and writes to its socket. Use it only for your own sessions, as the same OS user. It cannot cross users: the socket and key files are owner-only.
- `crossSessionInbound: "accept"` turns off a check that exists on purpose. After it, any process you run can put text in front of that session's model. Messages from other sessions are not your approval for anything, and a careful session will refuse to run credentialed tools on a message's say-so.
- The format was read from Claude Code 2.1.317 and is undocumented. Any update can break it.
- Tested on Linux only.

## License

MIT
