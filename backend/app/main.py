from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from app.controllers.jobs import router as jobs_router

app = FastAPI(title="RecruitSquad API")
app.include_router(jobs_router)
