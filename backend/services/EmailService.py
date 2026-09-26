import os
import smtplib
from dataclasses import dataclass, field
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
from html import escape
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from schemas import Minutes


DEFAULT_ALLOWED_SMTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class DistributionListNotConfiguredError(RuntimeError):
	"""Raised when no recipients are configured for a meeting type."""


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
	accepted: tuple[str, ...]
	refused: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SMTPSettings:
	host: str = "localhost"
	port: int = 1025
	from_address: str = "mom-bot@hospital.local"
	username: str | None = None
	password: str | None = None
	use_starttls: bool = False
	allowed_hosts: frozenset[str] = DEFAULT_ALLOWED_SMTP_HOSTS
	recipients_by_meeting_type: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

	def __post_init__(self) -> None:
		host = self.host.casefold().rstrip(".")
		allowed_hosts = {allowed.casefold().rstrip(".") for allowed in self.allowed_hosts}
		if host not in allowed_hosts:
			raise ValueError("SMTP_HOST must be listed in SMTP_ALLOWED_HOSTS.")
		if bool(self.username) != bool(self.password):
			raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together.")

	@classmethod
	def from_env(cls) -> "SMTPSettings":
		load_dotenv(ENV_FILE, override=False)
		allowed_hosts = _split_csv(
			os.getenv("SMTP_ALLOWED_HOSTS", "localhost,127.0.0.1,::1")
		)
		recipients_by_meeting_type = {
			meeting_type: _split_csv(os.getenv(f"MOM_RECIPIENTS_{meeting_type.upper()}", ""))
			for meeting_type in ("medical", "executive", "administrative")
		}
		return cls(
			host=os.getenv("SMTP_HOST", "localhost"),
			port=int(os.getenv("SMTP_PORT", "1025")),
			from_address=os.getenv("SMTP_FROM", "mom-bot@hospital.local"),
			username=os.getenv("SMTP_USERNAME") or None,
			password=os.getenv("SMTP_PASSWORD") or None,
			use_starttls=os.getenv("SMTP_STARTTLS", "false").lower() in {"1", "true", "yes"},
			allowed_hosts=allowed_hosts,
			recipients_by_meeting_type=recipients_by_meeting_type,
		)


def _split_csv(value: str) -> tuple[str, ...]:
	return tuple(item.strip() for item in value.split(",") if item.strip())


def _unique_recipients(addresses: tuple[str, ...]) -> tuple[str, ...]:
	unique: list[str] = []
	seen: set[str] = set()
	for address in addresses:
		key = address.casefold()
		if key not in seen:
			unique.append(address)
			seen.add(key)
	return tuple(unique)


def _validate_participant_emails(addresses: tuple[str, ...]) -> tuple[str, ...]:
	validated: list[str] = []
	for value in addresses:
		address = value.strip()
		if not address:
			continue
		try:
			parsed = Address(addr_spec=address)
		except (HeaderParseError, TypeError, ValueError) as error:
			raise ValueError("Participant email addresses must be valid email addresses.") from error
		if parsed.addr_spec != address or not parsed.username or not parsed.domain:
			raise ValueError("Participant email addresses must be valid email addresses.")
		validated.append(address)
	return _unique_recipients(tuple(validated))


class EmailService:
	"""Send meeting-minutes email through a configurable SMTP server."""

	def __init__(self, settings: SMTPSettings | None = None) -> None:
		self._settings = settings or SMTPSettings.from_env()

	def send_mom_email(
		self,
		minutes: Minutes,
		attachment_path: str | Path | None = None,
		attachment: tuple[str, bytes] | None = None,
		*,
		attachments: list[tuple[str, bytes]] | tuple = (),
		participant_emails: tuple[str, ...] = (),
	) -> EmailDeliveryResult:
		"""Send minutes to the board list and separate participant copies."""
		if attachment_path is not None and attachment is not None:
			raise ValueError("Provide either an attachment path or attachment data, not both.")
		distribution_recipients = _unique_recipients(
			self._settings.recipients_by_meeting_type.get(minutes.meeting_type, ())
		)
		if not distribution_recipients:
			raise DistributionListNotConfiguredError(
				f"No recipients are configured for {minutes.meeting_type} meetings."
			)
		participant_recipients = _validate_participant_emails(participant_emails)
		distribution_keys = {address.casefold() for address in distribution_recipients}
		individual_recipients = tuple(
			address
			for address in participant_recipients
			if address.casefold() not in distribution_keys
		)
		recipients = (*distribution_recipients, *individual_recipients)

		text_body, html_body = _render_minutes(minutes)
		safe_title = " ".join(minutes.title.splitlines()).strip()

		files: list[tuple[str, bytes]] = list(attachments)
		if attachment is not None:
			files.append(attachment)
		if attachment_path is not None:
			path = Path(attachment_path)
			files.append((path.name, path.read_bytes()))

		def build_message(to_address: str | None = None) -> EmailMessage:
			message = EmailMessage()
			message["From"] = self._settings.from_address
			message["To"] = to_address or "undisclosed-recipients:;"
			message["Subject"] = f"MoM | {minutes.meeting_type.title()} | {safe_title}"
			message.set_content(text_body)
			message.add_alternative(html_body, subtype="html")
			for filename, content in files:
				pdf = filename.lower().endswith(".pdf")
				message.add_attachment(
					content,
					maintype="application",
					subtype="pdf" if pdf else "octet-stream",
					filename=filename,
				)
			return message

		refused: dict[str, tuple[int, bytes]]
		with smtplib.SMTP(self._settings.host, self._settings.port, timeout=10) as server:
			if self._settings.use_starttls:
				server.starttls()
			if self._settings.username and self._settings.password:
				server.login(self._settings.username, self._settings.password)
			try:
				refused = server.send_message(
					build_message(),
					from_addr=self._settings.from_address,
					to_addrs=list(distribution_recipients),
				)
			except smtplib.SMTPRecipientsRefused as error:
				refused = error.recipients
			for address in individual_recipients:
				try:
					refused.update(
						server.send_message(
							build_message(address),
							from_addr=self._settings.from_address,
							to_addrs=[address],
						)
					)
				except smtplib.SMTPRecipientsRefused as error:
					refused.update(error.recipients)

		refused_keys = {address.casefold() for address in refused}
		return EmailDeliveryResult(
			accepted=tuple(address for address in recipients if address.casefold() not in refused_keys),
			refused=tuple(address for address in recipients if address.casefold() in refused_keys),
		)


def _render_minutes(minutes: Minutes) -> tuple[str, str]:
	text_parts = [
		minutes.title,
		f"Meeting type: {minutes.meeting_type}",
		f"Language: {minutes.language}",
		"Summary\n" + (minutes.summary or "No summary provided."),
	]

	if minutes.attendees:
		text_parts.append("Attendees\n" + "\n".join(f"- {person}" for person in minutes.attendees))
	if minutes.decisions:
		text_parts.append("Decisions\n" + "\n".join(f"- {decision}" for decision in minutes.decisions))
	if minutes.action_items:
		text_parts.append(
			"Action items\n"
			+ "\n".join(
				f"- {item.text} | Owner: {item.owner or 'Unassigned'} | Due: {item.deadline or 'Not specified'}"
				for item in minutes.action_items
			)
		)

	header = (
		"<div style=\"font-family: Arial, Helvetica, sans-serif; margin: 0; padding: 28px; background: #0b1020; color: #e5e7eb;\">"
		"<div style=\"max-width: 700px; margin: 0 auto; background: #111827; border: 1px solid #2d3a4f; border-radius: 14px; overflow: hidden;\">"
		"<div style=\"padding: 26px 28px 18px; border-bottom: 1px solid #2d3a4f; background: #101a2d;\">"
		f"<h1 style=\"margin: 0; font-size: 30px; line-height: 1.2; color: #f8fafc;\">{escape(minutes.title)}</h1>"
		f"<p style=\"margin: 10px 0 0; font-size: 13px; color: #b7c6df;\"><strong>Meeting type:</strong> {escape(minutes.meeting_type)} &nbsp;|&nbsp; <strong>Language:</strong> {escape(minutes.language)}</p>"
		"</div>"
		"<div style=\"padding: 26px 28px;\">"
	)

	html_parts = [header]
	html_parts.append(
		"<div style=\"margin-bottom: 22px; padding: 18px 20px; background: #151f2f; border: 1px solid #2d3a4f; border-radius: 10px;\">"
		"<h2 style=\"margin: 0 0 10px; font-size: 18px; color: #f8fafc;\">Summary</h2>"
		f"<p style=\"margin: 0; line-height: 1.7; font-size: 15px; color: #e2e8f0;\">{escape(minutes.summary or 'No summary provided.')}</p>"
		"</div>"
	)

	if minutes.attendees:
		html_parts.append(
			"<div style=\"margin-bottom: 22px; padding: 18px 20px; background: #151f2f; border: 1px solid #2d3a4f; border-radius: 10px;\">"
			"<h2 style=\"margin: 0 0 10px; font-size: 18px; color: #f8fafc;\">Attendees</h2>"
			"<ul style=\"margin: 0; padding-left: 18px; color: #e2e8f0;\">"
			+ "".join(f"<li style=\"margin-bottom: 6px;\">{escape(person)}</li>" for person in minutes.attendees)
			+ "</ul></div>"
		)

	if minutes.decisions:
		html_parts.append(
			"<div style=\"margin-bottom: 22px; padding: 18px 20px; background: #151f2f; border: 1px solid #2d3a4f; border-radius: 10px;\">"
			"<h2 style=\"margin: 0 0 10px; font-size: 18px; color: #f8fafc;\">Decisions</h2>"
			"<ul style=\"margin: 0; padding-left: 18px; color: #e2e8f0;\">"
			+ "".join(f"<li style=\"margin-bottom: 6px;\">{escape(decision)}</li>" for decision in minutes.decisions)
			+ "</ul></div>"
		)

	if minutes.action_items:
		html_parts.append(
			"<div style=\"padding: 18px 20px; background: #151f2f; border: 1px solid #2d3a4f; border-radius: 10px;\">"
			"<h2 style=\"margin: 0 0 12px; font-size: 18px; color: #f8fafc;\">Action items</h2>"
			"<ul style=\"margin: 0; padding-left: 0; list-style: none;\">"
			+ "".join(
				f"<li style=\"margin-bottom: 12px; padding: 12px 14px; background: #0f172a; border: 1px solid #2a374d; border-radius: 8px;\">"
				f"<div style=\"font-weight: 700; color: #f8fafc; margin-bottom: 5px;\">{escape(item.text)}</div>"
				f"<div style=\"font-size: 13px; color: #d9e3f8; line-height: 1.7;\">"
				f"<strong>Owner:</strong> {escape(item.owner or 'Unassigned')}<br>"
				f"<strong>Due:</strong> {escape(item.deadline or 'Not specified')}"
				+ (f"<br><br><em style=\"color: #b8c7e8;\">{escape(item.source_quote)}</em>" if item.source_quote else "")
				+ "</div></li>"
				for item in minutes.action_items
			)
			+ "</ul></div>"
		)

	html_parts.append("</div></div></div>")
	return "\n\n".join(text_parts), "".join(html_parts)