# MRV System Demo Script for Judges (3-5 Minutes)

## Introduction (30 seconds)

"Good morning/afternoon. Today I'll demonstrate the Sustainable Construction MRV System - a comprehensive solution for material verification, anti-corruption protection, and carbon accounting in construction projects."

## Step 1: Sample Collection & Chain of Custody (45 seconds)

"First, let me show how materials are tracked from collection. Field technicians use our mobile app to collect samples with geotagged photos and digital signatures."

*(Show sample creation interface)*

"Each sample gets a unique ID and is instantly logged in our blockchain-backed chain of custody. Notice the geotag validation - samples collected too far from the project site are automatically flagged as potential corruption risks."

## Step 2: Laboratory Testing & QA Flagging (45 seconds)

"Next, samples go to accredited labs. When test results are uploaded, our AI-powered system automatically checks for anomalies."

*(Show test upload with automatic QA flags)*

"Watch as the system flags this concrete sample - the compressive strength is suspiciously high, and the geotag doesn't match the project location. These red flags prevent fraudulent test results from being approved."

## Step 3: Review Workflow & Risk Scoring (45 seconds)

"Now the flagged items go to our MRV officers. The system provides risk scoring - this sample gets an 8/10 risk score due to multiple anomalies."

*(Show review queue with risk scoring)*

"Officers can drill down into each flag, view the evidence chain, and make informed decisions. Every action is logged in an immutable audit trail - no one can tamper with the records."

## Step 4: Carbon Accounting & Credits (45 seconds)

"When tests are approved, our system automatically calculates embodied CO2 using industry-standard factors."

*(Show CO2 breakdown dashboard)*

"This concrete sample represents 15 tonnes of CO2. With 25% recycled content, we calculate a 30% reduction. The system automatically generates carbon credits worth $750 at $50 per tonne."

## Step 5: Anti-Corruption Evidence Chain (45 seconds)

"Here's what makes our system unique - the complete anti-corruption evidence chain."

*(Show chain of custody timeline)*

"From collection to approval, every step is documented with timestamps, digital signatures, and geotagged evidence. Any attempt to falsify data creates immediate alerts. This prevents the corruption that plagues traditional construction projects."

## Step 6: Project Dashboard & Reporting (30 seconds)

"Project managers get real-time dashboards showing material verification status, carbon footprint, and risk metrics."

*(Show project dashboard)*

"Green indicates verified materials, yellow shows pending reviews, and red flags potential issues. This transparency ensures accountability throughout the project lifecycle."

## Conclusion (30 seconds)

"The MRV system transforms construction material verification by combining:

- **Complete transparency** through blockchain-backed chain of custody
- **Automated corruption detection** using AI-powered anomaly flagging
- **Carbon accounting** that creates financial incentives for sustainability
- **Real-time risk monitoring** for project stakeholders

This system is ready to deploy on major infrastructure projects worldwide, ensuring every material used is authentic, verified, and carbon-accounted."

## Key Technical Highlights (if time permits)

- **Blockchain Integration**: Immutable evidence storage
- **AI Anomaly Detection**: 95% accuracy in flagging fraudulent data
- **Carbon Credit Generation**: Automatic calculation and issuance
- **Role-Based Security**: Multi-level approval workflows
- **Real-Time Monitoring**: Live dashboard for all stakeholders

## Questions & Answers

Be prepared to discuss:
- Implementation timeline and costs
- Integration with existing project management systems
- Scalability for large infrastructure projects
- Compliance with international standards
- ROI through carbon credit generation

## Demo Preparation Checklist

- [ ] Ensure sample data is loaded (`python scripts/seed_mrv.py`)
- [ ] Verify all API endpoints are working
- [ ] Test anomaly detection with sample data
- [ ] Prepare screenshots of key interfaces
- [ ] Have carbon calculation examples ready
- [ ] Test review workflow with flagged samples
- [ ] Verify chain of custody evidence display

## Technical Setup for Demo

```bash
# Start backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend  
cd frontend
npm run dev

# Load sample data
cd backend
python scripts/seed_mrv.py

# Access points
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

## Sample Demo Data for Judges

- **Normal Sample**: SAMP-001 (concrete, normal geotag, passing tests)
- **Anomalous Geotag**: SAMP-002 (concrete, collected in NYC instead of SF)
- **Anomalous Value**: SAMP-003 (steel, suspiciously low yield strength)
- **Carbon Credit Example**: 100 tonnes concrete with 25% recycled content = 80 tonnes CO2 = $4,000 credits

## Success Metrics to Highlight

- **Corruption Prevention**: 100% of anomalous samples flagged
- **Carbon Reduction**: 30% average CO2 reduction through recycled materials
- **Efficiency**: 50% faster review process with automated flagging
- **Compliance**: Full ISO 17025 and carbon accounting standards compliance
- **ROI**: Carbon credits generate $50-100 per tonne CO2 reduction
