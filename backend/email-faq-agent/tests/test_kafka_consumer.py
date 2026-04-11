import pytest
from unittest.mock import AsyncMock, patch
from app.models.email_models import EmailJob, Priority


@pytest.mark.asyncio
async def test_process_job_with_template():
    with patch("app.kafka.consumer.send_email", new_callable=AsyncMock) as mock_send:
        with patch("app.kafka.consumer.render_template", return_value="<html>hi</html>"):
            from app.kafka.consumer import process_job
            job = EmailJob(
                job_id="j1",
                to="test@example.com",
                subject="Test",
                template_name="notification",
                template_data={"name": "X", "message": "Y"},
            )
            await process_job(job)
            mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_with_retry_success():
    with patch("app.kafka.consumer.process_job", new_callable=AsyncMock):
        from app.kafka.consumer import handle_with_retry
        raw = {
            "job_id": "j2", "to": "a@b.com", "subject": "Hi",
            "retry_count": 0, "priority": "normal",
        }
        await handle_with_retry(raw)


@pytest.mark.asyncio
async def test_handle_with_retry_dlq():
    with patch("app.kafka.consumer.process_job", new_callable=AsyncMock, side_effect=Exception("fail")):
        with patch("app.kafka.consumer.publish_email_job", new_callable=AsyncMock, return_value="dlq-id") as mock_pub:
            from app.kafka.consumer import handle_with_retry
            from app.config import settings
            raw = {
                "job_id": "j3", "to": "a@b.com", "subject": "Hi",
                "retry_count": settings.max_retries - 1, "priority": "normal",
            }
            await handle_with_retry(raw)
            mock_pub.assert_called_once()
            assert mock_pub.call_args.kwargs["topic"] == settings.kafka_dead_letter_topic


@pytest.mark.asyncio
async def test_handle_with_retry_requeue():
    with patch("app.kafka.consumer.process_job", new_callable=AsyncMock, side_effect=Exception("fail")):
        with patch("app.kafka.consumer.publish_email_job", new_callable=AsyncMock, return_value="retry-id") as mock_pub:
            from app.kafka.consumer import handle_with_retry
            from app.config import settings
            raw = {
                "job_id": "j4", "to": "a@b.com", "subject": "Hi",
                "retry_count": 0, "priority": "normal",
            }
            await handle_with_retry(raw)
            mock_pub.assert_called_once()
            assert mock_pub.call_args.kwargs.get("topic") != settings.kafka_dead_letter_topic
