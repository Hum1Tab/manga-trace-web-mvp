from __future__ import annotations

import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import DATA_DIR, FRONTEND_DIR, RENDERER_VERSION, SECRET
from .db import connect, init_db
from .security import new_token, short_hmac_u32, verify_password
from .watermark import render_watermarked_bytes

app = FastAPI(title="MangaTrace Web MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256((SECRET + value).encode("utf-8")).hexdigest()


def require_user(session_token: str | None) -> dict:
    if not session_token:
        raise HTTPException(status_code=401, detail="not logged in")
    with connect() as con:
        row = con.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ? AND sessions.expires_at > ? AND users.status = 'active'
            """,
            (session_token, now_iso()),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="invalid session")
        return dict(row)


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateViewRequest(BaseModel):
    page_id: str


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/viewer")
def viewer() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "viewer.html")


@app.post("/api/auth/login")
def login(body: LoginRequest, response: Response) -> dict:
    with connect() as con:
        user = con.execute("SELECT * FROM users WHERE email = ?", (body.email,)).fetchone()
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="email or password is wrong")
        token = new_token()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        con.execute(
            "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user["id"], now_iso(), expires_at),
        )
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 24 * 3600,
    )
    return {"ok": True, "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]}}


@app.post("/api/auth/logout")
def logout(response: Response, session_token: str | None = Cookie(default=None)) -> dict:
    if session_token:
        with connect() as con:
            con.execute("DELETE FROM sessions WHERE token = ?", (session_token,))
    response.delete_cookie("session_token")
    return {"ok": True}


@app.get("/api/auth/me")
def me(session_token: str | None = Cookie(default=None)) -> dict:
    user = require_user(session_token)
    return {"id": user["id"], "email": user["email"], "display_name": user["display_name"]}


@app.get("/api/pages")
def pages(session_token: str | None = Cookie(default=None)) -> dict:
    require_user(session_token)
    with connect() as con:
        rows = con.execute(
            "SELECT id, title, page_number, width, height FROM pages ORDER BY page_number ASC"
        ).fetchall()
    return {"pages": [dict(r) for r in rows]}


@app.post("/api/views")
def create_view(body: CreateViewRequest, session_token: str | None = Cookie(default=None)) -> dict:
    user = require_user(session_token)
    with connect() as con:
        page = con.execute("SELECT * FROM pages WHERE id = ?", (body.page_id,)).fetchone()
        if not page:
            raise HTTPException(status_code=404, detail="page not found")
        view_id = "view_" + uuid.uuid4().hex
        payload_id = random.getrandbits(32)
        auth_tag = short_hmac_u32(SECRET, f"{payload_id}:{page['id']}:{user['id']}")
        seed = uuid.uuid4().hex
        created_at = now_iso()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        con.execute(
            """
            INSERT INTO views(id, user_id, page_id, payload_id, auth_tag, seed, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (view_id, user["id"], page["id"], payload_id, auth_tag, seed, created_at, expires_at),
        )
    return {
        "view_id": view_id,
        "page_id": page["id"],
        "expires_at": expires_at,
        # MVPでは確認用に返す。本番では payload_id/auth_tag は返さない。
        "debug_payload_id": payload_id,
        "debug_auth_tag": auth_tag,
    }


@app.get("/api/views/{view_id}/image")
def view_image(view_id: str, request: Request, session_token: str | None = Cookie(default=None)) -> Response:
    user = require_user(session_token)
    with connect() as con:
        row = con.execute(
            """
            SELECT views.*, pages.base_image_path, pages.page_number
            FROM views JOIN pages ON pages.id = views.page_id
            WHERE views.id = ? AND views.user_id = ? AND views.status = 'active' AND views.expires_at > ?
            """,
            (view_id, user["id"], now_iso()),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="view not found or expired")
        payload_text = f"P{row['payload_id']:08x}A{row['auth_tag']:08x}G{int(row['page_number']):04x}"
        base_path = DATA_DIR / row["base_image_path"]
        if not base_path.exists():
            raise HTTPException(status_code=500, detail=f"base image missing: {row['base_image_path']}")
        image_bytes = render_watermarked_bytes(
            base_path,
            payload_text,
            key=SECRET + ":" + row["seed"],
            format="WEBP",
            quality=92,
            strength=0.22,
        )
        con.execute(
            """
            INSERT INTO render_logs(id, view_id, user_id, page_id, rendered_at, renderer_version, client_ip_hash, user_agent_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "render_" + uuid.uuid4().hex,
                view_id,
                user["id"],
                row["page_id"],
                now_iso(),
                RENDERER_VERSION,
                hash_optional(request.client.host if request.client else None),
                hash_optional(request.headers.get("user-agent")),
            ),
        )
    return Response(
        content=image_bytes,
        media_type="image/webp",
        headers={
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/api/views/{view_id}")
def view_debug(view_id: str, session_token: str | None = Cookie(default=None)) -> dict:
    user = require_user(session_token)
    with connect() as con:
        row = con.execute(
            "SELECT * FROM views WHERE id = ? AND user_id = ?", (view_id, user["id"])
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="view not found")
    d = dict(row)
    return d
