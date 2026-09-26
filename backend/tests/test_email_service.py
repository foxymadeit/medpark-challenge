import os
import unittest
from email import message_from_bytes
from email.policy import default
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from schemas import ActionItem, Minutes
from services.EmailService import (
	DistributionListNotConfiguredError,
	EmailService,
	SMTPSettings,
)


class EmailServiceTests(unittest.TestCase):
	@patch("services.EmailService.smtplib.SMTP")
	def test_sends_structured_minutes_with_text_and_html(self, smtp_factory) -> None:
		smtp = smtp_factory.return_value.__enter__.return_value
		recipients = ("board@hospital.local", "admin@hospital.local")
		settings = SMTPSettings(
			recipients_by_meeting_type={"medical": recipients},
		)
		service = EmailService(settings)
		minutes = Minutes(
			title="Cardiology Board",
			meeting_type="medical",
			summary="Approve <ICU> protocol",
			attendees=["Dr. Popescu"],
			decisions=["Approve ICU protocol"],
			action_items=[
				ActionItem(
					text="Review protocol",
					owner="Dr. Popescu",
					deadline="2026-10-05",
					source_quote="I will review it by October 5.",
				)
			],
		)

		with TemporaryDirectory() as directory:
			attachment = Path(directory) / "minutes.pdf"
			attachment.write_bytes(b"pdf data")
			result = service.send_mom_email(minutes, attachment)

		smtp_factory.assert_called_once_with("localhost", 1025, timeout=10)
		sent_message = message_from_bytes(smtp.send_message.call_args.args[0].as_bytes(), policy=default)
		self.assertEqual(sent_message["From"], "mom-bot@hospital.local")
		self.assertEqual(sent_message["To"], "board@hospital.local, admin@hospital.local")
		self.assertIsNone(sent_message["Cc"])
		self.assertIsNone(sent_message["Bcc"])
		self.assertEqual(sent_message["Subject"], "MoM | Medical | Cardiology Board")
		plain = sent_message.get_body(preferencelist=("plain",)).get_content()
		self.assertIn("Summary", plain)
		# the items are in the meeting's own words, often mixed: no language claim
		self.assertNotIn("Language:", plain)
		self.assertNotIn("Language:", sent_message.get_body(preferencelist=("html",)).get_content())
		self.assertIn(
			"&lt;ICU&gt;",
			sent_message.get_body(preferencelist=("html",)).get_content(),
		)
		self.assertNotIn("<ICU>", sent_message.get_body(preferencelist=("html",)).get_content())
		attachment_part = next(sent_message.iter_attachments())
		self.assertEqual(attachment_part.get_filename(), "minutes.pdf")
		self.assertEqual(attachment_part.get_payload(decode=True), b"pdf data")
		self.assertEqual(smtp.send_message.call_args.kwargs["to_addrs"], list(recipients))
		self.assertEqual(result.accepted, recipients)
		self.assertEqual(result.refused, ())

	@patch("services.EmailService.smtplib.SMTP")
	def test_list_in_to_participants_in_cc_one_message_no_duplicates(self, smtp_factory) -> None:
		recipients = ("board@hospital.local", "admin@hospital.local")
		settings = SMTPSettings(recipients_by_meeting_type={"medical": recipients})
		service = EmailService(settings)
		smtp = smtp_factory.return_value.__enter__.return_value
		smtp.send_message.return_value = {}
		minutes = Minutes(title="Board", meeting_type="medical", summary="Summary")

		result = service.send_mom_email(
			minutes,
			participant_emails=(
				"doctor@hospital.local",
				"admin@hospital.local",
				"DOCTOR@HOSPITAL.LOCAL",
			),
		)

		smtp.send_message.assert_called_once()
		message = message_from_bytes(smtp.send_message.call_args.args[0].as_bytes(), policy=default)
		self.assertEqual(message["To"], "board@hospital.local, admin@hospital.local")
		self.assertEqual(message["Cc"], "doctor@hospital.local")
		self.assertIsNone(message["Bcc"])
		self.assertEqual(
			smtp.send_message.call_args.kwargs["to_addrs"],
			["board@hospital.local", "admin@hospital.local", "doctor@hospital.local"],
		)
		self.assertEqual(
			result.accepted,
			("board@hospital.local", "admin@hospital.local", "doctor@hospital.local"),
		)
		self.assertEqual(result.refused, ())

	@patch("services.EmailService.smtplib.SMTP")
	def test_a_list_address_cannot_inject_headers(self, smtp_factory) -> None:
		for bad in ("board@hospital.local\r\nBcc: spy@evil.example", "Board <board@hospital.local>", "not-an-email"):
			settings = SMTPSettings(recipients_by_meeting_type={"medical": (bad,)})
			minutes = Minutes(title="Board", meeting_type="medical", summary="Summary")
			with self.assertRaisesRegex(ValueError, "valid email addresses"):
				EmailService(settings).send_mom_email(minutes)
		smtp_factory.assert_not_called()

	@patch("services.EmailService.smtplib.SMTP")
	def test_a_title_cannot_inject_headers(self, smtp_factory) -> None:
		smtp = smtp_factory.return_value.__enter__.return_value
		smtp.send_message.return_value = {}
		settings = SMTPSettings(recipients_by_meeting_type={"medical": ("board@hospital.local",)})
		minutes = Minutes(title="Board\r\nBcc: spy@evil.example", meeting_type="medical", summary="Summary")
		EmailService(settings).send_mom_email(minutes)
		message = message_from_bytes(smtp.send_message.call_args.args[0].as_bytes(), policy=default)
		self.assertIsNone(message["Bcc"])
		self.assertEqual(smtp.send_message.call_args.kwargs["to_addrs"], ["board@hospital.local"])

	@patch("services.EmailService.smtplib.SMTP")
	def test_rejects_invalid_participant_email_before_connecting(self, smtp_factory) -> None:
		settings = SMTPSettings(
			recipients_by_meeting_type={"medical": ("board@hospital.local",)},
		)
		service = EmailService(settings)
		minutes = Minutes(title="Board", meeting_type="medical", summary="Summary")

		with self.assertRaisesRegex(ValueError, "Participant email addresses"):
			service.send_mom_email(minutes, participant_emails=("not-an-email",))

		smtp_factory.assert_not_called()

	@patch("services.EmailService.smtplib.SMTP")
	def test_requires_a_configured_distribution_list(self, smtp_factory) -> None:
		service = EmailService(SMTPSettings())
		minutes = Minutes(title="Board", meeting_type="medical", summary="Summary")

		with self.assertRaises(DistributionListNotConfiguredError):
			service.send_mom_email(minutes)

		smtp_factory.assert_not_called()

	@patch("services.EmailService.smtplib.SMTP")
	def test_reports_partial_recipient_refusal(self, smtp_factory) -> None:
		recipients = ("board@hospital.local", "admin@hospital.local")
		settings = SMTPSettings(recipients_by_meeting_type={"medical": recipients})
		service = EmailService(settings)
		smtp = smtp_factory.return_value.__enter__.return_value
		smtp.send_message.return_value = {"admin@hospital.local": (550, b"mailbox unavailable")}
		minutes = Minutes(title="Board", meeting_type="medical", summary="Summary")

		result = service.send_mom_email(minutes)

		self.assertEqual(result.accepted, ("board@hospital.local",))
		self.assertEqual(result.refused, ("admin@hospital.local",))

	def test_rejects_smtp_host_not_explicitly_allowlisted(self) -> None:
		with self.assertRaisesRegex(ValueError, "SMTP_ALLOWED_HOSTS"):
			SMTPSettings(host="smtp.example.com")

	def test_loads_dotenv_from_backend_and_preserves_process_overrides(self) -> None:
		with TemporaryDirectory() as directory:
			env_file = Path(directory) / ".env"
			env_file.write_text(
				"SMTP_HOST=mailpit\n"
				"SMTP_PORT=2025\n"
				"SMTP_ALLOWED_HOSTS=mailpit,localhost\n"
				"MOM_RECIPIENTS_MEDICAL=board@hospital.local\n",
				encoding="utf-8",
			)
			with patch("services.EmailService.ENV_FILE", env_file):
				with patch.dict(os.environ, {"SMTP_PORT": "1025"}, clear=True):
					settings = SMTPSettings.from_env()

		self.assertEqual(settings.host, "mailpit")
		self.assertEqual(settings.port, 1025)
		self.assertEqual(
			settings.recipients_by_meeting_type["medical"],
			("board@hospital.local",),
		)


if __name__ == "__main__":
	unittest.main()