import json
import asyncio
from aiokafka import AIOKafkaConsumer
from app.config import settings
from app.models.email_models import EmailJob
from app.services.email_service import send_email
from app.services.template_service import render_template, render_text_fallback
from app.kafka.producer import publish_email_job
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def process_job(job: EmailJob) -> None:
    body_html = None
    body_text = job.body_text

    if job.template_name and job.template_data:
        body_html = render_template(job.template_name, job.template_data)
        if not body_text:
            body_text = render_text_fallback(job.template_name, job.template_data)

    await send_email(
        to=job.to,
        subject=job.subject,
        body_text=body_text,
        body_html=body_html,
    )
    logger.info(f"Processed job {job.job_id} for {job.to}")


async def handle_with_retry(raw: dict) -> None:
    job = EmailJob(**raw)
    try:
        await process_job(job)
    except Exception as exc:
        logger.error(f"Job {job.job_id} failed (attempt {job.retry_count + 1}): {exc}")
        if job.retry_count + 1 >= settings.max_retries:
            logger.error(f"Job {job.job_id} exceeded max retries. Sending to DLQ.")
            await publish_email_job(
                to=job.to,
                subject=job.subject,
                body_text=job.body_text,
                template_name=job.template_name,
                template_data=job.template_data,
                priority=job.priority,
                topic=settings.kafka_dead_letter_topic,
                retry_count=job.retry_count + 1,
            )
        else:
            await publish_email_job(
                to=job.to,
                subject=job.subject,
                body_text=job.body_text,
                template_name=job.template_name,
                template_data=job.template_data,
                priority=job.priority,
                retry_count=job.retry_count + 1,
            )


async def run_consumer() -> None:
    consumer = AIOKafkaConsumer(
        settings.kafka_email_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info(f"Consumer started on topic={settings.kafka_email_topic}")
    try:
        async for msg in consumer:
            await handle_with_retry(msg.value)
    finally:
        await consumer.stop()
        logger.info("Consumer stopped")


if __name__ == "__main__":
    asyncio.run(run_consumer())
