import hashlib
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from db.study_availability import load_study_availability, save_study_availability
from planning.inputs import PlanningInputError, StudyAvailability, decode_course_brief
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StrictInt

from agent.llm import ping
from agent.qa import answer_question
from db.auth import authenticate, close_session, open_session, register_user, user_from_token
from db.courses import (
    create_course,
    delete_document_rows,
    get_course,
    list_courses,
    owns_document,
    update_course,
)
from db.uploads import existing_upload, load_document_source, save_document
from db.qa_history import load_qa_history
from ingest.pdf_reader import read_pdf
from planning.material_files import (
    MaterialIntegrityError,
    load_original_pdf,
    save_original_pdf,
)
from vector.segments import delete_segments

app = FastAPI(title="CitePath")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BRIEF_LENGTH = 10000
COOKIE = "citepath_session"


class AuthBody(BaseModel):
    username: str = Field(max_length=32)
    password: str = Field(max_length=72)


class CourseBody(BaseModel):
    name: str = Field(max_length=255)
    student_brief: str = Field(max_length=MAX_BRIEF_LENGTH)


class QuestionBody(BaseModel):
    question: str = Field(max_length=2000)

class StudyAvailabilityBody(BaseModel):
    weekday_minutes: list[StrictInt] = Field(min_length=7, max_length=7)


def current_user(request: Request) -> dict:
    user = user_from_token(request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in first")
    return user


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
        raise HTTPException(status_code=502, detail="The model request failed") from error
    return {"reply": reply}


@app.post("/api/register")
def register(body: AuthBody, response: Response):
    try:
        user = register_user(body.username, body.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    _set_session(response, open_session(user["id"]))
    return user


@app.post("/api/login")
def login(body: AuthBody, response: Response):
    user = authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    _set_session(response, open_session(user["id"]))
    return user


@app.post("/api/logout")
def logout(request: Request, response: Response):
    close_session(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user

@app.get("/api/me/study-availability")
def get_my_study_availability(user: dict = Depends(current_user)):
    saved = load_study_availability(user["id"])
    settings = saved if saved is not None else StudyAvailability()

    return {
        "weekday_minutes": settings.weekday_minutes,
        "saved": saved is not None,
    }


@app.put("/api/me/study-availability")
def put_my_study_availability(
    body: StudyAvailabilityBody,
    user: dict = Depends(current_user),
):
    try:
        settings = StudyAvailability(tuple(body.weekday_minutes))
    except PlanningInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    save_study_availability(user["id"], settings)

    return {
        "weekday_minutes": settings.weekday_minutes,
        "saved": True,
    }

@app.get("/api/courses")
def courses(user: dict = Depends(current_user)):
    return {"courses": list_courses(user["id"])}


@app.post("/api/courses")
def add_course(body: CourseBody, user: dict = Depends(current_user)):
    name = body.name.strip()
    brief = body.student_brief.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Enter a course name")
    if not brief:
        raise HTTPException(status_code=400, detail="Write your goals and dates")
    return create_course(user["id"], name, brief)


@app.get("/api/courses/{course_id}")
def course_detail(course_id: int, user: dict = Depends(current_user)):
    course = get_course(user["id"], course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@app.put("/api/courses/{course_id}")
def edit_course(
    course_id: int,
    body: CourseBody,
    user: dict = Depends(current_user),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Enter a course name")

    student_brief = body.student_brief.strip()
    try:
        settings = decode_course_brief(student_brief)
    except PlanningInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    today = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
    if settings.deadline is None or settings.deadline < today:
        raise HTTPException(status_code=422, detail="Choose today or a future date")
    if settings.early_days > (settings.deadline - today).days:
        raise HTTPException(status_code=422, detail="Choose a valid target finish date")

    course = update_course(user["id"], course_id, name, student_brief)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return course

@app.post("/api/courses/{course_id}/documents")
async def add_document(
    course_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
):
    if get_course(user["id"], course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    filename = _pdf_filename(file.filename)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The PDF is empty")
    digest = hashlib.sha256(data).hexdigest()

    # 去重返回之前先补齐原件，使旧记录重传同一文件也能恢复原 PDF。
    try:
        save_original_pdf(course_id, digest, data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="The PDF could not be saved. Please try again.",
        ) from error

    existing = existing_upload(course_id, digest)
    if existing is not None:
        return existing
    try:
        pages = read_pdf(data)
    except Exception as error:
        raise HTTPException(status_code=400, detail="This PDF could not be read") from error
    if not pages:
        raise HTTPException(status_code=400, detail="This PDF has no pages")
    return save_document(course_id, filename, pages, digest)


@app.get("/api/courses/{course_id}/documents/{document_id}/file")
def get_document_file(
    course_id: int,
    document_id: int,
    user: dict = Depends(current_user),
):
    document = load_document_source(user["id"], course_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Material not found")

    content_hash = document["content_hash"]
    if not content_hash:
        raise HTTPException(
            status_code=409,
            detail=(
                "This material has no file fingerprint. "
                "Its original PDF cannot be located automatically."
            ),
        )

    try:
        path = load_original_pdf(course_id, content_hash)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=410,
            detail=(
                "The original PDF is unavailable. "
                "Upload the same PDF again to restore it."
            ),
        ) from error
    except MaterialIntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail=(
                "The original PDF failed its integrity check. "
                "Upload the same PDF again to restore it."
            ),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409, detail="The stored PDF metadata is invalid."
        ) from error
    except OSError as error:
        raise HTTPException(
            status_code=503, detail="The original PDF could not be read."
        ) from error

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=document["filename"],
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.delete("/api/courses/{course_id}/documents/{document_id}")
def remove_document(
    course_id: int,
    document_id: int,
    user: dict = Depends(current_user),
):
    if not owns_document(user["id"], course_id, document_id):
        raise HTTPException(status_code=404, detail="Material not found")
    delete_document_rows(document_id)
    try:
        delete_segments(document_id)
    except Exception:
        pass
    return {"ok": True}


@app.get("/api/courses/{course_id}/questions")
def question_history(
    course_id: int,
    before_id: int | None = Query(default=None, gt=0),
    user: dict = Depends(current_user),
):
    try:
        return load_qa_history(user["id"], course_id, before_id=before_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Course not found") from error


@app.post("/api/courses/{course_id}/questions")
def create_question(
    course_id: int,
    body: QuestionBody,
    user: dict = Depends(current_user),
):
    try:
        return answer_question(user["id"], course_id, body.question)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Course not found") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not answer") from error


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=14 * 24 * 3600,
        path="/",
    )


def _pdf_filename(name: str | None) -> str:
    cleaned = os.path.basename(name or "").strip()
    if not cleaned or Path(cleaned).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF file")
    return cleaned[:255]
