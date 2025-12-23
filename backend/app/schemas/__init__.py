"""All Pydantic schemas for API I/O."""

from .auth import LoginRequest, RefreshRequest
from .project import ProjectCreate, ProjectRead, ProjectBase
from .material import MaterialTokenCreate, MaterialTokenOut, MaterialTokenRedeem
from .mrv import MRVReportCreate, MRVReportOut, MRVCalculationResult

__all__ = [
    # Auth
    "LoginRequest",
    "RefreshRequest",
    # Projects
    "ProjectCreate",
    "ProjectRead",
    "ProjectBase",
    # Materials
    "MaterialTokenCreate",
    "MaterialTokenOut",
    "MaterialTokenRedeem",
    # MRV
    "MRVReportCreate",
    "MRVReportOut",
    "MRVCalculationResult",
]
