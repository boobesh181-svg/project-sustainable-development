# Sustainable Construction MRV System

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

### MRV Sample Management

#### Create Sample
```bash
curl -X POST "http://localhost:8000/api/mrv/samples" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-001",
    "collected_by": "John Smith",
    "collected_at": "2025-11-15T09:00:00Z",
    "geotag_lat": 37.7749,
    "geotag_lon": -122.4194,
    "sample_type": "concrete",
    "notes": "Foundation concrete sample"
  }'
```

#### Get Sample Details
```bash
curl -X GET "http://localhost:8000/api/mrv/samples/SAMP-001" \
  -H "Authorization: Bearer <token>"
```

#### Submit Sample to Lab
```bash
curl -X POST "http://localhost:8000/api/mrv/samples/SAMP-001/submit_lab" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "lab_id": "lab-001",
    "submitted_at": "2025-11-15T14:00:00Z",
    "notes": "Submit for compressive strength testing"
  }'
```

### Test Result Management

#### Upload Test Result
```bash
curl -X POST "http://localhost:8000/api/mrv/tests/SAMP-001/upload" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "parameter": "compressive_strength",
    "value": "30.5",
    "unit": "MPa",
    "method": "ASTM C39",
    "tested_at": "2025-11-20T10:00:00Z",
    "notes": "Normal compressive strength"
  }'
```

#### Review Test Result
```bash
curl -X POST "http://localhost:8000/api/mrv/tests/TEST-001/review" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "action": "approve",
    "reviewer_id": "reviewer123",
    "comments": "Test approved - meets all requirements"
  }'
```

### Carbon Accounting

#### Get Project CO2 Breakdown
```bash
curl -X GET "http://localhost:8000/api/mrv/projects/proj-001/co2-breakdown" \
  -H "Authorization: Bearer <token>"
```

#### Get MRV Queue
```bash
curl -X GET "http://localhost:8000/api/mrv/queue" \
  -H "Authorization: Bearer <token>"
```

## Security and Access Control

### User Roles

- **field_technician**: Can create and submit samples
- **lab_technician**: Can upload test results
- **mrv_officer**: Can review and approve tests
- **admin**: Full system access

### Authentication

- JWT-based authentication
- Token expiration: 24 hours
- Automatic token refresh
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
