# RecruitSquad Context File

## Overview
RecruitSquad is a 7-agent autonomous recruitment system designed to automate sourcing, screening, coordination, market analysis, and auditing.

## Architecture
- **Backend:** FastAPI, LangGraph for orchestration, Firebase Firestore for data storage.
- **Frontend:** React, Vite (currently UI shell with mock data).
- **Communication:** Agents communicate via LangGraph state and FastAPI BackgroundTasks.
- **Email/FAQ:** Handled by a separate microservice (`backend/email-faq-agent`) communicating via Kafka and REST.

## Agent System
- **Agent 1 (Sourcing Hunter):** Scrapes GitHub/LinkedIn, parses JDs, and persists candidates.
- **Agent 2 (Behavioral + OA):** Generates OA questions, conducts behavioral chat, and evaluates responses.
- **Agent 3 (Coordinator):** Stubbed. Will handle Calendly/Zoom scheduling.
- **Agent 4 (Market Analyst):** Synthesizes salary data using Serper API and LLM.
- **Agent 5 (Scoring Engine):** Computes composite scores and ranks candidates.
- **Agent 6 (Email + FAQ):** Separate microservice for sending emails and handling candidate FAQs.
- **Agent 7 (Audit):** Reads Firestore to generate a structured audit trail and anomaly report.

## Workflows (Graphs)
1. **Graph 1 (Sourcing):** A1 → A5 → A2 (OA init) → A6 (Outreach).
2. **Graph 2 (Screening):** A2 (OA evaluate) → A5 (Score) → Conditional: A3 (Coordinator) or A6 (Reject).
3. **Graph 3 (Coordination):** A5 (Final rank) → A4 (Market analysis) → A6 (Salary report) → A3 (Confirm slots) → A6 (Confirmations).
4. **Graph 4 (Interview Round):** A5 (Update scorecard) → Conditional: Schedule Next Round, Market Analysis (triggers Graph 3), or Reject.

## Current State
- Backend agents and graphs are largely implemented.
- `requirements.txt` updated for Python 3.9 compatibility.
- Environment variables (`.env`) are configured.
- Frontend lacks API integration.

## Key Files
- `backend/app/controllers/jobs.py`: Primary API routes for jobs and pipelines.
- `backend/app/graphs/`: LangGraph definitions.
- `backend/app/agents/`: Agent implementations.
- `backend/app/services/firestore_service.py`: Database operations.
- `backend/email-faq-agent/`: Separate email/FAQ microservice.
