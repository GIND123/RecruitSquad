import json
import uuid
from typing import Optional
from aiokafka import AIOKafkaProducer
from app.config import settings
from app.models.email_models import EmailJob, Priority
from app.utils.logger import get_logger

logger = get_logger(__name__)

_producer: Optional[AIOKafkaProducer] = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await _producer.start()
        logger.info("Kafka producer started")
    return _producer


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")


async def publish_email_job(
    to: str,
    subject: str,
    body_text: Optional[str] = None,
    template_name: Optional[str] = None,
    template_data: Optional[dict] = None,
    priority: Priority = Priority.normal,
    topic: Optional[str] = None,
    retry_count: int = 0,
) -> str:
    job_id = str(uuid.uuid4())
    job = EmailJob(
        job_id=job_id,
        to=to,
        subject=subject,
        body_text=body_text,
        template_name=template_name,
        template_data=template_data,
        priority=priority,
        retry_count=retry_count,
    )
    target_topic = topic or settings.kafka_email_topic
    producer = await get_producer()
    await producer.send_and_wait(target_topic, job.model_dump())
    logger.info(f"Published job {job_id} to topic={target_topic} recipient={to}")
    return job_id
