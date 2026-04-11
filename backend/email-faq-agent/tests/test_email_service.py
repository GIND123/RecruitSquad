import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_send_email_success():
    with patch("app.services.email_service.aiosmtplib.SMTP") as mock_smtp_cls:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        mock_smtp_cls.return_value = mock_smtp

        from app.services.email_service import send_email
        await send_email(
            to="test@example.com",
            subject="Test",
            body_text="Hello",
            body_html="<p>Hello</p>",
        )

        mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_no_body():
    with patch("app.services.email_service.aiosmtplib.SMTP") as mock_smtp_cls:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        mock_smtp_cls.return_value = mock_smtp

        from app.services.email_service import send_email
        await send_email(to="test@example.com", subject="Test", body_text=None)
        mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_smtp_error():
    import aiosmtplib
    with patch("app.services.email_service.aiosmtplib.SMTP") as mock_smtp_cls:
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=False)
        mock_smtp.send_message.side_effect = aiosmtplib.SMTPException("Connection refused")
        mock_smtp_cls.return_value = mock_smtp

        from app.services.email_service import send_email
        with pytest.raises(aiosmtplib.SMTPException):
            await send_email(to="fail@example.com", subject="Test", body_text="Hi")
