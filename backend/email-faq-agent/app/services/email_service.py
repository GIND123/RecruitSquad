import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def send_email(
    to: str,
    subject: str,
    body_text: Optional[str],
    body_html: Optional[str] = None,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to

    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))
    if not body_text and not body_html:
        msg.attach(MIMEText("", "plain"))

    # aiosmtplib 3.x: use_tls=True for implicit TLS (port 465),
    # start_tls=True for STARTTLS upgrade (port 587). Never both.
    smtp_kwargs: dict = dict(
        hostname=settings.smtp_host,
        port=settings.smtp_port,
    )
    if settings.smtp_use_tls:
        smtp_kwargs["use_tls"] = True
    elif settings.smtp_use_starttls:
        smtp_kwargs["start_tls"] = True

    try:
        async with aiosmtplib.SMTP(**smtp_kwargs) as smtp:
            if settings.smtp_username:
                await smtp.login(settings.smtp_username, settings.smtp_password)
            await smtp.send_message(msg)
        logger.info(f"Email sent to {to} | subject={subject}")
    except aiosmtplib.SMTPException as exc:
        logger.error(f"SMTP error sending to {to}: {exc}")
        raise