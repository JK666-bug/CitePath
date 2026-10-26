import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from agent.llm import ping
from db.uploads import read_upload, save_upload
from ingest.pdf_reader import read_pdf

app = FastAPI(title="CitePath")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BRIEF_LENGTH = 10000


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/agent/ping")
def agent_ping():
    try:
        reply = ping()
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="模型接口调用失败") from error
    return {"reply": reply}


@app.post("/api/uploads")
async def create_upload(
    file: UploadFile = File(...),
    student_brief: str = Form(...),
):
    brief = student_brief.strip()
    if not brief:
        raise HTTPException(status_code=400, detail="请写下学习目标和日期")
    if len(brief) > MAX_BRIEF_LENGTH:
        raise HTTPException(status_code=400, detail="学习说明过长")
    filename = _pdf_filename(file.filename)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="PDF 是空文件")
    try:
        pages = read_pdf(data)
    except Exception as error:
        raise HTTPException(status_code=400, detail="无法读取这份 PDF") from error
    if not pages:
        raise HTTPException(status_code=400, detail="PDF 里没有页面")
    return save_upload(filename, brief, pages)


@app.get("/api/uploads/{document_id}")
def get_upload(document_id: int):
    record = read_upload(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="没有找到这份讲义")
    return record


def _pdf_filename(name: str | None) -> str:
    cleaned = os.path.basename(name or "").strip()
    if not cleaned or Path(cleaned).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")
    return cleaned[:255]
