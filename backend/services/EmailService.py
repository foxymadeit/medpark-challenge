import os
import smtplib
from dataclasses import dataclass, field
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


class EmailService:
	"""Send meeting-minutes email through a configurable SMTP server."""

	def __init__(self, settings: SMTPSettings | None = None) -> None:
		self._settings = settings or SMTPSettings.from_env()

	def send_mom_email(
		self,
		minutes: Minutes,
		attachment_path: str | Path | None = None,
		attachment: tuple[str, bytes] | None = None,
	) -> EmailDeliveryResult:
		"""Send structured minutes to the configured distribution list."""
		if attachment_path is not None and attachment is not None:
			raise ValueError("Provide either an attachment path or attachment data, not both.")
		recipients = self._settings.recipients_by_meeting_type.get(minutes.meeting_type, ())
		if not recipients:
			raise DistributionListNotConfiguredError(
				f"No recipients are configured for {minutes.meeting_type} meetings."
			)

		text_body, html_body = _render_minutes(minutes)
		safe_title = " ".join(minutes.title.splitlines()).strip()

		message = EmailMessage()
		message["From"] = self._settings.from_address
		message["To"] = "undisclosed-recipients:;"
		message["Subject"] = f"MoM | {minutes.meeting_type.title()} | {safe_title}"
		message.set_content(text_body)
		message.add_alternative(html_body, subtype="html")

		if attachment_path is not None or attachment is not None:
			if attachment is not None:
				filename, content = attachment
			else:
				path = Path(attachment_path)
				filename, content = path.name, path.read_bytes()
			message.add_attachment(
				content,
				maintype="application",
				subtype="octet-stream",
				filename=filename,
			)

		refused: dict[str, tuple[int, bytes]]
		with smtplib.SMTP(self._settings.host, self._settings.port, timeout=10) as server:
			if self._settings.use_starttls:
				server.starttls()
			if self._settings.username and self._settings.password:
				server.login(self._settings.username, self._settings.password)
			try:
				refused = server.send_message(
					message,
					from_addr=self._settings.from_address,
					to_addrs=list(recipients),
				)
			except smtplib.SMTPRecipientsRefused as error:
				refused = error.recipients

		return EmailDeliveryResult(
			accepted=tuple(address for address in recipients if address not in refused),
			refused=tuple(address for address in recipients if address in refused),
		)


def _render_minutes(minutes: Minutes) -> tuple[str, str]:
	text_parts = [
		minutes.title,
		f"Meeting type: {minutes.meeting_type}",
		f"Language: {minutes.language}",
		"Summary\n" + (minutes.summary or "No summary provided."),
	]
	html_parts = [
		f"<h1>{escape(minutes.title)}</h1>",
		f"<p>Meeting type: {escape(minutes.meeting_type)}; language: {escape(minutes.language)}</p>",
		"<h2>Summary</h2>",
		f"<p>{escape(minutes.summary or 'No summary provided.')}</p>",
	]

	if minutes.attendees:
		text_parts.append("Attendees\n" + "\n".join(f"- {person}" for person in minutes.attendees))
		html_parts.extend(
			["<h2>Attendees</h2><ul>", *(f"<li>{escape(person)}</li>" for person in minutes.attendees), "</ul>"]
		)
	if minutes.decisions:
		text_parts.append("Decisions\n" + "\n".join(f"- {decision}" for decision in minutes.decisions))
		html_parts.extend(
			["<h2>Decisions</h2><ul>", *(f"<li>{escape(decision)}</li>" for decision in minutes.decisions), "</ul>"]
		)
	if minutes.action_items:
		text_parts.append(
			"Action items\n"
			+ "\n".join(
				f"- {item.text} | Owner: {item.owner or 'Unassigned'} | Due: {item.deadline or 'Not specified'}"
				for item in minutes.action_items
			)
		)
		html_parts.append("<h2>Action items</h2><ul>")
		for item in minutes.action_items:
			details = [
				f"<strong>Owner:</strong> {escape(item.owner or 'Unassigned')}",
				f"<strong>Due:</strong> {escape(item.deadline or 'Not specified')}",
			]
			if item.source_quote:
				details.append(f"<blockquote>{escape(item.source_quote)}</blockquote>")
			html_parts.append(f"<li>{escape(item.text)}<br>{'<br>'.join(details)}</li>")
		html_parts.append("</ul>")

	return "\n\n".join(text_parts), "\n".join(html_parts)