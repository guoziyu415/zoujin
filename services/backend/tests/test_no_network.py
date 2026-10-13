"""No network in tests (dev-plan 2.4): tests in CI and project threads cannot reach real models, while the local
PostgreSQL is still reachable.

テストではネットワーク禁止（dev-plan 2.4）：CI とプロジェクトのスレッドのテストは本物のモデルに届かず、
ローカルの PostgreSQL にはこれまでどおり接続できる。
"""

import socket
import threading

import pytest
from pytest_socket import SocketConnectBlockedError


@pytest.mark.filterwarnings("ignore:A test tried to use socket:UserWarning")
def test_outbound_network_is_blocked() -> None:
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("192.0.2.1", 443), timeout=1)


def test_localhost_is_allowed() -> None:
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
        accepted = threading.Thread(target=server.accept, daemon=True)
        accepted.start()
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
        accepted.join(timeout=1)
