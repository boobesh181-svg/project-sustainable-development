# Copilot Instructions for Sustainable Construction MRV System

## Architecture Overview

This is a **regulator-grade Materials, Resources, and Verification (MRV) system** for sustainable construction with strict compliance requirements:

- **Canonical Backend**: `/backend` (FastAPI + PostgreSQL) — this is THE execution backend. `/app`, `/prototype`, and `/sustainable_city_poc` are deprecated.
- **Frontend**: `/frontend` (React + TypeScript + Tailwind/Recharts) — dashboard-only; no editing UI.
- **Database**: PostgreSQL only (no SQLite in production); async SQLAlchemy 2.0+; Alembic migrations mandatory.

### Key Principles (Non-Negotiable)

1. **ISO-14064 Reproducibility**: All CO₂ calculations must be versioned (emission factors, methodologies). No floating-point surprises.
2. **Append-Only Audit Logs**: Once a carbon credit reaches `retired` status, it is immutable at DB level (PostgreSQL triggers enforce this).
3. **Separation of Duties**: issuer ≠ verifier ≠ approver (enforced via CHECK constraints).
4. **No Breaking Changes Without Migrations**: Every schema change requires an Alembic migration. Never modify `models/` without a corresponding migration.

---

## Core Architecture & Data Flows

### Backend Structure (`/backend/app`)

```
app/
  api/v1/
    auth.py, users.py, projects.py, mrv.py, anomalies.py, dashboard.py, upload.py
  models/
    user.py, role.py, project.py, material_token.py, mrv_report.py, 
    sensor_reading.py, anomaly_alert.py, whistleblower.py, lookup.py, supplier.py
  schemas/
    kpi.py, project.py, token.py, auth.py, user.py
  services/
    dashboard_service.py, file_service.py, user_service.py
  db/
    session.py (async SQLAlchemy setup), base.py (DeclarativeBase)
  core/
    config.py (pydantic Settings), security.py (JWT utilities)
  mrv/
    carbon.py, credits.py, notifications.py, qa.py, routes.py, schemas.py, utils_file.py
```

### Request Flow (Example: Dashboard)

1. **Frontend** (`src/App.tsx`) → `fetchDashboardSummary()` and `fetchDashboardCharts()`
2. **Backend Router** → `/api/v1/dashboard/summary` → `dashboard.py` router
3. **Service** → `dashboard_service.get_dashboard_summary(db)` (complex SQL aggregations)
4. **Models** → direct queries on `Project`, `MaterialToken`, `SensorReading`, `AnomalyAlert`, etc.
5. **Response Schema** → `DashboardSummary` + `DashboardCharts` (Pydantic models)

### Database Session Management

- **Async First**: All DB operations are `async` via `AsyncSession` (no blocking I/O).
- **Dependency Injection**: `get_db()` in `deps.py` injects `AsyncSession` into route handlers.
- **Context Management**: Routes must `async with` sessions or use Depends.

Example:
```python
@router.get("/summary")
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_dashboard_summary(db)
```

---

## Critical Patterns & Conventions

### 1. Models (PostgreSQL + Compliance)

**Location**: `backend/app/models/*.py`

**Must-Have**:
- All models inherit from `Base` (see `db/base.py`).
- UUIDs for IDs (PostgreSQL `UUID` type), not integers.
- `created_at` and `updated_at` timestamps (UTC timezone-aware).
- Role separation via CHECK constraints (issuer ≠ verifier ≠ approver).
- Immutable fields after certain lifecycle states (e.g., retired carbon credits).

**Example** (carbon_credit.py):
```python
from sqlalchemy import CheckConstraint, Numeric, String, event, DDL
from sqlalchemy.dialects.postgresql import UUID

class CarbonCreditLifecycle(Base):
    __tablename__ = "carbon_credit_lifecycle"
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_number: Mapped[int] = mapped_column(unique=True)
    status: Mapped[LifecycleStatus] = mapped_column(SAEnum(LifecycleStatus))
    
    # Role separation
    issuer_id, verifier_id, approver_id = ForeignKey(...)
    
    __table_args__ = (
        CheckConstraint("issuer_id IS DISTINCT FROM verifier_id ..."),  # Separation of duties
        CheckConstraint("status <> 'retired' OR retired_at IS NOT NULL"),  # Immutability rule
    )

# Immutability enforced at DB level
@event.listen(CarbonCreditLifecycle.__table__, "after_create")
def create_immutability_trigger(target, connection, **kw):
    connection.execute(DDL("CREATE TRIGGER ... BEFORE UPDATE ..."))
```

**When Adding a Model**:
1. Create new file in `models/`.
2. Add import to `models/__init__.py`.
3. Create Alembic migration: `alembic revision --autogenerate -m "Add <ModelName>"`.
4. Review migration; add CHECK constraints manually if Alembic missed them.
5. Run `alembic upgrade head` locally.

### 2. Schemas (Pydantic Validation)

**Location**: `backend/app/schemas/*.py`

**Rules**:
- Match model structure but add validation logic.
- Use `ConfigDict(from_attributes=True)` for ORM mode (renamed from `orm_mode`).
- Keep "Create" and "Out" schemas separate.

**Example**:
```python
from pydantic import BaseModel, ConfigDict

class ProjectOut(BaseModel):
    id: UUID
    name: str
    lat: float | None
    lon: float | None
    budget_usd: float
    
    model_config = ConfigDict(from_attributes=True)

class ProjectCreate(BaseModel):
    name: str
    lat: float | None = None
    lon: float | None = None
    budget_usd: float = 0.0
```

### 3. Routers (API Endpoints)

**Location**: `backend/app/api/v1/*.py`

**Convention**:
- Use `APIRouter` with prefix in `main.py`.
- All endpoints are async.
- Return Pydantic schemas, not ORM models.
- Use `Depends(get_db)` for DB session, `Depends(get_current_user)` for auth.

**Example**:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)) -> DashboardSummary:
    return await dashboard_service.get_dashboard_summary(db)
```

### 4. Services (Business Logic)

**Location**: `backend/app/services/*.py`

**Purpose**: Encapsulate complex queries, calculations, and side effects.

**Example** (`dashboard_service.py`):
```python
async def get_dashboard_summary(db: AsyncSession) -> DashboardSummary:
    """Calculate all 12 KPIs using optimized SQL queries."""
    # 1. Active projects count
    active = (await db.execute(
        select(func.count(Project.id)).where(Project.status == ProjectStatus.ACTIVE)
    )).scalar() or 0
    
    # 2. CO2 calculations (versioned emission factors)
    co2_query = await db.execute(
        select(func.coalesce(func.sum(SensorReading.value), 0))
        .where(SensorReading.sensor_type == SensorType.CO2_EMBODIED)
    )
    total_co2 = float(co2_query.scalar() or 0)
    
    return DashboardSummary(
        active_projects=int(active),
        total_co2_saved_t=total_co2,
        ...
    )
```

### 5. Frontend (React + TypeScript)

**Location**: `frontend/src/`

**Structure**:
- `services/api.ts`: API client (typed fetch wrappers).
- `charts/`: Recharts-based chart components (named `*Chart.tsx`).
- `pages/`: Route components.
- `hooks/`: Custom React hooks (if any).
- `App.tsx`: Main app entry point.

**Pattern** (API fetch):
```typescript
export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}
```

**Pattern** (Component with data):
```tsx
const App: React.FC = () => {
  const [data, setData] = useState<DashboardSummary | null>(null);
  useEffect(() => {
    (async () => {
      const summary = await fetchDashboardSummary();
      setData(summary);
    })();
  }, []);
  
  return <div>{data && <KpiCard label="Projects" value={data.active_projects} />}</div>;
};
```

---

## Developer Workflows

### Database Migrations

**New Schema Change**:
```bash
cd backend
alembic revision --autogenerate -m "Add <feature>"
# Review: backend/migrations/versions/<revision_id>.py
# Manually add CHECK constraints, indexes, triggers if Alembic missed them
alembic upgrade head
```

**Rollback**:
```bash
alembic downgrade -1  # One step back
```

**Verify Current Schema**:
```bash
alembic current
```

### Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
pytest tests/test_mrv_models.py -v  # Specific test file
```

### Local Development

**Backend** (with auto-reload):
```bash
cd backend
cp .env.example .env  # Configure DATABASE_URL, SECRET_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev  # Runs on http://localhost:5173
```

**Seed Sample Data**:
```bash
cd backend
python scripts/seed_mrv.py
```

### Health Checks

- **Backend Health**: `GET http://localhost:8000/health` → `{"status": "ok", "db": true}`
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Frontend**: `http://localhost:5173`

---

## Key Compliance Rules

### Carbon Credit Lifecycle (Immutable After Retirement)

Once a carbon credit status becomes `retired`:
1. No UPDATE or DELETE allowed at DB level (PostgreSQL trigger blocks it).
2. `retired_at`, `retired_by`, and `retirement_reason` must all be populated.
3. Reversion is impossible; audit log is append-only.

**Example**: Never allow status regression (`retired` → `approved`).

### Emission Factor Versioning

All CO₂ calculations must reference a specific emission factor version:
```python
class CarbonCreditLifecycle(Base):
    emission_factor_version: str  # e.g. "ipcc_ar6_2023_04"
    methodology_version: str      # e.g. "iso14064_3"
```

Always store the *version* with the calculation, never just the value.

### Role-Based Access Control (RBAC)

- **Roles**: admin, project_manager, contractor, mrv_officer, supplier, citizen
- **Separation**: issuer ≠ verifier ≠ approver (enforce at DB and endpoint level)
- **Example**: Only admins can mark credits as retired.

---

## Common Pitfalls (Avoid These)

1. **Using SQLite in production**: PostgreSQL only. SQLite is for dev/testing only.
2. **Forgetting migrations**: Every model change = one migration file.
3. **Mutable status after retirement**: Status must be immutable; use DB triggers.
4. **Floating-point CO₂ values**: Use `Numeric(18, 6)` for precision.
5. **Fetching all rows**: Use `select(...).where(...)` to limit query scope.
6. **Hardcoding emission factors**: Always version and store with calculation.
7. **Breaking API contracts**: Add new fields as optional; don't remove or rename old ones.

---

## Tools & Extensions

- **FastAPI**: Framework (async-first, built-in Swagger).
- **SQLAlchemy 2.0**: ORM with async support.
- **Alembic**: Schema versioning.
- **Pydantic v2**: Validation and serialization.
- **Recharts**: Frontend charting.
- **Tailwind CSS**: Styling.

---

## Quick Reference Commands

```bash
# Backend startup
cd backend && uvicorn app.main:app --reload --port 8000

# Database
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Seed data
python scripts/seed_mrv.py

# Frontend startup
cd frontend && npm run dev

# Tests
pytest tests/ -v
```

---

## Questions for AI Agents

When working on this codebase:
- **Always ask**: "Is this a schema change? Do I need a migration?"
- **Always check**: "Are separation of duties enforced? issuer ≠ verifier ≠ approver?"
- **Always verify**: "Is this immutable after retirement? Does DB-level trigger protect it?"
- **Always test**: "Does this calculation use the correct versioned emission factor?"
