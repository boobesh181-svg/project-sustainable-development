# Sustainable Construction MRV System

**Canonical backend is in `/backend`.**

- Start here: [README_CANONICAL.md](README_CANONICAL.md)
- Note: some legacy endpoint examples in this README may not reflect the canonical `/api/v1/*` routes.

A comprehensive Materials, Resources, and Verification (MRV) system for sustainable construction projects with carbon accounting and anti-corruption features.

## Features

- **Sample Management**: Track construction material samples from collection to approval
- **Lab Testing**: Upload and manage test results with automatic QA flagging
- **Chain of Custody**: Complete evidence trail for sample handling
- **Review Workflow**: Multi-level approval system for test results
- **Carbon Accounting**: Automatic CO2 calculation and credit tracking
- **Anomaly Detection**: Automated flagging for geotag and value anomalies
- **Security**: Role-based access control and audit trails

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL or SQLite database
- Node.js 16+ (for frontend)

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd windsurf-project
```

2. Set up backend
```bash
cd backend
pip install -r requirements.txt
```

3. Set up frontend
```bash
cd ../frontend
npm install
```

### Database Setup

1. Run migrations
```bash
cd backend
alembic upgrade head
```

2. Seed sample data
```bash
cd backend
python scripts/seed_mrv.py
```

### Running the Application

1. Start backend server
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. Start frontend (in separate terminal)
```bash
cd frontend
npm run dev
```

The application will be available at:
- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- API Documentation: http://localhost:8000/docs

## Database Migrations

### Running Migrations

To create and apply database schema changes:

```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply all migrations
alembic upgrade head

# Rollback to specific migration
alembic downgrade <revision_id>
```

### Migration Files

Recent migrations include:
- `add_carbon_models.py`: Adds CO2 accounting tables (CarbonLedger, CarbonCreditIssuance)
- `add_mrv_qa_columns.py`: Adds QA flagging and mrv_flags columns

## Sample Data Seeding

### Loading Sample Data

The system includes comprehensive sample data for testing and demonstrations:

```bash
cd backend
python scripts/seed_mrv.py
```

This creates:
- 2 projects (Green Office Complex, Eco Residential Tower)
- 2 testing labs (Certified Materials Testing Lab, Pacific Northwest Testing Services)
- 6 samples (3 per project, including anomalous samples)
- 9 test results (mix of pass/fail with various parameters)
- Chain of custody records
- QA flags for anomaly detection

### Sample Data Structure

- **Normal samples**: Expected geotags and test values
- **Anomalous geotag**: Sample collected far from project site
- **Anomalous values**: Test results outside expected ranges
- **Mixed results**: Both passing and failing tests for realistic workflow

## API Endpoints

### Authentication

All endpoints require authentication except health checks.

This repo supports browser-friendly authentication using **HttpOnly cookies**.

#### Login (sets cookies)
```bash
curl -c cookies.txt \
  -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Admin123!"}'
```

#### Who am I?
```bash
curl -b cookies.txt "http://localhost:8000/api/v1/auth/me"
```

Note: the login response body still includes JWTs for non-browser API clients. The backend accepts either cookies or an `Authorization: Bearer <token>` header.

### Canonical MRV Workflow (Regulator-grade)

The canonical MRV lifecycle lives under `/api/v1/mrv-approval/*` and enforces:
- role gating + separation of duties
- immutable-after-lock/retirement rules (DB triggers)
- versioned emission factor snapshots

#### List projects (scoped by role)
```bash
curl -b cookies.txt "http://localhost:8000/api/v1/projects"
```

#### Create MRV report (DRAFT)
```bash
curl -b cookies.txt \
  -X POST "http://localhost:8000/api/v1/mrv-approval/reports" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<project_uuid>",
    "reporting_period": "2025-Q1",
    "sample_desc": "Quarterly MRV report",
    "parameter": "co2e_total",
    "value": "1000",
    "total_co2e": 1000.0
  }'
```

#### Advance MRV status
```bash
curl -b cookies.txt \
  -X POST "http://localhost:8000/api/v1/mrv-approval/reports/<report_uuid>/advance" \
  -H "Content-Type: application/json" \
  -d '{"next_status":"SUBMITTED"}'
```

### Legacy MRV Ingestion (Feature-gated)

The older ingestion router lives under `/api/mrv/*` and is **disabled by default** in hardened deployments.
To enable it, set `ENABLE_MRV_INGESTION=true` in the backend environment.

## Security and Access Control

### User Roles

- **admin**: Full system access (including approval/lock)
- **project_manager**: Create/manage projects (scoped)
- **contractor**: Create MRV drafts and submit
- **mrv_officer**: Verify submitted MRV reports
- **supplier**: Supplier-facing visibility (read-only)
- **citizen**: Public/read-only visibility (read-only)

### Authentication

- JWT-based auth with **HttpOnly cookie sessions** for browser clients
- Backend accepts either cookies or `Authorization: Bearer <token>` for API clients
- Role-based endpoint access

### Data Protection

- All sensitive data encrypted at rest
- API endpoints use HTTPS in production
- Audit trails for all data modifications
- Chain of custody evidence tracking

## Testing

### Running Tests

```bash
cd backend
pytest tests/ -v
```

### Test Coverage

- **Unit Tests**: Individual component testing
- **Integration Tests**: API endpoint testing
- **End-to-End Tests**: Complete workflow testing
- **Carbon Calculation Tests**: CO2 calculation verification

### Key Test Scenarios

1. **Sample Creation**: Verify sample data validation and storage
2. **Test Upload**: Ensure automatic QA flagging works
3. **Review Workflow**: Test approval/rejection processes
4. **Carbon Calculation**: Verify CO2 calculations with known values
5. **Anomaly Detection**: Test flagging for geotag and value anomalies
6. **Chain of Custody**: Verify evidence trail integrity

## Demo Script for Judges (5 Minutes)

### Introduction (1 minute)
"Welcome to the Sustainable Construction MRV System. This system provides complete transparency in construction material verification with built-in anti-corruption features and carbon accounting."

### Step 1: Sample Collection (1 minute)
"First, field technicians collect material samples with geotagged photos and chain of custody documentation. Each sample is tracked from collection through testing with immutable evidence."

### Step 2: Lab Testing (1 minute)
"Samples are submitted to accredited laboratories where they undergo standardized testing. Our system automatically flags anomalies in test results and geotag locations to detect potential corruption."

### Step 3: Review Process (1 minute)
"MRV officers review flagged samples and test results. The system provides risk scoring and requires multi-level approval for high-risk items. All actions are logged in an immutable audit trail."

### Step 4: Carbon Accounting (1 minute)
"When tests are approved, the system automatically calculates embodied CO2 using industry-standard factors and creates carbon credit opportunities. This provides financial incentives for sustainable material choices."

### Conclusion (30 seconds)
"The complete workflow ensures material authenticity, prevents corruption through automated checks, and enables carbon accounting for sustainable construction. The system is ready for deployment in major infrastructure projects."

## Development

### Project Structure

```
windsurf-project/
├── backend/
│   ├── app/
│   │   ├── mrv/          # MRV models, routes, and logic
│   │   ├── models/        # Database models
│   │   └── api/          # Authentication and API utilities
│   ├── tests/             # Test suite
│   ├── migrations/         # Database migrations
│   └── scripts/           # Utility scripts
├── frontend/
│   ├── src/
│   │   ├── pages/mrv/     # MRV React components
│   │   ├── services/       # API client code
│   │   └── hooks/         # React hooks
└── README.md
```

### Adding New Features

1. Create database models in `backend/app/mrv/models.py`
2. Add API routes in `backend/app/mrv/routes.py`
3. Create frontend components in `frontend/src/pages/mrv/`
4. Add tests in `backend/tests/`
5. Update documentation

## Support

For technical support or questions:
- Check the API documentation at `/docs`
- Review test cases for implementation examples
- Check migration files for database schema changes

## License

[License information here]
