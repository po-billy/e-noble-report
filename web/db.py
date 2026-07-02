"""SQLite 데이터베이스 - 클라이언트, 보고서 관리"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"
DB_PATH.parent.mkdir(exist_ok=True)


# owner_id 로 팀장별 격리. naver_customer_id 는 (팀마다 같은 광고주 가능해) UNIQUE 아님.
CLIENTS_SQL = """CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id        INTEGER,
    naver_customer_id TEXT,
    name            TEXT NOT NULL,
    homepage        TEXT DEFAULT '',
    manager_name    TEXT DEFAULT '',
    manager_email   TEXT DEFAULT '',
    manager_phone   TEXT DEFAULT '',
    template_type   TEXT DEFAULT 'A',
    media           TEXT DEFAULT '',
    api_key         TEXT DEFAULT '',
    api_secret      TEXT DEFAULT '',
    key_status      TEXT DEFAULT '',
    active          INTEGER DEFAULT 1,
    synced_at       TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
)"""


def init_db():
    # 1) 기본 테이블 — 별도 트랜잭션으로 먼저 커밋 (마이그레이션이 실패해도 항상 유지)
    with get_conn() as conn:
        conn.execute(CLIENTS_SQL)
        conn.execute("""CREATE TABLE IF NOT EXISTS reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       INTEGER REFERENCES clients(id),
            year            INTEGER NOT NULL,
            month           INTEGER NOT NULL,
            filename        TEXT,
            comment         TEXT,
            status          TEXT DEFAULT 'pending',
            error           TEXT DEFAULT '',
            assigned_to     INTEGER,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL DEFAULT '',
            name            TEXT NOT NULL,
            role            TEXT DEFAULT 'member',
            parent_id       INTEGER,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS client_users (
            client_id       INTEGER REFERENCES clients(id),
            user_id         INTEGER REFERENCES users(id),
            PRIMARY KEY (client_id, user_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER,
            report_id       INTEGER,
            kind            TEXT,      -- assigned | updated | removed
            message         TEXT,
            seen            INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        )""")

    # 2) 마이그레이션 — 실패해도 기본 테이블/앱은 살아있게 격리
    try:
        with get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS _clients_old")   # 이전 실패 잔재 정리
            cols = {r[1] for r in conn.execute("PRAGMA table_info(clients)")}
            for col in ("api_key", "api_secret", "media", "key_status"):
                if col not in cols:
                    conn.execute(f"ALTER TABLE clients ADD COLUMN {col} TEXT DEFAULT ''")
            if "owner_id" not in cols:
                conn.execute("ALTER TABLE clients ADD COLUMN owner_id INTEGER")
            rcols = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
            if "error" not in rcols:
                conn.execute("ALTER TABLE reports ADD COLUMN error TEXT DEFAULT ''")
            if "assigned_to" not in rcols:
                conn.execute("ALTER TABLE reports ADD COLUMN assigned_to INTEGER")
            ucols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
            if "parent_id" not in ucols:
                conn.execute("ALTER TABLE users ADD COLUMN parent_id INTEGER")

            # 레거시 UNIQUE(naver_customer_id) 제거 → 팀마다 같은 광고주 등록 허용
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='clients'").fetchone()
            if row and "UNIQUE" in (row[0] or "").upper():
                conn.execute("DROP TABLE IF EXISTS _clients_old")
                conn.execute("ALTER TABLE clients RENAME TO _clients_old")
                conn.execute(CLIENTS_SQL)
                newc = [r[1] for r in conn.execute("PRAGMA table_info(clients)")]
                oldc = [r[1] for r in conn.execute("PRAGMA table_info(_clients_old)")]
                common = ",".join(c for c in newc if c in oldc)
                conn.execute(f"INSERT INTO clients ({common}) SELECT {common} FROM _clients_old")
                conn.execute("DROP TABLE _clients_old")

            conn.execute("""UPDATE clients SET owner_id=(SELECT MIN(id) FROM users)
                            WHERE owner_id IS NULL AND EXISTS(SELECT 1 FROM users)""")
    except Exception as e:
        print(f"[init_db] migration skipped: {e}")


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 클라이언트 ────────────────────────────────────────────
def upsert_client(naver_customer_id: str | None, name: str,
                  owner_id: int | None = None, **kwargs) -> tuple[int, bool]:
    """클라이언트 추가/갱신 (owner_id 소유자별 격리).
    같은 소유자 안에서 customer_id 또는 이름이 겹치면 갱신, 아니면 신규.
    빈 값으로는 기존 값을 덮어쓰지 않는다(키 유실 방지).
    반환: (client_id, created)  — created=True 면 신규 추가, False 면 기존 갱신."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE owner_id IS ? AND (naver_customer_id=? OR name=?)",
            (owner_id, naver_customer_id, name)
        ).fetchone()

        def pick(field):
            v = kwargs.get(field, "")
            if v:
                return v
            return row[field] if (row and field in row.keys()) else ""

        vals = {f: pick(f) for f in
                ("homepage", "manager_name", "manager_email", "manager_phone",
                 "media", "api_key", "api_secret")}

        if row:
            conn.execute(
                """UPDATE clients SET name=?, homepage=?, manager_name=?,
                   manager_email=?, manager_phone=?, media=?, api_key=?, api_secret=?,
                   synced_at=datetime('now','localtime') WHERE id=?""",
                (name, vals["homepage"], vals["manager_name"], vals["manager_email"],
                 vals["manager_phone"], vals["media"], vals["api_key"], vals["api_secret"],
                 row["id"])
            )
            return row["id"], False
        else:
            cur = conn.execute(
                """INSERT INTO clients (owner_id, naver_customer_id, name, homepage,
                   manager_name, manager_email, manager_phone, media, api_key, api_secret,
                   synced_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
                (owner_id, naver_customer_id, name, vals["homepage"], vals["manager_name"],
                 vals["manager_email"], vals["manager_phone"], vals["media"],
                 vals["api_key"], vals["api_secret"])
            )
            return cur.lastrowid, True


def edit_client(client_id: int, name, naver_customer_id, media,
                manager_name, manager_email, api_key="", api_secret="") -> bool:
    """광고주 정보 수정. api_key/secret 은 값이 있을 때만 교체(빈값이면 기존 유지).
    반환: 키가 새로 입력되었는지(재검증 필요 여부)."""
    with get_conn() as conn:
        row = conn.execute("SELECT api_key, api_secret FROM clients WHERE id=?", (client_id,)).fetchone()
        key_changed = bool(api_key and api_secret)
        ak = api_key if api_key else (row["api_key"] if row else "")
        asec = api_secret if api_secret else (row["api_secret"] if row else "")
        conn.execute(
            """UPDATE clients SET name=?, naver_customer_id=?, media=?,
               manager_name=?, manager_email=?, api_key=?, api_secret=? WHERE id=?""",
            (name, naver_customer_id, media, manager_name, manager_email, ak, asec, client_id))
    return key_changed


def delete_client(client_id: int) -> list[dict]:
    """광고주 삭제 + 연결 보고서·배정·알림 정리.
    반환: 삭제된 보고서 정보 [{id, filename, assigned_to, year, month}] (파일 정리·할당자 통지용)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, assigned_to, year, month FROM reports WHERE client_id=?",
            (client_id,)).fetchall()
        info = [dict(r) for r in rows]
        rids = [r["id"] for r in rows]
        if rids:
            ph = ",".join("?" * len(rids))
            conn.execute(f"DELETE FROM notifications WHERE report_id IN ({ph})", rids)
        conn.execute("DELETE FROM reports WHERE client_id=?", (client_id,))
        conn.execute("DELETE FROM client_users WHERE client_id=?", (client_id,))
        conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
    return info


def delete_clients_by_owner(owner_id: int) -> tuple[int, list[dict]]:
    """소유자의 모든 광고주 + 보고서 삭제('전체 교체'용).
    반환: (삭제된 광고주 수, 삭제된 보고서 정보 리스트)."""
    with get_conn() as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM clients WHERE owner_id=?", (owner_id,)).fetchone()[0]
        rows = conn.execute(
            """SELECT r.id, r.filename, r.assigned_to, r.year, r.month
               FROM reports r JOIN clients c ON c.id=r.client_id WHERE c.owner_id=?""",
            (owner_id,)).fetchall()
        info = [dict(r) for r in rows]
        rids = [r["id"] for r in rows]
        if rids:
            ph = ",".join("?" * len(rids))
            conn.execute(f"DELETE FROM notifications WHERE report_id IN ({ph})", rids)
        conn.execute(
            "DELETE FROM reports WHERE client_id IN (SELECT id FROM clients WHERE owner_id=?)",
            (owner_id,))
        conn.execute(
            "DELETE FROM client_users WHERE client_id IN (SELECT id FROM clients WHERE owner_id=?)",
            (owner_id,))
        conn.execute("DELETE FROM clients WHERE owner_id=?", (owner_id,))
    return cnt, info


def get_all_clients() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE active=1 ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_clients_by_owner(owner_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE active=1 AND owner_id=? ORDER BY name",
            (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_names() -> dict:
    """{user_id: name} — 담당 팀장/할당자 표시용."""
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name FROM users").fetchall()
    return {r["id"]: r["name"] for r in rows}


# ── 조직(팀) 계층 ─────────────────────────────────────────
def set_parent(user_id: int, parent_id: int | None):
    """팀원의 소속 팀장 지정(없으면 None)."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET parent_id=? WHERE id=?", (parent_id or None, user_id))


def get_team_ids(manager_id: int) -> list[int]:
    """팀장 자신 + 소속 팀원 user_id 목록(조회 범위)."""
    with get_conn() as conn:
        rows = conn.execute("SELECT id FROM users WHERE parent_id=?", (manager_id,)).fetchall()
    return [manager_id] + [r["id"] for r in rows]


def get_members_of(manager_id: int) -> list[dict]:
    """해당 팀장의 소속 팀원 목록."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, email FROM users WHERE parent_id=? ORDER BY name",
            (manager_id,)).fetchall()
    return [dict(r) for r in rows]


def clear_user_refs(user_id: int):
    """사용자 삭제 시 유령 참조 정리: 소속 팀원의 parent_id·다른 보고서의 할당·본인 알림."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET parent_id=NULL WHERE parent_id=?", (user_id,))
        conn.execute("UPDATE reports SET assigned_to=NULL WHERE assigned_to=?", (user_id,))
        conn.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))


def is_manager(user_id: int) -> bool:
    with get_conn() as conn:
        r = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    return bool(r and r["role"] == "manager")


def get_users_by_role(role: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, email, parent_id FROM users WHERE role=? ORDER BY name",
            (role,)).fetchall()
    return [dict(r) for r in rows]


def get_clients_scoped(owner_ids: list[int]) -> list[dict]:
    """owner_ids(팀 범위)에 속한 활성 광고주."""
    if not owner_ids:
        return []
    ph = ",".join("?" * len(owner_ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM clients WHERE active=1 AND owner_id IN ({ph}) ORDER BY name",
            list(owner_ids)).fetchall()
    return [dict(r) for r in rows]


def assign_report(report_id: int, member_id: int | None):
    """보고서를 팀원에게 할당(열람 권한 부여). member_id=None 이면 할당 해제."""
    with get_conn() as conn:
        conn.execute("UPDATE reports SET assigned_to=? WHERE id=?", (member_id, report_id))


# ── 알림 ──────────────────────────────────────────────────
def add_notification(user_id: int, report_id, kind: str, message: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notifications (user_id, report_id, kind, message) VALUES (?,?,?,?)",
            (user_id, report_id, kind, message))


def unseen_notif_count(user_id: int) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=? AND seen=0", (user_id,)).fetchone()[0]


def list_notifications(user_id: int, limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


def mark_notifications_seen(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE notifications SET seen=1 WHERE user_id=?", (user_id,))


def client_report_counts(client_ids: list[int]) -> dict:
    """{client_id: {'total': n, 'assigned': m}} — 삭제 경고용."""
    if not client_ids:
        return {}
    ph = ",".join("?" * len(client_ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT client_id AS cid, COUNT(*) AS total,
                       SUM(CASE WHEN assigned_to IS NOT NULL THEN 1 ELSE 0 END) AS assigned
                FROM reports WHERE client_id IN ({ph}) GROUP BY client_id""",
            list(client_ids)).fetchall()
    return {r["cid"]: {"total": r["total"], "assigned": r["assigned"] or 0} for r in rows}


def set_key_status(client_id: int, status: str):
    """API 키 검증 결과 저장: '' 미검증 / 'ok' 정상 / 'invalid' 정보없음."""
    with get_conn() as conn:
        conn.execute("UPDATE clients SET key_status=? WHERE id=?", (status, client_id))


def last_report_dates(owner_ids=None, member_self=None) -> dict:
    """광고주별 최근 '완료' 보고서 생성일(YYYY-MM-DD). {client_id: date}."""
    where, params = _report_scope_clause(owner_ids, member_self)
    where = (where + " AND r.status='done'") if where else "WHERE r.status='done'"
    with get_conn() as conn:
        q = ("SELECT r.client_id AS cid, MAX(r.created_at) AS d "
             "FROM reports r JOIN clients c ON c.id=r.client_id " + where + " GROUP BY r.client_id")
        rows = conn.execute(q, params).fetchall()
    return {r["cid"]: (r["d"] or "")[:10] for r in rows}


def get_client(client_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        return dict(row) if row else None


# ── 보고서 ────────────────────────────────────────────────
def create_report(client_id: int, year: int, month: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reports (client_id, year, month, status) VALUES (?,?,?,'generating')",
            (client_id, year, month)
        )
        return cur.lastrowid


# ── 생성 큐 (서버측 백그라운드 처리) ──────────────────────
def enqueue_report(client_id: int, year: int, month: int) -> int:
    """생성 대기열에 등록. 같은 광고주·같은 달 보고서가 이미 있으면 그 행을 재사용(덮어쓰기),
    없으면 신규 생성. → (광고주, 보고월)당 항상 1건만 유지(중복 누적 방지). 할당은 유지."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM reports WHERE client_id=? AND year=? AND month=? ORDER BY id DESC LIMIT 1",
            (client_id, year, month)
        ).fetchone()
        if row:
            conn.execute("UPDATE reports SET status='queued', error='' WHERE id=?", (row["id"],))
            return row["id"]
        cur = conn.execute(
            "INSERT INTO reports (client_id, year, month, status, error) VALUES (?,?,?,'queued','')",
            (client_id, year, month)
        )
        return cur.lastrowid


def claim_next_report() -> dict | None:
    """대기열에서 가장 오래된 1건을 원자적으로 'processing'으로 잡아 반환.
    단일 프로세스 asyncio 라 이 함수는 원자적으로 동작한다."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if not row:
            return None
        conn.execute("UPDATE reports SET status='processing' WHERE id=?", (row["id"],))
        return dict(row)


def requeue_stuck():
    """서버 시작 시: 진행 중이던(=크래시로 끊긴) 것들을 다시 대기열로.
    구버전 상태('generating'/'fetching' 등)도 정리."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE reports SET status='queued' "
            "WHERE status IN ('processing','generating','fetching','building','commenting')")


def report_status_counts(owner_ids=None, member_self=None) -> dict:
    """상태별 개수(예약/진행/완료/실패 + active). owner_ids/member_self 로 팀 범위 스코프."""
    where, params = _report_scope_clause(owner_ids, member_self)
    with get_conn() as conn:
        q = ("SELECT r.status AS s, COUNT(*) AS n FROM reports r "
             "JOIN clients c ON c.id=r.client_id " + where + " GROUP BY r.status")
        rows = conn.execute(q, params).fetchall()
    d = {"queued": 0, "processing": 0, "done": 0, "error": 0}
    for r in rows:
        s = r["s"] or ""
        if s in ("generating", "fetching", "building", "commenting"):
            d["processing"] += r["n"]
        elif s in d:
            d[s] += r["n"]
    d["active"] = d["queued"] + d["processing"]
    return d


def update_report(report_id: int, **kwargs):
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [report_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE reports SET {fields} WHERE id=?", values)


def _report_scope_clause(owner_ids, member_self):
    """보고서 조회 범위 WHERE 절 생성.
    owner_ids=None → 전체(admin). 그 외 → 소유(팀 범위) OR 나에게 할당된 것."""
    if owner_ids is None:
        return "", []
    parts, params = [], []
    if owner_ids:
        ph = ",".join("?" * len(owner_ids))
        parts.append(f"c.owner_id IN ({ph})")
        params += list(owner_ids)
    if member_self is not None:
        parts.append("r.assigned_to=?")
        params.append(member_self)
    if not parts:
        return "WHERE 1=0", []
    return "WHERE (" + " OR ".join(parts) + ")", params


def list_reports(owner_ids=None, member_self=None, limit: int = 500) -> list[dict]:
    """생성 보고서 목록. owner_ids=None → 전체(admin), 리스트면 그 소유자들(팀) + 나에게 할당된 것."""
    where, params = _report_scope_clause(owner_ids, member_self)
    with get_conn() as conn:
        q = ("SELECT r.*, c.name AS client_name, c.media, c.owner_id "
             "FROM reports r JOIN clients c ON c.id = r.client_id "
             + where + " ORDER BY r.created_at DESC LIMIT ?")
        rows = conn.execute(q, params + [limit]).fetchall()
        return [dict(r) for r in rows]


def delete_report(report_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM reports WHERE id=?", (report_id,))


def get_report(report_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT r.*, c.name as client_name, c.homepage, c.manager_name,
               c.manager_email, c.manager_phone, c.naver_customer_id, c.owner_id
               FROM reports r JOIN clients c ON c.id=r.client_id
               WHERE r.id=?""",
            (report_id,)
        ).fetchone()
        return dict(row) if row else None
