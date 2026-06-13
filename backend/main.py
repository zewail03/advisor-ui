from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.database import Base, engine
from core.security import decode_token
from core.websocket import ws_manager

from routers import (
    admin_approvals,
    admin_assistant,
    admin_auth,
    admin_catalog,
    admin_dashboard,
    admin_financial,
    admin_grades,
    admin_notifications,
    admin_offerings,
    admin_policies,
    admin_staff,
    admin_students,
    advisor,
    attendance,
    audit,
    auth,
    capstone,
    chat,
    courses,
    enrollments,
    evaluations,
    financial,
    gpa,
    notifications,
    petitions,
    retakes,
    schedule,
    students,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            from sqlalchemy import text
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    # ensure every business rule has a row (idempotent)
    from core.database import AsyncSessionLocal
    from services.policy import seed_policies
    async with AsyncSessionLocal() as db:
        await seed_policies(db)
    yield
    await engine.dispose()


app = FastAPI(title="AIU Academic Advisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "aiu-advisor-api"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(students.router, prefix="/students", tags=["students"])
app.include_router(courses.router, prefix="/courses", tags=["courses"])
app.include_router(enrollments.router, prefix="/enrollments", tags=["enrollments"])
app.include_router(schedule.router, prefix="/schedule", tags=["schedule"])
app.include_router(gpa.router, prefix="/gpa", tags=["gpa"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(advisor.router, prefix="/advisor", tags=["advisor"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(financial.router, prefix="/financial", tags=["financial"])
app.include_router(petitions.router, prefix="/petitions", tags=["petitions"])
app.include_router(capstone.router, prefix="/capstone", tags=["capstone"])
app.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])
app.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
app.include_router(retakes.router, prefix="/retakes", tags=["retakes"])
app.include_router(admin_auth.router, prefix="/admin/auth", tags=["admin"])
app.include_router(admin_dashboard.router, prefix="/admin", tags=["admin"])
app.include_router(admin_students.router, prefix="/admin", tags=["admin"])
app.include_router(admin_policies.router, prefix="/admin", tags=["admin"])
app.include_router(admin_grades.router, prefix="/admin", tags=["admin"])
app.include_router(admin_approvals.router, prefix="/admin", tags=["admin"])
app.include_router(admin_catalog.router, prefix="/admin", tags=["admin"])
app.include_router(admin_financial.router, prefix="/admin", tags=["admin"])
app.include_router(admin_notifications.router, prefix="/admin", tags=["admin"])
app.include_router(admin_offerings.router, prefix="/admin", tags=["admin"])
app.include_router(admin_assistant.router, prefix="/admin", tags=["admin"])
app.include_router(admin_staff.router, prefix="/admin", tags=["admin"])


@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        payload = decode_token(token)
        student_id = payload.get("sub")
        if not student_id or payload.get("type") != "access":
            await websocket.close(code=4401)
            return
    except Exception:
        await websocket.close(code=4401)
        return

    await ws_manager.connect(websocket, str(student_id))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, str(student_id))
