#!/usr/bin/env python3
import socket, json, time

class QMPClient:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)

        # 1) Read the greeting
        greeting = self._recv()
        # 2) Enable capabilities
        self._cmd({ "execute": "qmp_capabilities" })

    def _recv(self):
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

    def _cmd(self, msg):
        self.sock.sendall((json.dumps(msg) + '\n').encode())
        return self._recv()

    def execute(self, cmd, arguments=None):
        msg = { "execute": cmd }
        if arguments:
            msg["arguments"] = arguments
        return self._cmd(msg)

if __name__ == "__main__":
    qmp = QMPClient("/tmp/qmp-sock")

    # example: send Ctrl+Alt+Del into the guest
    resp = qmp.execute("human-monitor-command",
                       { "command-line": "sendkey ctrl-alt-delete" })
    print("→", resp)

    # example: query VM status
    status = qmp.execute("query-status")
    print("VM status:", status.get("return", {}))
