import os
import re
import smtplib
from dataclasses import dataclass, field
from datetime import date
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

# The email is official Romanian (Republic of Moldova), whatever the meeting's language.
# Board names as the Romanian PDF prints them (minutes/mom/schemas.py BODY_NAME): (nominative, genitive).
BOARD_RO = {
	"medical": ("Consiliul Medical", "Consiliului Medical"),
	"executive": ("Comitetul Executiv", "Comitetului Executiv"),
	"administrative": ("Consiliul Administrativ", "Consiliului Administrativ"),
}
MONTHS_RO = ("ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
	"septembrie", "octombrie", "noiembrie", "decembrie")
LANGUAGE_RO = {"ro": "română", "ru": "rusă", "en": "engleză"}
AI_NOTICE_RO = (
	"Notă: procesul-verbal a fost întocmit automat de un sistem de inteligență artificială care funcționează "
	"local, pe serverul instituției, iar fiecare punct a fost verificat în raport cu înregistrarea ședinței "
	"(mențiune de transparență conform art. 50 din Regulamentul (UE) 2024/1689 privind inteligența artificială)."
)
_LANGUAGE_IN_NAME = re.compile(r"_(ro|ru|en)\.pdf$", re.IGNORECASE)


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


def _validate_emails(addresses: tuple[str, ...], who: str = "Participant") -> tuple[str, ...]:
	"""Bare addresses only (no display names, no line breaks): they go into
	the To and Cc headers."""
	validated: list[str] = []
	for value in addresses:
		address = value.strip()
		if not address:
			continue
		try:
			parsed = Address(addr_spec=address)
		except (HeaderParseError, TypeError, ValueError) as error:
			raise ValueError(f"{who} email addresses must be valid email addresses.") from error
		if parsed.addr_spec != address or not parsed.username or not parsed.domain:
			raise ValueError(f"{who} email addresses must be valid email addresses.")
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
		"""One message: the board's distribution list in To, participants who
		are not on it in Cc."""
		if attachment_path is not None and attachment is not None:
			raise ValueError("Provide either an attachment path or attachment data, not both.")
		distribution_recipients = _validate_emails(
			tuple(self._settings.recipients_by_meeting_type.get(minutes.meeting_type, ())), "Distribution list"
		)
		if not distribution_recipients:
			raise DistributionListNotConfiguredError(
				f"No recipients are configured for {minutes.meeting_type} meetings."
			)
		participant_recipients = _validate_emails(participant_emails)
		distribution_keys = {address.casefold() for address in distribution_recipients}
		individual_recipients = tuple(
			address
			for address in participant_recipients
			if address.casefold() not in distribution_keys
		)
		recipients = (*distribution_recipients, *individual_recipients)

		files: list[tuple[str, bytes]] = list(attachments)
		if attachment is not None:
			files.append(attachment)
		if attachment_path is not None:
			path = Path(attachment_path)
			files.append((path.name, path.read_bytes()))
		subject, text_body, html_body = compose_email(minutes, [name for name, _ in files])

		message = EmailMessage()
		message["From"] = self._settings.from_address
		message["To"] = ", ".join(distribution_recipients)
		if individual_recipients:
			message["Cc"] = ", ".join(individual_recipients)
		message["Subject"] = " ".join(subject.splitlines()).strip()   # one line: nothing can add a header
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

		refused_keys = {address.casefold() for address in refused}
		return EmailDeliveryResult(
			accepted=tuple(address for address in recipients if address.casefold() not in refused_keys),
			refused=tuple(address for address in recipients if address.casefold() in refused_keys),
		)


def _meeting_day(value: str | None) -> date | None:
	"""Only a real ISO date reaches the subject or a file name, never raw text."""
	try:
		return date.fromisoformat((value or "")[:10])
	except ValueError:
		return None


def attachment_name(minutes: Minutes, language: str) -> str:
	"""Proces-verbal_Consiliul-Medical_2026-09-26_RO.pdf (ASCII, so every mail client shows it)."""
	day = _meeting_day(minutes.date)
	parts = ("Proces-verbal", BOARD_RO[minutes.meeting_type][0].replace(" ", "-"), day and day.isoformat(), language.upper())
	return "_".join(p for p in parts if p) + ".pdf"


def compose_email(minutes: Minutes, attachment_names: list[str] | tuple = ()) -> tuple[str, str, str]:
	"""Subject, plain text and HTML of the cover email, in official Romanian. The minutes
	themselves, in the meeting's own (often mixed) words, travel only in the attached PDFs."""
	board = BOARD_RO[minutes.meeting_type][1]
	day = _meeting_day(minutes.date)
	meeting = f"ședinței {board}" + (f" din {day.day} {MONTHS_RO[day.month - 1]} {day.year}" if day else "")
	listed = []
	for number, name in enumerate(attachment_names, 1):
		found = _LANGUAGE_IN_NAME.search(name)
		described = f"Procesul-verbal în limba {LANGUAGE_RO[found.group(1).lower()]} (format PDF)" if found else name
		listed.append(f"{number}. {described}")
	paragraphs = [
		f"Stimați membri ai {board},",
		(f"Vă transmitem, în anexă, procesul-verbal al {meeting}. Vă rugăm să luați cunoștință de conținutul acestuia."
		 if listed else f"Procesul-verbal al {meeting} a fost întocmit."),
		*(["Anexe:\n" + "\n".join(listed)] if listed else []),
		AI_NOTICE_RO,
		f"Cu stimă,\nSecretariatul {board}",
	]
	html = "".join("<p>" + "<br>".join(escape(line) for line in p.split("\n")) + "</p>" for p in paragraphs)
	return (
		f"Proces-verbal al {meeting}",
		"\n\n".join(paragraphs),
		f"<div lang=\"ro\" style=\"font-family: Arial, Helvetica, sans-serif; font-size: 15px; line-height: 1.6;\">{html}</div>",
	)
