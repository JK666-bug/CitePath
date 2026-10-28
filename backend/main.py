import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.llm import ping
from agent.qa import answer_question
from db.auth import authenticate, close_session, open_session, register_user, user_from_token
from db.courses import (
    create_course,
    delete_document_rows,
    get_course,
    list_courses,
    owns_document,
)
from db.uploads import save_document
from ingest.pdf_reader import read_pdf
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
    try:
        pages = read_pdf(data)
    except Exception as error:
        raise HTTPException(status_code=400, detail="This PDF could not be read") from error
    if not pages:
        raise HTTPException(status_code=400, detail="This PDF has no pages")
    return save_document(course_id, filename, pages)


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
