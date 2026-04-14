# RecruitSquad — High Level Design

## System Overview

RecruitSquad is a 7-agent autonomous recruitment platform built on FastAPI + LangGraph + Firebase Firestore.
Managers post jobs, and the system autonomously sources candidates, screens them via OA and behavioral interviews,
schedules interviews, performs market salary analysis, and generates audit reports.

## Architecture Diagram

```mermaid
graph TB
    subgraph Frontend["Frontend (React + Vite)"]
        UI_Login["Login Page\n(Firebase Auth)"]
        UI_Manager["Manager Portal\n/manager"]
        UI_CreateJob["Create Job\n/manager/create-job"]
        UI_Pipeline["Candidate Pipeline\n/manager/jobs/:id"]
        UI_Jobs["Job Board\n/jobs"]
        UI_Apply["Apply\n/jobs/:id/apply"]
        UI_Profile["Candidate Profile\n/profile"]
    end

    subgraph Auth["Firebase (recruit-squad-7d8e1)"]
        FB_Auth["Firebase Auth\nEmail / Google"]
        FB_Store["Firestore\nusers collection"]
    end

    subgraph Backend["Backend (FastAPI :8000)"]
        API["REST API\n/api/jobs"]

        subgraph Graphs["LangGraph Orchestration"]
            G1["Graph 1\nSourcing Pipeline"]
            G2["Graph 2\nScreening Pipeline"]
            G3["Graph 3\nCoordination Pipeline"]
            G4["Graph 4\nInterview Round Pipeline"]
        end

        subgraph Agents["Agents"]
            A1["A1 Sourcing Hunter\nGitHub + LinkedIn"]
            A2["A2 Behavioral + OA\nGPT-4o-mini"]
            A3["A3 Coordinator\n(stubbed)"]
            A4["A4 Market Analyst\nGPT-4o-mini"]
            A5["A5 Scoring Engine\nComposite Ranker"]
            A7["A7 Audit\nGPT-4o-mini"]
        end
    end

    subgraph EmailSvc["Email Microservice (:8001)"]
        A6["A6 Email + FAQ\nGemini + Kafka"]
        Kafka["Kafka\nemail-jobs topic"]
    end

    subgraph Firestore["Firestore Collections"]
        FS_Jobs["jobs/\n{job_id}"]
        FS_Cands["jobs/{id}/candidates/\n{candidate_id}"]
        FS_Users["users/\n{uid}"]
    end

    subgraph External["External APIs"]
        GitHub["GitHub API"]
        Serper["Serper API\n(LinkedIn search)"]
        OpenAI["OpenAI GPT-4o-mini"]
        Calendly["Calendly API"]
        Zoom["Zoom API"]
        SMTP["SMTP / Gmail"]
    end

    %% Auth flow
    UI_Login -->|"sign in / sign up"| FB_Auth
    FB_Auth --> FB_Store
    FB_Store --> FS_Users

    %% Manager flows
    UI_Manager -->|"GET /api/jobs"| API
    UI_CreateJob -->|"POST /api/jobs"| API
    UI_Pipeline -->|"GET /api/jobs/:id/candidates"| API
    UI_Pipeline -->|"POST interview-feedback"| API
    UI_Pipeline -->|"GET /api/jobs/:id/report"| API

    %% Candidate flows
    UI_Jobs -->|"reads jobs"| FS_Jobs
    UI_Apply -->|"OA token submit"| API

    %% API → Graphs
    API -->|"POST /api/jobs\n(BackgroundTask)"| G1
    API -->|"OA submit\n(BackgroundTask)"| G2
    API -->|"interview-feedback\n(BackgroundTask)"| G4

    %% Graph 1
    G1 --> A1
    A1 --> A5
    A5 --> A2
    A2 -->|"OA init"| A6

    %% Graph 2
    G2 --> A2
    A2 -->|"evaluate OA"| A5
    A5 -->|"shortlisted"| A3
    A5 -->|"rejected"| A6

    %% Graph 3
    G3 --> A5
    A5 --> A4
    A4 --> A6
    A6 -->|"salary report"| A3
    A3 --> A6

    %% Graph 4
    G4 --> A5
    A5 -->|"next round"| A3
    A5 -->|"final round"| G3
    A5 -->|"rejected"| A6

    %% Audit
    API -->|"GET /report"| A7
    A7 --> FS_Jobs

    %% External
    A1 --> GitHub
    A1 --> Serper
    A2 --> OpenAI
    A4 --> OpenAI
    A4 --> Serper
    A7 --> OpenAI
    A3 --> Calendly
    A3 --> Zoom
    A6 --> Kafka
    Kafka --> SMTP

    %% Firestore reads/writes
    A1 -->|"persist candidates"| FS_Cands
    A2 -->|"update OA fields"| FS_Cands
    A5 -->|"update scores/rank"| FS_Cands
    A4 -->|"write salary_report"| FS_Jobs
    A7 -->|"write audit"| FS_Jobs
    API -->|"read/write jobs"| FS_Jobs
    API -->|"read/write candidates"| FS_Cands

    %% Email svc
    A6 -.->|"HTTP"| EmailSvc

    %% Styling
    classDef frontend fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    classDef backend fill:#ede9fe,stroke:#7c3aed,color:#4c1d95
    classDef agent fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef pipegraph fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef db fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef ext fill:#f3f4f6,stroke:#6b7280,color:#374151

    class UI_Login,UI_Manager,UI_CreateJob,UI_Pipeline,UI_Jobs,UI_Apply,UI_Profile frontend
    class API,Backend backend
    class A1,A2,A3,A4,A5,A6,A7 agent
    class G1,G2,G3,G4 pipegraph
    class FS_Jobs,FS_Cands,FS_Users,FB_Auth,FB_Store db
    class GitHub,Serper,OpenAI,Calendly,Zoom,SMTP,Kafka ext
```

## Pipeline Flows

| Flow | Trigger | Agent Chain |
|------|---------|-------------|
| **Sourcing** | Manager posts job | G1 → A1 → A5 → A2 → A6 (outreach emails) |
| **Screening** | Candidate submits OA | G2 → A2 → A5 → A3 (schedule) or A6 (reject) |
| **Interview Round** | Manager submits feedback | G4 → A5 → next round / G3 / reject |
| **Coordination** | Final round passed | G3 → A5 → A4 → A6 → A3 → A6 (confirmations) |
| **Audit** | Manager requests report | A7 → reads Firestore → structured report |

## Candidate Pipeline Stages

```
SOURCED → OA_SENT → BEHAVIORAL_COMPLETE → SCORED → SHORTLISTED
       → INTERVIEW_SCHEDULED → INTERVIEW_DONE → OFFERED → HIRED

Rejection stages: OA_FAILED | REJECTED | EXPERIENCE_REJECTED |
                  LOCATION_REJECTED | SALARY_REJECTED | OVERQUALIFIED_REJECTED
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui, React Router v7 |
| Auth | Firebase Auth (Email/Password + Google) |
| Backend | FastAPI, Python 3.9+ |
| Orchestration | LangGraph (with fallback runners) |
| Database | Firebase Firestore |
| LLM | OpenAI GPT-4o-mini (A2, A4, A7) |
| Email | Gemini + Kafka (A6 microservice) |
| Sourcing | GitHub API + Serper API (LinkedIn) |
| Scheduling | Calendly + Zoom APIs (A3, stubbed) |
