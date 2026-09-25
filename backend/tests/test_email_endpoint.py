import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from schemas import Minutes
from services.EmailService import (
	DistributionListNotConfiguredError,
	EmailDeliveryResult,
)


class EmailEndpointTests(unittest.TestCase):
	def setUp(self) -> None:
		self.client = TestClient(app)

	def _payload(self) -> dict:
		return {
			"minutes": {
				"title": "Cardiology Board",
				"meeting_type": "medical",
				"language": "ro",
				"summary": "Approve ICU protocol",
				"attendees": ["Dr. Popescu"],
				"decisions": ["Approve ICU protocol"],
				"action_items": [
					{
						"text": "Review the protocol",
						"owner": "Dr. Popescu",
						"deadline": "2026-10-05",
						"source_quote": "I will review it by October 5.",
					}
				],
			}
		}

	@patch("main.email_service.send_mom_email")
	def test_sends_pipeline_minutes_without_accepting_request_recipients(self, send_mom_email) -> None:
		send_mom_email.return_value = EmailDeliveryResult(
			accepted=("board@hospital.local", "admin@hospital.local"),
			refused=(),
		)
		payload = self._payload()
		payload["to_addresses"] = ["outside@example.com"]

		response = self.client.post(
			"/email/send",
			json=payload,
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.json(),
			{
				"status": "sent",
				"accepted_count": 2,
				"refused_count": 0,
				"message": "Email sent.",
			},
		)
		send_mom_email.assert_called_once()
		self.assertIsInstance(send_mom_email.call_args.args[0], Minutes)
		self.assertEqual(send_mom_email.call_args.args[0].title, "Cardiology Board")

	@patch("main.email_service.send_mom_email")
	def test_reports_partial_delivery(self, send_mom_email) -> None:
		send_mom_email.return_value = EmailDeliveryResult(
			accepted=("board@hospital.local",),
			refused=("admin@hospital.local",),
		)
		response = self.client.post("/email/send", json=self._payload())

		self.assertEqual(response.status_code, 207)
		self.assertEqual(response.json()["status"], "partial")
		self.assertEqual(response.json()["accepted_count"], 1)
		self.assertEqual(response.json()["refused_count"], 1)

	@patch("main.email_service.send_mom_email")
	def test_reports_unconfigured_distribution_list(self, send_mom_email) -> None:
		send_mom_email.side_effect = DistributionListNotConfiguredError("No recipients configured")
		response = self.client.post("/email/send", json=self._payload())

		self.assertEqual(response.status_code, 503)
		send_mom_email.assert_called_once()


if __name__ == "__main__":
	unittest.main()