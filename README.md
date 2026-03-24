# DeployPulse

A modern web-based application for generating comprehensive deployment impact reports with real-time metrics analysis and AI-powered insights.

## Overview

DeployPulse is an intelligent deployment monitoring and analysis tool that fetches metrics from New Relic before and after deployments, compares performance data, and generates detailed impact reports enhanced with AI-powered analysis and visualizations.

### Key Features

- 🚀 **Real-time Metrics Fetching**: Automatically retrieves performance metrics from New Relic API
- 📊 **Comprehensive Comparison**: Analyzes pre-deployment vs post-deployment metrics
- 🤖 **AI-Powered Insights**: Generates intelligent analysis and recommendations using AI endpoints
- 📈 **Visual Reports**: Creates publication-ready PDF reports with charts and graphs
- 🌐 **Web Interface**: User-friendly dashboard for easy deployment analysis
- 📝 **Detailed Logging**: Comprehensive logs for troubleshooting

## Prerequisites

Before you begin, ensure you have the following:

- **Python 3.12 or higher**: [Download Python](https://www.python.org/downloads/)
- **pip**: Python package manager (included with Python)
- **New Relic Account**: With API access (Account ID and API Key required)
- **AI Endpoint**: For generating AI-powered insights (URL required)

### Verify Prerequisites

```bash
python3 --version
pip3 --version
```

## Installation & Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/chiragxp/DeployPulse-temp.git
```

### Step 2: Create Environment Variables

Create a `.env` file in the project root directory:

```bash
touch .env
```

Add the following variables to the `.env` file:

```
NEW_RELIC_API_KEY=your_new_relic_api_key
NEW_RELIC_ACCOUNT_ID=your_new_relic_account_id
AI_ENDPOINT=your_ai_endpoint_url
```

**Required variables:**

- `NEW_RELIC_API_KEY`: Your New Relic API authentication key
- `NEW_RELIC_ACCOUNT_ID`: Your New Relic account identifier
- `AI_ENDPOINT`: URL to your AI analysis endpoint

### Step 3: Quick Start the Application

```bash
python3 run.py
```

This command will:

- ✓ Verify Python version (3.8+)
- ✓ Create/activate virtual environment
- ✓ Install all dependencies
- ✓ Validate project structure
- ✓ Check for `.env` file
- ✓ Start FastAPI server on `http://localhost:8000`
- ✓ Automatically open the web interface

## Usage

### Web Interface

1. Open your browser and navigate to `http://localhost:8000`
2. Before Deployment:
   - **Environment**: Select the target environment (PROD, STG, etc.)
   - **Event**: Select the deployment event as Pre-Deployment
   - **Deployment ID**: Enter Ticket Number for the deployment
3. Click "Submit" to fetch and store metrics as pre-deployment data. You will be redirected to a new screen.
4. On the new screen, you will see real-time progress of data fetching. Once completed, the json snapshot is stored in database folder. If required, it can be downloaded by clicking on the filename. Once ready, click "Back to Form" button to go back to the main screen.
5. Deployment Happens
6. After Deployment:
   - **Environment**: Select the same target environment (PROD, STG, etc.)(Must be the same env as Pre-Deployment)
   - **Event**: Select the deployment event as Post-Deployment
   - **Deployment ID**: Enter Ticket Number for the deployment (Must be the same env as Pre-Deployment)
7. Click "Submit" to fetch and store metrics as post-deployment data, you will be redirected to a new screen
8. This time the application will not only fetch and store the metrics, but it will also perform a comparison, sent the data to AI for generating a summary based on the comparison, generate comparison charts, and put it all together in a final PDF report that is stored ni database folder, as well as available to download on the redirected screen.
9. Download the generated PDF report with insights for review

### Command Line Interface (Advanced)

For advanced usage, you can run individual scripts:

#### Fetch Metrics Only

For fetching the metrics before the deployment

```bash
python3 fetch_metrics.py --deployment-id TEST001 --environment PROD --deployment-event pre-deploy
```

For fetching the metrics after the deployment

```bash
python3 fetch_metrics.py --deployment-id TEST001 --environment PROD --deployment-event post-deploy
```

#### Compare Metrics & Generate Report

Once pre and post deployment metrics are fetched, you can perform a comparison and generate a PDF report by running the compare-metrics.py script

```bash
python3 compare_metrics.py --deployment-id TEST001
```

## Project Structure

```
DeployPulse/
├── app.py                      # FastAPI backend application
├── run.py                      # Automated startup script
├── fetch_metrics.py            # New Relic metrics fetcher
├── compare_metrics.py          # Metrics comparison & report generator
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── database/                   # Deployment snapshots and comparisons
│   ├── PROD001/
│   └── TEST001/
├── logs/                       # Application logs
│   ├── PROD001.json
│   ├── TEST001.json
├── prompts/                    # AI prompt configurations
└── static/                     # Web interface files
    ├── index.html              # Frontend HTML
    ├── script.js               # Frontend JavaScript
    └── style.css               # Frontend styling
```

## File Descriptions

- **app.py**: FastAPI backend that serves the web interface, handles API requests, and manages metric processing with real-time streaming
- **fetch_metrics.py**: Retrieves pre- and post-deployment metrics from New Relic API using parallel requests
- **compare_metrics.py**: Compares metrics, generates PDF reports with visualizations, and integrates AI insights
- **run.py**: Automated setup and startup script that handles environment validation and server initialization
- **database/**: Stores snapshot data (pre/post-deployment metrics) and comparison results organized by deployment ID
- **logs/**: JSON logs for each deployment containing execution details and timestamps

## Output Files

After running a deployment analysis, the following files are generated and stored in database/deployment_ID folder:

- **Snapshot-{ID}-{ENV}-pre-deploy-{TIMESTAMP}.json**: Pre-deployment metrics snapshot
- **Snapshot-{ID}-{ENV}-post-deploy-{TIMESTAMP}.json**: Post-deployment metrics snapshot
- **comparison-{ID}-{TIMESTAMP}.json**: Detailed comparison results
- **ai-response-{ID}-{TIMESTAMP}.json**: AI-generated insights and recommendations
- **PDF Report**: Publication-ready report with visualizations (view in web interface)

## API Endpoints

### Core Endpoints

- `GET /` - Web interface dashboard
- `POST /generate-report` - Submit deployment for analysis with real-time streaming
- `GET /download/{filename}` - Download generated reports

## Dependencies

- **FastAPI** (0.109.0): Modern web framework for building APIs
- **Uvicorn** (0.27.0): ASGI server for running FastAPI
- **Requests** (2.32.5): HTTP client for API calls
- **python-dotenv** (1.2.1): Environment variable management
- **ReportLab** (4.4.9): PDF generation library
- **Matplotlib** (3.9.4): Data visualization
- **python-multipart** (0.0.6): Form data parsing

## Configuration

### Environment Variables

All configuration is managed through the `.env` file:

```
# New Relic Configuration
NEW_RELIC_API_KEY=your_api_key_here
NEW_RELIC_ACCOUNT_ID=your_account_id_here

# AI Integration
AI_ENDPOINT=your_ai_endpoint_url_here
```

### Application Settings

Default settings in the application:

- **Server Host**: localhost (127.0.0.1)
- **Server Port**: 8000
- **Timeout**: Configurable per request
- **Concurrent Requests**: Optimized thread pool for parallel metric fetching

## Troubleshooting

### Issue: `.env file not found`

**Solution**: Create the `.env` file in the project root directory with the required credentials

```bash
touch .env
# Then add the required environment variables
```

### Issue: `NEW Relic API errors`

**Solution**: Verify your API key and Account ID are correct and have proper permissions

```bash
# Check if credentials are loaded
echo $NEW_RELIC_API_KEY
echo $NEW_RELIC_ACCOUNT_ID
```

### Issue: Port 8000 already in use

**Solution**: Either stop the process using port 8000 or modify the port in `app.py`:

```python
# In app.py, find the uvicorn.run() call and change the port
uvicorn.run(app, host="127.0.0.1", port=8001)
```

### Issue: Virtual environment not activating

**Solution**: The `run.py` script handles this automatically, but you can manually activate it:

```bash
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

## Development

### Running in Development Mode

For development with auto-reload:

```bash
pip3 install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

## License

## This project is licensed under the MIT License - see the LICENSE file for details.

**Last Updated**: March 4, 2026

**Maintained by**: Common Capabilities, Shared Services & Platform
