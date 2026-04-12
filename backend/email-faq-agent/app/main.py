from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from app.models.email_models import (
    EmailRequest,
    EnqueueRequest,
    AgentTaskRequest,
    SendEmailResponse,
    EnqueueEmailResponse,
    AgentTaskResponse,
    TemplatesResponse,
    TemplateInfo,
    AITaskRequest,
    AITaskResponse,
    ToolCallRecord,
    FAQRequest,
    FAQResponse,
)
from app.services.email_service import send_email
from app.services.template_service import (
    render_template,
    render_text_fallback,
    list_templates,
    validate_template_data,
)
from app.kafka.producer import publish_email_job, stop_producer
from app.agent.orchestrator import handle_email_task
from app.agent.ai_agent import run_agent, run_faq_agent
from app.agent.scheduling_agent import run_scheduling_agent
from app.models.scheduling_models import AIScheduleRequest, AIScheduleResponse
from app.services.user_store import get_all_users, get_user_by_id, get_user_by_email
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Email agent starting up")
    yield
    await stop_producer()
    logger.info("Email agent shut down")


app = FastAPI(title="Email Agent", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/templates", response_model=TemplatesResponse)
async def get_templates():
    return TemplatesResponse(
        templates=[TemplateInfo(**t) for t in list_templates()]
    )


@app.post("/send-email", response_model=SendEmailResponse)
async def send_email_endpoint(request: EmailRequest):
    body_html = None
    body_text = request.body_text

    if request.template_name:
        if request.template_data:
            missing = validate_template_data(request.template_name, request.template_data)
            if missing:
                raise HTTPException(status_code=422, detail=f"Missing template fields: {', '.join(missing)}")
            body_html = render_template(request.template_name, request.template_data)
            if not body_text:
                body_text = render_text_fallback(request.template_name, request.template_data)
        else:
            raise HTTPException(status_code=422, detail="template_data required when template_name is set")

    try:
        await send_email(
            to=str(request.to),
            subject=request.subject,
            body_text=body_text,
            body_html=body_html,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return SendEmailResponse(status="sent", message="Email sent successfully", recipient=str(request.to))


@app.post("/enqueue-email", response_model=EnqueueEmailResponse)
async def enqueue_email_endpoint(request: EnqueueRequest):
    if request.template_name and request.template_data:
        missing = validate_template_data(request.template_name, request.template_data)
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing template fields: {', '.join(missing)}")

    job_id = await publish_email_job(
        to=str(request.to),
        subject=request.subject,
        body_text=request.body_text,
        template_name=request.template_name,
        template_data=request.template_data,
        priority=request.priority,
    )
    from app.config import settings
    return EnqueueEmailResponse(status="queued", job_id=job_id, topic=settings.kafka_email_topic)


@app.get("/users")
async def list_users():
    return {"users": get_all_users()}


@app.get("/users/{user_id}")
async def get_user(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


@app.post("/agent/email-task", response_model=AgentTaskResponse)
async def agent_email_task(request: AgentTaskRequest):
    return await handle_email_task(request)


@app.post("/agent/faq", response_model=FAQResponse)
async def faq_agent(request: FAQRequest):
    if not request.user_id and not request.email:
        raise HTTPException(status_code=422, detail="Provide user_id or email")
    user = get_user_by_id(request.user_id) if request.user_id else get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    answer = await run_faq_agent(request.question, user)
    return FAQResponse(answer=answer, user=user)


@app.post("/agent/schedule-interview", response_model=AIScheduleResponse)
async def schedule_interview(request: AIScheduleRequest):
    try:
        return await run_scheduling_agent(request.task)
    except Exception as exc:
        logger.error(f"Scheduling agent error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/agent/task", response_model=AITaskResponse)
async def agent_task(request: AITaskRequest):
    result = await run_agent(request.task)
    return AITaskResponse(
        status=result.status,
        summary=result.summary,
        actions=[ToolCallRecord(**a.model_dump()) for a in result.actions],
        total_steps=result.total_steps,
    )
