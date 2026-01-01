from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.demo import DemoWalkthroughState, DemoWalkthroughStep


router = APIRouter()


@router.get("/walkthrough-state", response_model=DemoWalkthroughState)
async def get_demo_walkthrough_state() -> DemoWalkthroughState:
    """Return the ordered demo walkthrough steps.

    This endpoint is intentionally read-only and does not require auth so the
    demo script can be displayed before login. It does not expose credentials.
    """

    steps = [
        DemoWalkthroughStep(order=1, title="Login"),
        DemoWalkthroughStep(order=2, title="View seeded project"),
        DemoWalkthroughStep(order=3, title="View MRV lifecycle (draft → approved)"),
        DemoWalkthroughStep(order=4, title="View emission factor snapshot"),
        DemoWalkthroughStep(order=5, title="View anomaly explanation"),
        DemoWalkthroughStep(order=6, title="Export compliance bundle"),
    ]

    return DemoWalkthroughState(demo_mode=bool(settings.DEMO_MODE), steps=steps)
