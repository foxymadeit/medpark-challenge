import os
import unittest
from email import message_from_bytes
from email.policy import default
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from schemas import ActionItem, Minutes
from services.EmailService import (
	DistributionListNotConfiguredError,
	EmailService,
	SMTPSettings,
	compose_email,
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
			date="2026-09-26",
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
		self.assertEqual(sent_message["Subject"], "Proces-verbal al ședinței Consiliului Medical din 26 septembrie 2026")
		plain = sent_message.get_body(preferencelist=("plain",)).get_content()
		html = sent_message.get_body(preferencelist=("html",)).get_content()
		for part in (plain, html):
			self.assertIn("Stimați membri ai Consiliului Medical,", part)
			self.assertIn("Cu stimă,", part)
			self.assertIn("Secretariatul Consiliului Medical", part)
		# the meeting's own words (often mixed languages) stay in the PDFs, not in the email
		self.assertNotIn("ICU", plain + html)
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
	def test_a_date_cannot_inject_headers(self, smtp_factory) -> None:
		smtp = smtp_factory.return_value.__enter__.return_value
		smtp.send_message.return_value = {}
		settings = SMTPSettings(recipients_by_meeting_type={"medical": ("board@hospital.local",)})
		for date in ("2026-09-26\r\nBcc: spy@evil.example", "\r\nBcc: spy@evil.example", "not a date"):
			minutes = Minutes(title="Board", meeting_type="medical", date=date, summary="Summary")
			EmailService(settings).send_mom_email(minutes)
			raw = smtp.send_message.call_args.args[0].as_bytes()
			message = message_from_bytes(raw, policy=default)
			self.assertIsNone(message["Bcc"])
			self.assertNotIn(b"spy@evil.example", raw)
			self.assertNotIn("\n", message["Subject"])
			self.assertTrue(message["Subject"].startswith("Proces-verbal al ședinței Consiliului Medical"))
			self.assertEqual(smtp.send_message.call_args.kwargs["to_addrs"], ["board@hospital.local"])

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



# Words that must never reach a recipient: the old English boilerplate and labels.
ENGLISH = ("MoM", "Minutes", "Meeting", "Summary", "Attendees", "Decisions", "Action items", "Owner", "Due",
           "Unassigned", "Not specified", "attached", "Dear", "Regards", "Drafted", "checked", "Liminal", "board")
BOARDS = {
	"medical": "Consiliului Medical",
	"executive": "Comitetului Executiv",
	"administrative": "Consiliului Administrativ",
}


def _render(meeting_type: str, date: str | None = "2026-09-26", files=("x_ro.pdf", "x_ru.pdf", "x_en.pdf")):
	minutes = Minutes(title="Weekly review", meeting_type=meeting_type, date=date, summary="The board met.",
	                  attendees=["Participant 1"], decisions=["Approve the protocol."],
	                  action_items=[ActionItem(text="Send the report.", owner="Participant 2", deadline="2026-10-02")])
	return compose_email(minutes, files)


class RomanianEmailTests(unittest.TestCase):
	def test_subject_greeting_and_signature_name_the_right_board(self) -> None:
		for meeting_type, board in BOARDS.items():
			subject, text, html = _render(meeting_type)
			self.assertEqual(subject, f"Proces-verbal al ședinței {board} din 26 septembrie 2026")
			self.assertTrue(text.startswith(f"Stimați membri ai {board},\n\n"))
			self.assertIn(f"procesul-verbal al ședinței {board} din 26 septembrie 2026", text)
			self.assertTrue(text.endswith(f"Cu stimă,\nSecretariatul {board}"))
			self.assertIn(f"Secretariatul {board}", html)

	def test_every_month_is_written_in_romanian(self) -> None:
		months = ("ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
		          "septembrie", "octombrie", "noiembrie", "decembrie")
		for n, month in enumerate(months, 1):
			minutes = Minutes(title="T", meeting_type="medical", date=f"2026-{n:02d}-05", summary="S")
			self.assertTrue(compose_email(minutes)[0].endswith(f"din 5 {month} 2026"))

	def test_without_a_date_the_subject_just_names_the_meeting(self) -> None:
		self.assertEqual(_render("medical", date=None)[0], "Proces-verbal al ședinței Consiliului Medical")

	def test_attachments_are_described_in_romanian_in_order(self) -> None:
		_, text, _ = _render("medical")
		self.assertIn("Vă transmitem, în anexă, procesul-verbal", text)
		self.assertIn(
			"Anexe:\n"
			"1. Procesul-verbal în limba română (format PDF)\n"
			"2. Procesul-verbal în limba rusă (format PDF)\n"
			"3. Procesul-verbal în limba engleză (format PDF)",
			text,
		)

	def test_states_that_a_local_ai_drafted_it_and_it_was_checked(self) -> None:
		_, text, _ = _render("medical")
		self.assertIn("întocmit automat de un sistem de inteligență artificială", text)
		self.assertIn("pe serverul instituției", text)
		self.assertIn("verificat în raport cu înregistrarea ședinței", text)
		self.assertIn("Regulamentul (UE) 2024/1689", text)

	def test_no_english_or_russian_and_only_comma_below_diacritics(self) -> None:
		for meeting_type in BOARDS:
			subject, text, html = _render(meeting_type)
			everything = "\n".join((subject, text, html))
			for word in ENGLISH:
				self.assertNotIn(word, everything)
			# the meeting's own words stay in the PDFs
			for content in ("Weekly review", "The board met.", "Participant", "Approve the protocol.", "Send the report."):
				self.assertNotIn(content, everything)
			self.assertFalse(any("\u0400" <= c <= "\u04ff" for c in everything), "Cyrillic in the email")
			self.assertFalse(set("şţŞŢ") & set(everything), "cedilla instead of comma below")
			self.assertTrue(set("șț") <= set(everything))

	def test_html_is_the_same_text(self) -> None:
		_, text, html = _render("medical")
		for paragraph in text.split("\n\n"):
			for line in paragraph.split("\n"):
				self.assertIn(escape(line), html)


if __name__ == "__main__":
	unittest.main()