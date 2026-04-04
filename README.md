# RecruitSquad
The â€œAutonomous Recruiterâ€ Squad

## Environment config

1. Copy `backend/.env.example` to `backend/.env`.
2. Add your keys (never commit `backend/.env`):
   - `OPENAI_API_KEY`
   - `GITHUB_TOKEN`
   - `SERPER_API_KEY`
   - `STACKEXCHANGE_API_KEY` (for Stack Exchange scorecard enrichment)

`stackexchange` sample key (do not commit):


3. `RecruitSquad/.gitignore` already excludes `.env` and `backend/.env`.
