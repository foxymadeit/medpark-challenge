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
	"""Prevent model libraries from reaching online model hubs."""
	for key, value in OFFLINE_ENV.items():
		os.environ.setdefault(key, value)


def block_outbound() -> Callable[[], None]:
	"""Refuse process socket connections to non-loopback addresses."""
	real_connect = socket.socket.connect
	real_create = socket.create_connection

	def host_of(address) -> str:
		if isinstance(address, tuple) and address:
			return str(address[0])
		return str(address)

	def guarded_connect(connection, address, *args, **kwargs):
		host = host_of(address)
		if host not in _LOOPBACK:
			raise OSError(f"network disabled: refused connection to {host}")
		return real_connect(connection, address, *args, **kwargs)

	def guarded_create(address, *args, **kwargs):
		host = host_of(address)
		if host not in _LOOPBACK:
			raise OSError(f"network disabled: refused connection to {host}")
		return real_create(address, *args, **kwargs)

	socket.socket.connect = guarded_connect
	socket.create_connection = guarded_create

	def restore() -> None:
		socket.socket.connect = real_connect
		socket.create_connection = real_create

	return restore