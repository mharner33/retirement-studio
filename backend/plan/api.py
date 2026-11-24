from datetime import date

from fastapi import APIRouter, HTTPException, Request

from backend.engine.projection import Projection, Strategy, project
from backend.profile.api import Conn, load_household
from backend.rules.store import current_rules

router = APIRouter(prefix="/api/plan")


@router.post("/project")
def project_plan(strategy: Strategy, conn: Conn, request: Request) -> Projection:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    rules, _ = current_rules(conn, request.app.state.data_dir)
    return project(household, strategy, rules, date.today().year)
