#!/usr/bin/env python3
import json 
import socket 
import time
from typing import Any 

class QMPClient:
    def __init__(self, path: str):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)

        # 1) Read the greeting
        _ = self._recv()
        # 2) Enable capabilities
        self._cmd({ "execute": "qmp_capabilities" })

    def _recv(self) -> dict[str, Any]:
        buf = b''
        # read until we get a complete JSON object
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            try:
                return json.loads(buf.decode())
            except json.JSONDecodeError:
                continue

        raise ConnectionError("Failed to read a complete JSON object from the QMP server.")

    def _cmd(self, msg):
        self.sock.sendall((json.dumps(msg) + '\n').encode())
        return self._recv()

    def execute(self, cmd, arguments=None):
        msg = { "execute": cmd }
        if arguments:
            msg["arguments"] = arguments
        return self._cmd(msg)

    def _execute_key_down(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a key down event to the QMP server."""
        return self._cmd({
            "execute": "input-event-sent",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "down": True,
                        "key": key
                    } for key in cla_action.get("keys", [])
                ],
            },
        })

    def _execute_key_up(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a key up event to the QMP server."""
        return self._cmd({
            "execute": "input-event-sent",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "down": False,
                        "key": key
                    } for key in cla_action.get("keys", [])
                ],
            },
        })

    def _execute_click(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a mouse click event to the QMP server."""
        point = cla_action.get("point")
        button = cla_action.get("button", "left")
        pattern = cla_action.get("pattern")
        hold_keys = cla_action.get("hold_keys", [])

        responses = []

        pre_events = [{ "type": "abs", "data" : { "axis": "x", "value" : point.get("x") } },
                { "type": "abs", "data" : { "axis": "y", "value" : point.get("y") } } ]

        BUTTON_NAME_MAP={"foward": "side", "back": "extra"}
        button = BUTTON_NAME_MAP.get(button, button)

        if hold_keys:
            pre_events += [{ "type": "key", "down": True, "key": key } for key in hold_keys]

        responses.append(self._cmd({
            "execute": "input-event-sent",
            "arguments": {"events": pre_events},
        }))

        click_cmd = {
            "execute": "input-event-sent",
            "arguments": {
                "events": [
                    {
                        "type": "button",
                        "down": True,
                        "button": button
                    },
                    {
                        "type": "button",
                        "down": False,
                        "button": button
                    }
                ]
            }
        }
        if pattern and len(pattern) > 0:
            responses.append(self._cmd(click_cmd))
            for delay in pattern:
                time.sleep(delay/1000.0)
                responses.append(self._cmd(click_cmd))
        else:
            responses.append(self._cmd(click_cmd))

        post_events = []
        if hold_keys:
            post_events += [{ "type": "key", "down": False, "key": key } for key in hold_keys]

        responses.append(self._cmd({
            "execute": "input-event-sent",
            "arguments": {"events": post_events},
        }))

        return {"responses": responses}



if __name__ == "__main__":
    qmp = QMPClient("/tmp/qmp-sock")

    # example: send Ctrl+Alt+Del into the guest
    resp = qmp.execute("human-monitor-command",
                       { "command-line": "sendkey ctrl-alt-delete" })
    print("→", resp)

    # example: query VM status
    status = qmp.execute("query-status")
    print("VM status:", status.get("return", {}))
