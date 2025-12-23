# MRV Dashboard - Database Setup Guide

## ⚠️ CRITICAL: PostgreSQL Requirement

This system **REQUIRES PostgreSQL** for production use. SQLite is NOT supported for the following reasons:

### Why PostgreSQL is Mandatory

1. **UUID Data Type**: All models use PostgreSQL's native UUID type for primary keys
2. **JSONB Support**: Emission factor snapshots and audit logs use JSONB for versioning
3. **CHECK Constraints**: Role separation enforcement (issuer ≠ verifier ≠ approver)
4. **Triggers**: Immutability enforcement for retired carbon credits
5. **PostGIS (Future)**: Geospatial queries for delivery verification
6. **Regulatory Compliance**: PostgreSQL's ACID properties meet audit standards

## Quick Setup (Development)

### Option 1: Docker PostgreSQL (Recommended)

```bash
# Start PostgreSQL container
docker run --name mrv-postgres -e POSTGRES_PASSWORD=your_password -e POSTGRES_DB=mrvdb -p 5432:5432 -d postgres:15

# Update backend/.env
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/mrvdb
```

### Option 2: Windows PostgreSQL Installation

1. Download PostgreSQL 15+ from [https://www.postgresql.org/download/windows/](https://www.postgresql.org/download/windows/)
2. Install with default settings (port 5432)
3. Create database:
   ```sql
   CREATE DATABASE mrvdb;
   CREATE USER mrv_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE mrvdb TO mrv_user;
   ```
4. Update `backend/.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://mrv_user:secure_password@localhost:5432/mrvdb
   ```

## Database Schema - 9 Core Tables

### 1. Users & Access Control
- **users**: System actors (email, password_hash, role, created_at)
- **roles**: Role definitions (admin, contractor, mrv_officer, auditor, public)

### 2. Projects
- **projects**: Construction projects (name, location, owner_org, status, budget)

### 3. Material Tokens (Supply Chain)
- **material_tokens**: Material batch authorizations (project_id, material_type, quantity, supplier, issued_at, status)

### 4. Delivery Verification
- **deliveries** / **delivery_verification**: Physical proof (token_id, gps_lat, gps_lon, gps_hash, photo_hash, delivered_at, verified)

### 5. Emission Factors (IMMUTABLE)
- **emission_factors**: CO₂ factors with versioning (material_type, factor_value, unit, source, version, valid_from, valid_to, factor_hash)
  - **CRITICAL**: Once activated, records cannot be edited or deleted
  - New versions created instead of updates
  - factor_hash provides SHA256 lock

### 6. MRV Reports (Core Model)
- **mrv_reports**: Measurement, Reporting, Verification (project_id, period_start, period_end, total_quantity, total_emissions, emission_factor_snapshot, status, created_by, approved_by, approved_at)
  - Once approved → **IMMUTABLE** at database level

### 7. Anomaly Detection
- **anomalies** / **anomaly_alert**: Rule violations (related_token_id, rule_code, severity, description, detected_at, resolved)
  - Rules: quantity_too_high, delivery_too_far, duplicate_token, factor_mismatch

### 8. Audit Log (APPEND-ONLY)
- **audit_logs**: Complete action history (actor_id, action, entity_type, entity_id, before_state, after_state, timestamp, hash)
  - **CRITICAL**: Cannot be edited or deleted
  - Hash chains provide tamper evidence
  - Legal defensibility

### 9. Public Transparency
- **public_metrics**: Aggregated public data (project_id, total_co2, verified_co2, last_updated)
  - Read-only
  - No sensitive data (PII, contracts, suppliers)

## Running Migrations

Once PostgreSQL is installed and configured:

```bash
cd backend

# Generate migration
python -m alembic revision --autogenerate -m "Initial schema"

# Apply migrations
python -m alembic upgrade head

# Verify current version
python -m alembic current

# Seed sample data
python scripts/seed_mrv.py
```

## Current Demo Mode

**TEMPORARY WORKAROUND**: The dashboard currently returns **mock data** if PostgreSQL is unavailable.

This allows frontend development without a database, but is **NOT production-ready**.

To see mock data:
1. Both servers running (backend on 8000, frontend on 5173)
2. Navigate to http://localhost:5173
3. Dashboard loads with sample KPIs and charts

**Mock Data Indicators**:
- Active Projects: 12
- Total CO₂ Saved: 14,523.5 tCO₂e
- Material Tokens Issued (Month): 156
- Tokens Redeemed: 92.3%
- Open Anomalies: 3

## Production Deployment Checklist

- [ ] PostgreSQL 15+ installed
- [ ] Database `mrvdb` created
- [ ] User with proper privileges configured
- [ ] `backend/.env` updated with PostgreSQL connection string
- [ ] All Alembic migrations applied
- [ ] Sample data seeded (optional)
- [ ] Backup strategy implemented
- [ ] Audit log retention policy configured
- [ ] Monitoring/alerting set up

## Troubleshooting

### Error: "password authentication failed for user"
- Check `DATABASE_URL` in `backend/.env`
- Verify PostgreSQL is running: `psql -U postgres -c "SELECT version();"`
- Test connection: `psql -U mrv_user -d mrvdb`

### Error: "Can't render element of type UUID"
- Using SQLite instead of PostgreSQL
- Update `.env` to PostgreSQL connection string
- SQLite does not support PostgreSQL UUID type

### Error: "Target database is not up to date"
- Run migrations: `python -m alembic upgrade head`
- Check migration history: `python -m alembic history`

### Error: "Multiple head revisions"
- Merge heads: `python -m alembic merge -m "Merge heads" heads`
- Apply merge: `python -m alembic upgrade head`

## Database Compliance Principles

All tables follow these rules:

1. **Immutability**: Retired carbon credits, approved MRV reports cannot be modified
2. **Reproducibility**: Same input → same CO₂ calculation (emission factor versioning)
3. **Traceability**: Who did what, when (audit_logs table)
4. **Separation of Duties**: issuer ≠ verifier ≠ approver (CHECK constraints)
5. **Append-Only Audit**: audit_logs table never allows DELETE or UPDATE

## Next Steps

1. **Install PostgreSQL** (see Quick Setup above)
2. **Update backend/.env** with PostgreSQL connection
3. **Run migrations**: `cd backend && python -m alembic upgrade head`
4. **Seed data**: `python scripts/seed_mrv.py`
5. **Restart backend**: Server will auto-reload and connect to PostgreSQL
6. **Verify dashboard**: Navigate to http://localhost:5173 and see real data

---

**Status**: ✅ Frontend running | ⚠️ Backend using mock data (PostgreSQL required for production)

For PostgreSQL installation help, see: https://www.postgresql.org/docs/current/tutorial-install.html
