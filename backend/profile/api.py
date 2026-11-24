import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from backend import db, settings
from backend.profile.models import Household

router = APIRouter(prefix="/api/profile")


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(settings.db_path(request.app.state.data_dir))
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def load_household(conn: sqlite3.Connection) -> Household | None:
    row = conn.execute("SELECT body FROM profile WHERE id = 1").fetchone()
    return Household.model_validate_json(row[0]) if row else None


@router.get("")
def get_profile(conn: Conn) -> Household:
    household = load_household(conn)
    if household is None:
        raise HTTPException(404, "No profile saved")
    return household


@router.put("")
def put_profile(household: Household, conn: Conn) -> Household:
    try:
        household.check_plan_to_age()
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    conn.execute(
        "INSERT INTO profile (id, body) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET body = excluded.body",
        (household.model_dump_json(by_alias=True),),
    )
    conn.commit()
    return household
