from .qemu_gui import QMPClient
from typing import Any

def step(actions: list[dict[str, Any]]) -> Any:
    qmp = QMPClient("/tmp/qmp-sock")

    print(qmp.execute_action_list(actions))

    return {"observation": {"screenshot": qmp.screenshot()}}

def setup() -> None:
    pass
