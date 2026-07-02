"""
광고 보고서B 자동화 웹 앱 (정리본)
핵심 동선만: 로그인 → 광고주 등록(업로드/개별/검색/삭제) → 버전B 생성·다운로드
계정: /setup(최초 admin) · /admin/users(팀원 관리)
"""
import asyncio
import hashlib
import os
import sys
import uuid
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
SRC  = ROOT / "src"
sys.path.insert(0, str(SRC))

load_dotenv(ROOT / ".env")

from web.db import (
    init_db, get_all_clients, get_clients_by_owner, get_client,
    upsert_client, delete_client, delete_clients_by_owner,
    create_report, update_report, get_report, list_reports, delete_report,
)
from collectors.naver_searchad import is_connected, MOCK_MODE

init_db()

app = FastAPI(title="보고서B 자동화")
# 정적 폴더가 없으면(예: git 빈 폴더 미커밋) 생성 후 마운트 — 없으면 시작 시 크래시함
_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# DATA_DIR: 영속 저장 루트. Fly 볼륨(/app/data) 마운트 시 여기에 DB·보고서·업로드가 모두 남는다.
# 로컬은 미설정 → 프로젝트 루트 사용(기존 동작 유지).
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT)))
OUTPUT_DIR = DATA_DIR / "output"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("SESSION_SECRET", "change-me-in-production")
signer = URLSafeTimedSerializer(SECRET_KEY)


def render(request: Request, name: str, **ctx):
    """로그인 사용자용 페이지 렌더 — 공통 컨텍스트 자동 주입."""
    sess = get_session(request)
    now = datetime.now()
    base_ctx = {
        "sess": sess,
        "api_connected": is_connected(),
        "mock_mode": MOCK_MODE,
        "now_year": now.year,
        "now_month": now.month,
    }
    base_ctx.update(ctx)
    return templates.TemplateResponse(request=request, name=name, context=base_ctx)


# 진행 중 작업 (메모리)
jobs: dict[str, dict] = {}


# ── 세션 / 인증 ─────────────────────────────────────────
# 비밀번호 해싱용 고정 솔트 — SESSION_SECRET 과 분리한다.
# (세션키를 바꿔도 비밀번호/로그인이 깨지지 않게 하기 위함)
PW_SALT = os.getenv("PASSWORD_SALT", "e-noble-report::pw-salt::v1")


def _hash_pw(pw: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), PW_SALT.encode(), 100_000).hex()


def get_session(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        return signer.loads(token, max_age=86400 * 7)
    except BadSignature:
        return None


def require_session(request: Request) -> dict:
    sess = get_session(request)
    if not sess:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return sess


def _set_session_cookie(response, user: dict):
    data = {"user_id": user["id"], "name": user["name"], "role": user["role"]}
    response.set_cookie("session", signer.dumps(data), httponly=True, max_age=86400 * 7)


def _is_admin(sess) -> bool:
    return bool(sess and sess.get("role") == "admin")


def _owns(sess, owner_id) -> bool:
    """admin 은 전체, 그 외는 자기 소유만 접근 가능."""
    return _is_admin(sess) or (sess and owner_id is not None and sess.get("user_id") == owner_id)


# ── 로그인 ──────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_session(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    from web.db import get_conn
    with get_conn() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password_hash=?",
            (email.strip().lower(), _hash_pw(password))
        ).fetchone()
    if not user:
        return templates.TemplateResponse(request=request, name="login.html",
                                          context={"error": "이메일 또는 비밀번호가 틀렸습니다."})
    resp = RedirectResponse("/", status_code=302)
    _set_session_cookie(resp, dict(user))
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session")
    return resp


# ── 루트: 로그인 후 광고주 페이지로 ──────────────────────
@app.get("/")
async def index(request: Request):
    if not get_session(request):
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/clients", status_code=302)


# ── 광고주 등록·검색·삭제 ─────────────────────────────────
def _mask(secret) -> str:
    s = str(secret or "")
    if not s:
        return ""
    return "••••" + s[-4:] if len(s) > 4 else "••••"


@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/login", status_code=302)
    clients = get_all_clients() if _is_admin(sess) else get_clients_by_owner(sess["user_id"])
    rows = []
    for c in clients:
        rows.append({
            "id": c["id"], "name": c["name"],
            "naver_customer_id": c.get("naver_customer_id") or "",
            "media": c.get("media") or "",
            "manager_name": c.get("manager_name") or "",
            "has_key": bool(c.get("api_key") and c.get("api_secret")),
            "key_masked": _mask(c.get("api_key")),
        })
    return render(request, "clients.html", active_page="clients",
                  client_rows=rows,
                  added=request.query_params.get("added"),
                  uploaded=request.query_params.get("uploaded"),
                  err=request.query_params.get("err"))


@app.post("/clients/add")
async def clients_add(
    request: Request,
    name: str = Form(...),
    naver_customer_id: str = Form(...),
    api_key: str = Form(""),
    api_secret: str = Form(""),
    media: str = Form("파워링크"),
    manager_name: str = Form(""),
    manager_email: str = Form(""),
):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/login", status_code=302)
    upsert_client(
        naver_customer_id=naver_customer_id.strip(), name=name.strip(),
        owner_id=sess["user_id"],
        api_key=api_key.strip(), api_secret=api_secret.strip(),
        media=media.strip(), manager_name=manager_name.strip(),
        manager_email=manager_email.strip(),
    )
    return RedirectResponse(f"/clients?added={name.strip()}", status_code=302)


@app.post("/clients/{client_id}/delete")
async def clients_delete(client_id: int, request: Request):
    sess = get_session(request)
    if not sess:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    c = get_client(client_id)
    if not c:
        return JSONResponse({"error": "없는 광고주"}, status_code=404)
    if not _owns(sess, c.get("owner_id")):
        return JSONResponse({"error": "권한 없음"}, status_code=403)
    delete_client(client_id)
    return JSONResponse({"ok": True})


@app.get("/clients/template")
async def clients_template(request: Request):
    """로스터 업로드용 xlsx 템플릿 다운로드."""
    if not get_session(request):
        return RedirectResponse("/login", status_code=302)
    import roster
    tpl = UPLOAD_DIR / "roster_template.xlsx"
    roster.create_template(tpl, overwrite=True)
    return FileResponse(path=str(tpl), filename="광고주_로스터_템플릿.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/clients/upload")
async def clients_upload(request: Request, file: UploadFile = File(...),
                         mode: str = Form("append")):
    """엑셀/CSV 로스터 업로드 → 광고주 일괄 등록.
    mode='append' : 기존 목록에 없는 광고주 추가(있으면 갱신)
    mode='replace': 내 광고주 전체 삭제 후 시트 데이터로 새로 채움
    """
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/login", status_code=302)
    import roster
    dest = UPLOAD_DIR / f"roster_{uuid.uuid4().hex[:8]}_{file.filename}"
    dest.write_bytes(await file.read())
    try:
        records = roster.read_file(dest)
    except Exception as e:
        return RedirectResponse(f"/clients?err={e}", status_code=302)

    valid = [r for r in records if (r.get("customer_id") or "").strip()]
    if mode == "replace" and not valid:
        return RedirectResponse("/clients?err=시트에 유효한 광고주(customer_id)가 없어 전체 교체를 중단했습니다.",
                                status_code=302)

    deleted = delete_clients_by_owner(sess["user_id"]) if mode == "replace" else 0

    new_cnt, upd_cnt, skipped = 0, 0, len(records) - len(valid)
    for r in valid:
        cid = r["customer_id"].strip()
        _id, created = upsert_client(
            naver_customer_id=cid, name=r.get("name") or f"광고주 {cid}",
            owner_id=sess["user_id"],
            api_key=r.get("api_key", ""), api_secret=r.get("api_secret", ""),
            media=r.get("media", ""), manager_name=r.get("marketer", ""),
            manager_email=r.get("email", ""),
        )
        if created:
            new_cnt += 1
        else:
            upd_cnt += 1

    if mode == "replace":
        msg = f"기존 {deleted}건 삭제 · {new_cnt}건 추가"
    else:
        msg = f"{new_cnt}건 추가" + (f" · {upd_cnt}건 갱신" if upd_cnt else "")
    if skipped:
        msg += f" · {skipped}건 건너뜀"
    return RedirectResponse(f"/clients?uploaded={msg}", status_code=302)


# ── 버전B 보고서 생성 ────────────────────────────────────
@app.post("/api/generate-v2")
async def generate_v2(
    request: Request,
    client_id: int = Form(...),
    year: int = Form(...),
    month: int = Form(...),
):
    sess = require_session(request)
    client = get_client(client_id)
    if not client:
        return JSONResponse({"error": "클라이언트 없음"}, status_code=404)
    if not _owns(sess, client.get("owner_id")):
        return JSONResponse({"error": "권한 없음"}, status_code=403)
    report_id = create_report(client_id, year, month)
    job_id = f"r{report_id}"
    jobs[job_id] = {"status": "starting", "progress": 0, "report_id": report_id}
    asyncio.create_task(_run_report_v2(job_id, report_id, client, year, month))
    return JSONResponse({"job_id": job_id, "report_id": report_id})


async def _run_report_v2(job_id: str, report_id: int, client: dict, year: int, month: int):
    """버전B 생성: RAW 수집 → 전 시트 채우기 → AI 코멘트(L9) 까지 내부 수행."""
    try:
        jobs[job_id].update({"status": "fetching", "progress": 20})
        update_report(report_id, status="fetching")

        # 팀장이 UI에서 입력한 이 클라이언트의 키를 수집기에 런타임 등록
        if client.get("api_key") and client.get("api_secret"):
            from collectors.naver_searchad import register_account
            register_account(
                client.get("naver_customer_id"),
                client["api_key"], client["api_secret"],
                name=client.get("name", ""), media=client.get("media", ""),
            )

        from v2_report import generate_v2_report
        # 파일명에 report_id 를 넣어 같은 광고주·같은 달 재생성 시 덮어쓰기(충돌) 방지
        uniq_name = f"{year}년{month:02d}월_{client['name']}_보고서B_{report_id}.xlsx"
        out_path = await asyncio.to_thread(
            generate_v2_report,
            client.get("naver_customer_id") or str(client["id"]),
            year, month,
            client_name=client["name"], output_dir=OUTPUT_DIR, out_name=uniq_name,
        )
        filename = out_path.name

        def _read_comment(filepath):
            import openpyxl
            wb = openpyxl.load_workbook(str(filepath))
            if "파워링크_Summary" in wb.sheetnames:
                return wb["파워링크_Summary"].cell(row=9, column=12).value or ""
            return ""
        comment = await asyncio.to_thread(_read_comment, OUTPUT_DIR / filename)

        jobs[job_id].update({"status": "done", "progress": 100,
                             "filename": filename, "comment": comment or ""})
        update_report(report_id, status="done", filename=filename, comment=comment or "")

    except Exception as e:
        import traceback
        update_report(report_id, status="error", error=str(e))
        jobs[job_id].update({"status": "error", "error": str(e),
                             "traceback": traceback.format_exc()})


@app.get("/api/job/{job_id}")
async def job_status(job_id: str, request: Request):
    require_session(request)
    job = jobs.get(job_id)
    if not job:
        try:
            r = get_report(int(job_id.lstrip("r")))
            if r:
                return JSONResponse({"status": r["status"],
                                     "progress": 100 if r["status"] == "done" else 50,
                                     "comment": r["comment"], "filename": r["filename"]})
        except Exception:
            pass
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(job)


# ── 생성된 보고서 ─────────────────────────────────────────
def _reports_scope(sess):
    """admin → 전체, 그 외 → 자기 것만."""
    return None if _is_admin(sess) else sess["user_id"]


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/login", status_code=302)
    reports = list_reports(_reports_scope(sess))
    done = sum(1 for r in reports if r["status"] == "done")
    failed = sum(1 for r in reports if r["status"] == "error")
    return render(request, "reports.html", active_page="reports",
                  reports=reports, done_count=done, failed_count=failed,
                  total_count=len(reports))


@app.post("/reports/download-zip")
async def reports_download_zip(request: Request, ids: str = Form("")):
    """선택(또는 전체) 완료 보고서를 zip 으로 묶어 다운로드."""
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/login", status_code=302)
    import zipfile
    want = {i for i in ids.split(",") if i.strip()}
    reports = list_reports(_reports_scope(sess))
    picked = [r for r in reports
              if r["status"] == "done" and r["filename"]
              and (not want or str(r["id"]) in want)]
    if not picked:
        return JSONResponse({"error": "다운로드할 완료 보고서가 없습니다."}, status_code=404)

    zpath = UPLOAD_DIR / f"reports_{uuid.uuid4().hex[:8]}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for r in picked:
            fp = OUTPUT_DIR / r["filename"]
            if fp.exists():
                z.write(fp, arcname=r["filename"])   # 파일명이 report_id 로 유일 → 충돌 없음
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return FileResponse(path=str(zpath), filename=f"보고서_{stamp}.zip",
                        media_type="application/zip")


@app.post("/reports/delete")
async def reports_delete(request: Request, ids: str = Form("")):
    """보고서 삭제(개별/선택). 소유자(또는 admin)만. 파일도 함께 제거."""
    sess = get_session(request)
    if not sess:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    targets = [i for i in ids.split(",") if i.strip()]
    deleted = 0
    for rid in targets:
        try:
            r = get_report(int(rid))
        except ValueError:
            continue
        if not r or not _owns(sess, r.get("owner_id")):
            continue
        if r.get("filename"):
            fp = OUTPUT_DIR / r["filename"]
            try:
                if fp.exists():
                    fp.unlink()
            except OSError:
                pass
        delete_report(int(rid))
        deleted += 1
    return JSONResponse({"ok": True, "deleted": deleted})


# ── 다운로드 ─────────────────────────────────────────────
@app.get("/download/{filename}")
async def download(filename: str, request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/login", status_code=302)
    # 본인(또는 admin) 소유 보고서 파일만 허용
    allowed = {r["filename"] for r in list_reports(_reports_scope(sess)) if r.get("filename")}
    if filename not in allowed:
        raise HTTPException(status_code=404)
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path=str(path), filename=filename,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── 팀원(로그인 계정) 관리 ────────────────────────────────
@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    sess = get_session(request)
    if not sess or sess["role"] != "admin":
        return RedirectResponse("/", status_code=302)
    from web.db import get_conn
    with get_conn() as conn:
        users = [dict(r) for r in conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC").fetchall()]
    return render(request, "admin_users.html", active_page="users",
                  users=users, error=None, success=None)


@app.post("/admin/users/create")
async def create_user(
    request: Request,
    name: str = Form(...), email: str = Form(...),
    password: str = Form(...), role: str = Form(...),
):
    sess = get_session(request)
    if not sess or sess["role"] != "admin":
        return RedirectResponse("/", status_code=302)
    from web.db import get_conn
    email = email.strip().lower()
    role = role if role in ("admin", "manager", "member") else "member"
    with get_conn() as conn:
        if conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]
            return render(request, "admin_users.html", active_page="users",
                          users=users, error=f"이미 존재하는 이메일입니다: {email}", success=None)
        conn.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?,?,?,?)",
                     (email, _hash_pw(password), name.strip(), role))
    with get_conn() as conn:
        users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]
    return render(request, "admin_users.html", active_page="users",
                  users=users, error=None, success=f"{name} 계정이 생성되었습니다.")


@app.post("/admin/users/{user_id}/delete")
async def delete_user(user_id: int, request: Request):
    sess = get_session(request)
    if not sess or sess["role"] != "admin":
        return JSONResponse({"error": "권한 없음"}, status_code=403)
    if user_id == sess["user_id"]:
        return JSONResponse({"error": "본인 계정은 삭제 불가"}, status_code=400)
    from web.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    return JSONResponse({"ok": True})


# ── 초기 관리자 계정 생성 (최초 1회) ─────────────────────
@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    from web.db import get_conn
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request=request, name="setup.html", context={})


@app.post("/setup")
async def setup(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    from web.db import get_conn
    with get_conn() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return RedirectResponse("/login", status_code=302)
        conn.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?,?,?,?)",
                     (email.strip().lower(), _hash_pw(password), name, "admin"))
    return RedirectResponse("/login", status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
