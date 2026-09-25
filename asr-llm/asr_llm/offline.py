from __future__ import annotations

import os
import socket
from collections.abc import Callable

OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def enforce_offline() -> None:
    """Model libraries must never reach for a hub, even if a name looks like a repo id."""
    for key, value in OFFLINE_ENV.items():
        os.environ.setdefault(key, value)


def block_outbound() -> Callable[[], None]:
    """Refuse every non-loopback connection. Returns a restore callable."""
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def _host_of(address) -> str:
        if isinstance(address, tuple) and address:
            return str(address[0])
        return str(address)

    def guarded_connect(self, address, *args, **kwargs):
        if _host_of(address) not in _LOOPBACK:
            raise OSError(f"network disabled: refused connection to {_host_of(address)}")
        return real_connect(self, address, *args, **kwargs)

    def guarded_create(address, *args, **kwargs):
        if _host_of(address) not in _LOOPBACK:
            raise OSError(f"network disabled: refused connection to {_host_of(address)}")
        return real_create(address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.create_connection = guarded_create

    def restore() -> None:
        socket.socket.connect = real_connect
        socket.create_connection = real_create

    return restore
