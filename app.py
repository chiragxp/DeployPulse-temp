"""
DeployPulse - FastAPI Backend
Handles metrics fetching and comparison with real-time progress streaming
"""

import os
import sys
import json
import logging
import subprocess
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Environment Validation
# ============================================================================
def validate_env_file():
    """Validate that .env file exists before starting the application"""
    env_path = Path(".env")
    if not env_path.exists():
        error_message = (
            "\n" + "=" * 60 + "\n"
            "ERROR: .env file not found!\n"
            "=" * 60 + "\n"
            "The application cannot start without the .env file.\n\n"
            "Required setup steps:\n"
            "  1. Create a .env file in the project root directory\n"
            "  2. Add the following variables to the .env file:\n"
            "     - NEW_RELIC_API_KEY=your_api_key\n"
            "     - NEW_RELIC_ACCOUNT_ID=your_account_id\n"
            "  3. Save the .env file\n"
            "  4. Run the application again:\n"
            "     python3 run.py\n"
            "=" * 60 + "\n"
        )
        logger.error(error_message)
        sys.exit(1)
    logger.info("✓ .env file validation passed")

# Thread pool for blocking I/O operations
executor = ThreadPoolExecutor(max_workers=5)

# Validate environment before initializing FastAPI
validate_env_file()

# Initialize FastAPI
app = FastAPI(title="DeployPulse API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ============================================================================
# Pydantic Models
# ============================================================================

class ExecutionRequest(BaseModel):
    """Request model for metrics execution"""
    environment: str  # DEV, QA, STG, PROD
    event: str        # pre-deploy or post-deploy
    ticket_id: str    # Deployment ID

# ============================================================================
# Helper Functions
# ============================================================================

def run_command(cmd: list) -> tuple[bool, str]:
    """
    Run a shell command and capture output
    Returns: (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out after 10 minutes"
    except Exception as e:
        return False, f"Error running command: {str(e)}"

async def run_command_async(cmd: list) -> tuple[bool, str]:
    """
    Async wrapper for run_command using thread pool
    Prevents blocking the event loop
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, run_command, cmd)

def validate_environment(env: str) -> str:
    """Map frontend environment names to backend format and validate"""
    env_map = {
        "dev": "DEV",
        "qa": "QA",
        "stage": "STG",
        "prod": "PROD"
    }
    
    env_upper = env.upper()
    if env_upper in env_map.values():
        return env_upper
    elif env.lower() in env_map:
        return env_map[env.lower()]
    else:
        raise ValueError(f"Invalid environment: {env}")

def validate_event(event: str) -> str:
    """Validate and normalize event type"""
    event_lower = event.lower()
    if event_lower in ["pre-deploy", "pre-deployment", "pre"]:
        return "pre-deploy"
    elif event_lower in ["post-deploy", "post-deployment", "post"]:
        return "post-deploy"
    else:
        raise ValueError(f"Invalid event: {event}")

def get_snapshot_files(ticket_id: str, environment: str, deployment_tag: str) -> list:
    """
    Get snapshot files matching the pattern
    Returns list of matching file paths
    """
    db_dir = Path("database") / ticket_id
    if not db_dir.exists():
        return []
    
    pattern = f"Snapshot-{ticket_id}-{environment}-{deployment_tag}-*.json"
    matching_files = list(db_dir.glob(pattern))
    return [str(f) for f in matching_files]

def get_pdf_files(ticket_id: str) -> list:
    """Get generated PDF files for a ticket"""
    db_dir = Path("database") / ticket_id
    if not db_dir.exists():
        return []
    
    pdf_files = list(db_dir.glob(f"Deployment-Metrics-Report-{ticket_id}-*.pdf"))
    return [str(f) for f in pdf_files]

# ============================================================================
# Streaming Response for Real-Time Progress
# ============================================================================

async def execute_metrics(environment: str, event: str, ticket_id: str):
    """
    Async generator function to stream progress updates
    Executes fetch_metrics and optionally compare_metrics without blocking
    """
    
    try:
        # Validate inputs
        env = validate_environment(environment)
        evt = validate_event(event)
        
        logger.info(f"Starting execution: {ticket_id} | {env} | {evt}")
        
        yield f"data: {json.dumps({'status': 'info', 'message': 'Validating inputs...'})}\n\n"
        yield f"data: {json.dumps({'status': 'info', 'message': f'Environment: {env}'})}\n\n"
        yield f"data: {json.dumps({'status': 'info', 'message': f'Event: {evt}'})}\n\n"
        yield f"data: {json.dumps({'status': 'info', 'message': f'Ticket ID: {ticket_id}'})}\n\n"
        
        # Step 1: Fetch metrics
        yield f"data: {json.dumps({'status': 'info', 'message': 'Starting metrics collection...'})}\n\n"
        
        fetch_cmd = [
            sys.executable, "fetch_metrics.py",
            ticket_id, env, evt
        ]
        
        logger.info(f"Running: {' '.join(fetch_cmd)}")
        success, output = await run_command_async(fetch_cmd)
        
        if not success:
            logger.error(f"fetch_metrics failed: {output}")
            yield f"data: {json.dumps({'status': 'error', 'message': f'Metrics fetch failed: {output}'})}\n\n"
            return
        
        # Show fetch output
        for line in output.split('\n'):
            if line.strip():
                yield f"data: {json.dumps({'status': 'info', 'message': line.strip()})}\n\n"
        
        yield f"data: {json.dumps({'status': 'success', 'message': '✓ Metrics collected successfully'})}\n\n"
        
        # Step 2: If post-deploy, run comparison
        if evt == "post-deploy":
            yield f"data: {json.dumps({'status': 'info', 'message': 'Starting comparison and report generation...'})}\n\n"
            
            compare_cmd = [sys.executable, "compare_metrics.py", ticket_id]
            
            logger.info(f"Running: {' '.join(compare_cmd)}")
            success, output = await run_command_async(compare_cmd)
            
            if not success:
                logger.error(f"compare_metrics failed: {output}")
                yield f"data: {json.dumps({'status': 'warning', 'message': f'Comparison failed, but metrics were collected: {output}'})}\n\n"
            else:
                # Show comparison output
                for line in output.split('\n'):
                    if line.strip() and 'WARNING' not in line:
                        yield f"data: {json.dumps({'status': 'info', 'message': line.strip()})}\n\n"
                
                yield f"data: {json.dumps({'status': 'success', 'message': '✓ Comparison and report generated successfully'})}\n\n"
        
        # Get files for completion message
        snapshot_files = get_snapshot_files(ticket_id, env, evt)
        pdf_files = get_pdf_files(ticket_id) if evt == "post-deploy" else []
        
        completion_data = {
            'status': 'complete',
            'message': 'Execution completed successfully!',
            'ticket_id': ticket_id,
            'environment': env,
            'event': evt,
            'snapshots': snapshot_files,
            'reports': pdf_files
        }
        
        yield f"data: {json.dumps(completion_data)}\n\n"
        logger.info(f"Execution completed successfully for {ticket_id}")
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        yield f"data: {json.dumps({'status': 'error', 'message': f'Validation error: {str(e)}'})}\n\n"
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__} - {e}")
        yield f"data: {json.dumps({'status': 'error', 'message': f'Unexpected error: {str(e)}'})}\n\n"

# ============================================================================
# API Routes
# ============================================================================

@app.get("/")
async def root():
    """Serve the main page"""
    return FileResponse(Path("static") / "index.html")

@app.get("/api/execute-stream")
async def execute_stream(environment: str, event: str, ticket_id: str):
    """
    Execute metrics with real-time progress streaming
    Uses Server-Sent Events (SSE) for real-time updates
    Accepts parameters as query strings
    """
    
    return StreamingResponse(
        execute_metrics(environment, event, ticket_id),
        media_type="text/event-stream"
    )

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/downloads/{ticket_id}")
async def list_downloads(ticket_id: str):
    """List available downloads for a ticket"""
    try:
        snapshots = get_snapshot_files(ticket_id, "", "")
        pdfs = get_pdf_files(ticket_id)
        
        return {
            "ticket_id": ticket_id,
            "snapshots": snapshots,
            "reports": pdfs
        }
    except OSError as e:
        logger.error(f"Error accessing file system: {e}")
        raise HTTPException(status_code=500, detail="File system error")
    except Exception as e:
        logger.error(f"Unexpected error listing downloads: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/download-file/{file_path:path}")
async def download_file(file_path: str):
    """Download a file from the database"""
    try:
        # If file_path already starts with 'database/', use it directly
        # Otherwise prepend it
        if file_path.startswith("database/"):
            resolved_path = Path(file_path).resolve()
        else:
            resolved_path = (Path("database") / file_path).resolve()
        
        db_path = Path("database").resolve()
        
        # Security: ensure file is within database directory
        if not str(resolved_path).startswith(str(db_path)):
            logger.error(f"Access denied: {resolved_path}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not resolved_path.exists():
            logger.error(f"File not found: {resolved_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        logger.info(f"Downloading file: {resolved_path}")
        return FileResponse(resolved_path)
    except HTTPException:
        raise
    except (OSError, ValueError) as e:
        logger.error(f"File system error accessing file: {e}")
        raise HTTPException(status_code=500, detail="File system error")
    except Exception as e:
        logger.error(f"Unexpected error downloading file: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/logs/{ticket_id}")
async def get_logs(ticket_id: str):
    """Get logs for a specific ticket"""
    try:
        log_file = Path("logs") / f"{ticket_id}.json"
        if not log_file.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
        
        with open(log_file, 'r') as f:
            return json.load(f)
    except HTTPException:
        raise
    except (FileNotFoundError, IOError) as e:
        logger.error(f"Error reading log file: {e}")
        raise HTTPException(status_code=404, detail="Log file not found")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in log file: {e}")
        raise HTTPException(status_code=500, detail="Corrupted log file")
    except Exception as e:
        logger.error(f"Unexpected error reading logs: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
