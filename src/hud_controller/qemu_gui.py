#!/usr/bin/env python3
import json 
import socket 
import time
import base64
from typing import Any 

SCREEN_SIZE_QEMU = 32767  # Maximum screen size for QEMU, used for mouse coordinates
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720  # Default screen size, can be adjusted as needed


KEYMAP = {
    "enter": "ret",
    "win": "meta_l",
    "escape": "esc",
    ' ': 'spc',
    '\n': 'ret',
    '\t': 'tab',
    '-': 'minus',
    '=': 'equal',
    '[': 'bracket_left',
    ']': 'bracket_right',
    '\\': 'backslash',
    ';': 'semicolon',
    "'": 'apostrophe',
    '`': 'grave_accent',
    ',': 'comma',
    '.': 'dot',
    '/': 'slash',
}

shift_char_map = {
    '!': '1',     # Shift + 1
    '@': '2',     # Shift + 2
    '#': '3',     # Shift + 3
    '$': '4',     # Shift + 4
    '%': '5',     # Shift + 5
    '^': '6',     # Shift + 6
    '&': '7',     # Shift + 7
    '*': '8',     # Shift + 8
    '(': '9',     # Shift + 9
    ')': '0',     # Shift + 0
    '_': 'minus', # Shift + -
    '+': 'equal', # Shift + =
    '{': 'bracket_left',   # Shift + [
    '}': 'bracket_right',  # Shift + ]
    '|': 'backslash',      # Shift + \
    ':': 'semicolon',      # Shift + ;
    '"': 'apostrophe',     # Shift + '
    '~': 'grave_accent',   # Shift + `
    '<': 'comma',          # Shift + ,
    '>': 'dot',            # Shift + .
    '?': 'slash',          # Shift + /
}

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

    def _convert(self, key: str) -> str:
        """Convert a key to its QMP representation."""
        return KEYMAP.get(key, key)

    def get_devices(self) -> dict[str, Any]:
        """Get a list of devices from the QMP server."""
        return self.execute("query-mice")

    def _execute_keydown(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a key down event to the QMP server."""
        return self._cmd({
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "down": True,
                        "key": self._convert(key)
                    } for key in cla_action.get("keys", [])
                ],
            },
        })

    def _execute_keyup(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a key up event to the QMP server."""
        return self._cmd({
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "data": {
                            "down": False,
                            "key": self._convert(key)
                        }
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

        BUTTON_NAME_MAP={"forward": "side", "back": "extra"}
        button = BUTTON_NAME_MAP.get(button, button)

        if hold_keys:
            pre_events += [{ "type": "key", "data":{"down": True, "key": self._convert(key) }} for key in hold_keys]

        responses.append(self._cmd({
            "execute": "input-send-event",
            "arguments": {"events": pre_events},
        }))

        def send_click() -> None:
            responses.append(self._cmd({
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {
                            "type": "btn",
                            "data": {
                                "down": True,
                                "button": button
                            }
                        },
                    ]
                }}))
            time.sleep(0.05)
            responses.append(self._cmd({
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {
                            "type": "btn",
                            "data": {
                                "down": False,
                                "button": button
                            }
                        }
                    ]
                }
            }))

        if pattern and len(pattern) > 0:
            send_click()
            for delay in pattern:
                time.sleep(delay/1000.0)
                send_click()
        else:
            send_click()

        post_events = []
        if hold_keys:
            post_events += [{ "type": "key", "data": {"down": False, "key": self._convert(key)} } for key in hold_keys]

        responses.append(self._cmd({
            "execute": "input-send-event",
            "arguments": {"events": post_events},
        }))

        return {"responses": responses}

    def _send_key(self, key: str) -> dict[str, Any]:
        if key in shift_char_map or key.isupper():
            return self._cmd({
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {"type": "key", "data": {"down": True, "key": {"type":"qcode", "data": self._convert("shift")}}},
                        {"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": self._convert(key.lower())}}},
                        {"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": self._convert(key.lower())}}},
                        {"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": self._convert("shift")}}},
                    ]
                }
            })
        else:
            return self._cmd({
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": self._convert(key)}}},
                        {"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": self._convert(key)}}},
                    ]
                }
            })

    def _execute_press(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a key press event to the QMP server."""
        keys = cla_action.get("keys")

        if not keys:
            raise ValueError("No keys specified for press action.")

        return self._cmd({
            "execute": "send-key",
            "arguments": {
                "keys": [{"type": "qcode", "data": self._convert(key)} for key in keys]
            }
        })
        
    def _execute_type(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a type event to the QMP server."""
        text = cla_action.get("text")
        if not text:
            raise ValueError("No text specified for type action.")

        responses = []
        for char in text:
           responses.append(self._send_key(char)) 
        return {"responses": responses}

    def _execute_scroll(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a scroll event to the QMP server."""
        point = cla_action.get("point")
        scroll = cla_action.get("scroll")
        hold_keys = cla_action.get("hold_keys", [])

        responses = []
        pre_events = []

        if not scroll:
            raise ValueError("No scroll specified for scroll action.")

        if hold_keys:
            pre_events += [{"type": "key","data":{"down": True, "key": self._convert(key)}} for key in hold_keys]

        if point:
            pre_events += [
                {"type": "abs", "data": {"axis": "x", "value": point.get("x")}},
                {"type": "abs", "data": {"axis": "y", "value": point.get("y")}}
            ]

        responses.append(self._cmd({
            "execute": "input-send-event",
            "arguments": {"events": pre_events},
        }))

        scroll_x = scroll.get("x", 0)
        scroll_y = scroll.get("y", 0)

        def get_scroll_event(button: str) -> dict[str, Any]:
            return {
                "type": "btn",
                "data": {
                    "down": True,
                    "button": button
                }
            }

        scroll_events = []
        if scroll_x >= 0:
            scroll_events += [get_scroll_event("wheel-right")] * scroll_x
        else:
            scroll_events += [get_scroll_event("wheel-left")] * abs(scroll_x)

        if scroll_y >= 0:
            scroll_events += [get_scroll_event("wheel-down")] * scroll_y
        else:
            scroll_events += [get_scroll_event("wheel-up")] * abs(scroll_y)

        responses.append(self._cmd({
            "execute": "input-send-event",
            "arguments": {"events": scroll_events},
        }))

        post_events = []

        if hold_keys:
            post_events += [{"type": "key", "data":{"down": False, "key": self._convert(key)}} for key in hold_keys]

        responses.append(self._cmd({
            "execute": "input-send-event",
            "arguments": {"events": post_events},
        }))

        return {"responses": responses}

    def _execute_move(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Send a mouse move event to the QMP server."""
        point = cla_action.get("point")
        offset = cla_action.get("offset")

        if point:
            return self._cmd({
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {"type": "abs", "data": {"axis": "x", "value": point.get("x")}},
                        {"type": "abs", "data": {"axis": "y", "value": point.get("y")}}
                    ]
                }
            })
        if offset:
            return self._cmd({
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {"type": "rel", "data": {"axis": "x", "value": offset.get("x", 0)}},
                        {"type": "rel", "data": {"axis": "y", "value": offset.get("y", 0)}}
                    ]
                }
            })
        else:
            raise ValueError("No point or offset specified for move action.")

    def _execute_wait(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Execute a time.sleep command."""
        time_ms = cla_action.get("time", 1000)  # Default to 1 second
        seconds = time_ms / 1000.0

        time.sleep(seconds)

        return {}

    def _execute_drag(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        path = cla_action.get("path", [])
        pattern = cla_action.get("pattern", [])
        hold_keys = cla_action.get("hold_keys", [])

        if not path or len(path) < 2:
            raise ValueError("Drag action must have a 'path' field with at least 2 points")
        
        def _move_cmd(point: dict[str, Any]) -> dict[str, Any]:
            return self._cmd({
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {"type": "abs", "data": {"axis": "x", "value": point.get("x")}},
                        {"type": "abs", "data": {"axis": "y", "value": point.get("y")}}
                    ]
                }
            })

        responses = []
        pre_events = [
            {"type": "abs", "data": {"axis": "x", "value": path[0].get("x")}},
            {"type": "abs", "data": {"axis": "y", "value": path[0].get("y")}}
        ]

        # Execute key down commands if hold_keys is specified
        if hold_keys:
            pre_events += [{"type": "key","data": {"down": True, "key": self._convert(key)}} for key in hold_keys]

        pre_events.append({"type": "btn", "data": {"down": True, "button": "left"}})
        responses.append(self._cmd({
            "execute": "input-send-event",
            "arguments": {"events": pre_events},
        }))

        if pattern and len(pattern) > 0:
            responses.append(_move_cmd(path[1]))

            for delay, point in zip(pattern, path[2:]):
                time.sleep(delay / 1000.0)
                responses.append(_move_cmd(point))

        else:
            for point in path[1:]:
                responses.append(_move_cmd(point))

        post_events = [{"type": "btn", "data": {"down": False, "button": "left"}}]
        if hold_keys:
            post_events += [{"type": "key", "data": {"down": False, "key": self._convert(key)}} for key in hold_keys]

        responses.append(self._cmd({
            "execute": "input-send-event",
            "arguments": {"events": post_events},
        }))

        return {"responses": responses}

    def execute_action(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Execute a QMP action based on the provided action dictionary."""
        action_type = cla_action.get("type")
        if not action_type:
            raise ValueError("Action must have a 'type' field")
        if action_type == "screenshot":
            return {}

        method_name = f"_execute_{action_type}"
        method = getattr(self, method_name, None)

        if not method:
            raise ValueError(f"Action type not recognized: {action_type}")

        return method(cla_action)

    def preprocess(self, cla_action: dict[str, Any]) -> dict[str, Any]:
        """Preprocess the action dictionary before executing."""
        # Here you can add any preprocessing logic if needed
        if "point" in cla_action:
            cla_action["point"]["x"] = cla_action["point"].get("x", 0)* SCREEN_SIZE_QEMU // SCREEN_WIDTH
            cla_action["point"]["y"] = cla_action["point"].get("y", 0)* SCREEN_SIZE_QEMU // SCREEN_HEIGHT
            print(cla_action["point"])
        if "offset" in cla_action:
            cla_action["offset"]["x"] = cla_action["offset"].get("x", 0)* SCREEN_SIZE_QEMU // SCREEN_WIDTH
            cla_action["offset"]["y"] = cla_action["offset"].get("y", 0)* SCREEN_SIZE_QEMU // SCREEN_HEIGHT
        if "path" in cla_action:
            for point in cla_action["path"]:
                point["x"] = point.get("x", 0) * SCREEN_SIZE_QEMU // SCREEN_WIDTH
                point["y"] = point.get("y", 0) * SCREEN_SIZE_QEMU // SCREEN_HEIGHT
        return cla_action

    def preprocess_list(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Preprocess a list of QMP actions."""
        return [self.preprocess(action) for action in actions]

    def execute_action_list(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute a list of QMP actions."""
        actions = self.preprocess_list(actions)
        responses = []
        for action in actions:
            response = self.execute_action(action)
            responses.append(response)
        return responses

    def screenshot(self) -> str:
        """Take a screenshot of the QEMU VM."""
        response = self._cmd({
            "execute": "screendump",
            "arguments": {
                "filename": "/app/screenshot.png",
                "format": "png"
            }
        })
        print(response)

        with open("/app/screenshot.png", "rb") as f:
            screenshot_data = f.read()
            return base64.b64encode(screenshot_data).decode()

if __name__ == "__main__":
    qmp = QMPClient("/tmp/qmp-sock")

    # example: send Ctrl+Alt+Del into the guest
    print(qmp._cmd({
  "execute": "input-set-pointer",
  "arguments": {"index": 2}
}))
