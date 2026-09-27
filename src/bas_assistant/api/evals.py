"""GET /evals/latest: the newest golden-set and red-team runs, for the Evals tab."""

from typing import Annotated

from fastapi import APIRouter, Depends

from bas_assistant.evals.runs import LatestRuns, latest_runs
from bas_assistant.runtime import AppRuntime, get_runtime

router = APIRouter()


@router.get("/evals/latest")
def latest(runtime: Annotated[AppRuntime, Depends(get_runtime)]) -> LatestRuns:
    return latest_runs(runtime.agent.engine)
