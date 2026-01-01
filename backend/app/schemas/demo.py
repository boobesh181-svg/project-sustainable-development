from __future__ import annotations

from pydantic import BaseModel


class DemoWalkthroughStep(BaseModel):
    order: int
    title: str


class DemoWalkthroughState(BaseModel):
    demo_mode: bool
    steps: list[DemoWalkthroughStep]
