import os
import socket
import unittest
from unittest.mock import patch

from offline import OFFLINE_ENV, block_outbound, enforce_offline


class OfflineTests(unittest.TestCase):
	def test_enforce_offline_sets_model_library_flags(self) -> None:
		with patch.dict(os.environ, {}, clear=True):
			enforce_offline()
			for name, value in OFFLINE_ENV.items():
				self.assertEqual(os.environ[name], value)

	def test_outbound_block_rejects_non_loopback_connections(self) -> None:
		restore = block_outbound()
		try:
			with socket.socket() as connection:
				with self.assertRaisesRegex(OSError, "network disabled"):
					connection.connect(("203.0.113.1", 25))
		finally:
			restore()


if __name__ == "__main__":
	unittest.main()