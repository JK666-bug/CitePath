# CitePath

An agent that helps a student study from course PDFs.

Need Docker Desktop, Python 3.10, and Node.js. Commands are for PowerShell.

## First time

From the repository root:

```powershell
docker compose up -d
Get-Content .\backend\db\schema.sql -Raw | docker exec -i citepath-mysql mysql -ucitepath -pcitepath citepath
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Put your key in `backend/.env` as `HKU_API_KEY`. Then start the API and leave the window open:

```powershell
.\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In another window:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173/ and create an account.

## Next time

```powershell
docker compose up -d
```

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
