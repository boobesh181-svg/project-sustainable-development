# Frontend - MRV Dashboard

React + Vite + Tailwind CSS dashboard for the Sustainable Construction MRV System.

## Features

- **Real-time Dashboard**: KPI cards, trends, and aggregations
- **MRV Workflow**: View and manage MRV reports with state machine visualization
- **Anomaly Detection**: Real-time anomaly alerts with severity levels
- **Audit Trail**: Immutable append-only log with hash chain verification
- **Responsive Design**: Mobile-friendly layout with Tailwind CSS
- **API Integration**: Typed API client for backend communication

## Structure

```
src/
├── api/           # API client for backend communication
├── layout/        # Layout components (Sidebar, Topbar)
├── pages/         # Page components (Dashboard, MRV, Anomalies, Audit)
├── components/    # Reusable UI components
├── charts/        # Chart components (CO2Trend, AnomalyBar)
├── styles/        # Global CSS and Tailwind setup
├── App.jsx        # Main application component
└── main.jsx       # Entry point
```

## Getting Started

### Prerequisites

- Node.js 16+
- npm or yarn

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Navigate to `http://localhost:5173`

### Build for Production

```bash
npm run build
npm run preview
```

## API Configuration

Set the backend URL via environment variable:

```bash
# Recommended for dev: do NOT set VITE_API_URL; use Vite proxy via relative /api
npm run dev

# If you set VITE_API_URL=http://localhost:8000, it will only work on this machine.
# When opening the UI via the Vite "Network" URL from another device, "localhost" refers
# to that device, not your PC.
```

Or edit `src/api/client.js` to change the default API_BASE.

## Pages

### Dashboard
- Real-time KPI metrics
- CO₂ trend chart
- Anomaly timeline
- MRV workflow status
- Material token statistics

### MRV Reports
- List of all MRV reports
- Status workflow visualization
- Report approval rate
- Immutability enforcement

### Anomalies
- Detected anomalies by severity (HIGH/MEDIUM/LOW)
- Real-time anomaly rules:
  - Excess Quantity Detection
  - Distance Anomaly Detection
  - Duplicate Photo Detection
  - Suspicious Supplier Detection

### Audit Trail
- Append-only immutable log
- Hash chain verification
- All critical actions logged:
  - TOKEN_ISSUED, TOKEN_REDEEMED
  - DELIVERY_VERIFIED, DELIVERY_APPROVED
  - MRV_CREATED, MRV_SUBMITTED, MRV_VERIFIED, MRV_APPROVED, MRV_LOCKED
  - ANOMALY_DETECTED

## Components

### KPICard
Displays a single KPI metric with icon and optional secondary text.

### Loading
Loading spinner displayed while fetching data.

### CO2Trend
Stacked bar chart showing embodied, operational, and saved CO₂ over time.

### AnomalyBar
Horizontal bar chart showing anomaly counts per date.

## Features

✅ **ISO-14064 Compliant**  
✅ **Real-time Updates**  
✅ **Immutability Visualization**  
✅ **Responsive Design**  
✅ **Accessibility First**  

## License

Proprietary - Sustainable Construction Project
