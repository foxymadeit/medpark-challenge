import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import security
from main import app
from schemas import Minutes
from services.EmailService import (
	DistributionListNotConfiguredError,
	EmailDeliveryResult,
)


class EmailEndpointTests(unittest.TestCase):
	def setUp(self) -> None:
		app.dependency_overrides[security.require_admin] = lambda: {"id": "admin", "role": "admin"}
		self.addCleanup(app.dependency_overrides.clear)
		self.client = TestClient(app, headers={"Origin": "http://testserver"})

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
	def test_sends_minutes_to_confirmed_participants_and_ignores_generic_recipients(
		self, send_mom_email
	) -> None:
		send_mom_email.return_value = EmailDeliveryResult(
			accepted=(
				"board@hospital.local",
				"admin@hospital.local",
				"doctor@hospital.local",
			),
			refused=(),
		)
		payload = self._payload()
		payload["participant_emails"] = ["doctor@hospital.local"]
		payload["to_addresses"] = ["outside@example.com"]

		response = self.client.post(
			"/api/email/send",
			json=payload,
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.json(),
			{
				"status": "sent",
				"accepted_count": 3,
				"refused_count": 0,
				"message": "Email sent.",
			},
		)
		send_mom_email.assert_called_once()
		self.assertIsInstance(send_mom_email.call_args.args[0], Minutes)
		self.assertEqual(send_mom_email.call_args.args[0].title, "Cardiology Board")
		self.assertEqual(
			send_mom_email.call_args.kwargs["participant_emails"],
			("doctor@hospital.local",),
		)

	@patch("main.email_service.send_mom_email")
	def test_maps_invalid_participant_email_to_422(self, send_mom_email) -> None:
		payload = self._payload()
		payload["participant_emails"] = ["not-an-email"]
		send_mom_email.side_effect = ValueError(
			"Participant email addresses must be valid email addresses."
		)

		response = self.client.post("/api/email/send", json=payload)

		self.assertEqual(response.status_code, 422)
		send_mom_email.assert_called_once()

	@patch("main.email_service.send_mom_email")
	def test_reports_partial_delivery(self, send_mom_email) -> None:
		send_mom_email.return_value = EmailDeliveryResult(
			accepted=("board@hospital.local",),
			refused=("admin@hospital.local",),
		)
		response = self.client.post("/api/email/send", json=self._payload())

		self.assertEqual(response.status_code, 207)
		self.assertEqual(response.json()["status"], "partial")
		self.assertEqual(response.json()["accepted_count"], 1)
		self.assertEqual(response.json()["refused_count"], 1)

	@patch("main.email_service.send_mom_email")
	def test_reports_unconfigured_distribution_list(self, send_mom_email) -> None:
		send_mom_email.side_effect = DistributionListNotConfiguredError("No recipients configured")
		response = self.client.post("/api/email/send", json=self._payload())

		self.assertEqual(response.status_code, 503)
		send_mom_email.assert_called_once()


if __name__ == "__main__":
	unittest.main()

def test_nobody_signed_out_can_send_mail():
	client = TestClient(app, headers={"Origin": "http://testserver"})
	assert client.post("/api/email/send", json={"minutes": {}}).status_code == 401
