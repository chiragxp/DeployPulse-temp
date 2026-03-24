# Running DeployPulse via Docker

This guide provides platform-specific instructions for running the DeployPulse application using Docker.

## ⚠️ Important: Set Your Environment Variables

Before running the application, you'll need to provide your own credentials in the `.env` file:

- **`NEW_RELIC_API_KEY`** — Your New Relic API key (obtain from New Relic account)
- **`NEW_RELIC_ACCOUNT_ID`** — Your New Relic account ID
- **`AI_ENDPOINT`** — Your AI/GWAM endpoint URL

Do **NOT** commit the `.env` file to Git as it contains sensitive credentials.

## Mac Setup Instructions

### Mac Prerequisites

- Docker Desktop for Mac installed
- Docker Compose installed (comes with Docker Desktop)
- Terminal (Bash or Zsh)

### Mac Quick Start

After cloning the repository, run:

```bash
mkdir -p database logs && chmod 777 database logs && cat > .env << 'EOF'
NEW_RELIC_API_KEY=<your-api-key>
NEW_RELIC_ACCOUNT_ID=<your-account-id>
AI_ENDPOINT=<your-ai-endpoint>
EOF
docker-compose build && docker-compose up
```

### Mac Step-by-Step Instructions

**Step 1: Clone the Repository**

```bash
git clone <repo-url>
cd DeployPulse-temp
```

**Step 2: Create the `.env` File**

Create a `.env` file in the project root with the required environment variables:

```bash
cat > .env << EOF
NEW_RELIC_API_KEY=<your-api-key>
NEW_RELIC_ACCOUNT_ID=<your-account-id>
AI_ENDPOINT=<your-ai-endpoint>
EOF
```

**OR** manually create `.env` in the project root and add:

```
NEW_RELIC_API_KEY=<your-api-key>
NEW_RELIC_ACCOUNT_ID=<your-account-id>
AI_ENDPOINT=<your-ai-endpoint>
```

**Step 3: Create Required Directories with Proper Permissions**

```bash
mkdir -p database logs
chmod 777 database logs
```

These directories are used by the application to store deployment metrics and logs.

**Step 4: Build the Docker Image**

```bash
docker-compose build
```

**Step 5: Run the Application**

```bash
docker-compose up
```

The application will start on `http://localhost:8000`

**Step 6: Access the Application**

Open your browser and navigate to: `http://localhost:8000`

### Mac-Specific Notes

- The `chmod 777` command is necessary to ensure proper read/write permissions for the mounted volumes
- Docker Desktop on Mac runs Linux in a lightweight VM, so volume permissions are automatically handled by Docker
- Use `Cmd+C` in Terminal to stop the container gracefully

## Windows Setup Instructions

If you're running on **Windows**, follow these steps instead:

### Windows Prerequisites

- Docker Desktop for Windows installed
- PowerShell or Command Prompt
- Git for Windows (for cloning the repository)

### Windows Quick Start

After cloning the repository, run this in PowerShell:

```powershell
mkdir database; mkdir logs; @"
NEW_RELIC_API_KEY=<your-api-key>
NEW_RELIC_ACCOUNT_ID=<your-account-id>
AI_ENDPOINT=<your-ai-endpoint>
"@ | Out-File -Encoding UTF8 .env; docker-compose build; docker-compose up
```

### Windows Step-by-Step Instructions

**Step 1: Clone the Repository**

```powershell
git clone <repo-url>
cd DeployPulse-temp
```

**Step 2: Create the `.env` File (PowerShell)**

```powershell
@"
NEW_RELIC_API_KEY=<your-api-key>
NEW_RELIC_ACCOUNT_ID=<your-account-id>
AI_ENDPOINT=<your-ai-endpoint>
"@ | Out-File -Encoding UTF8 .env
```

**OR** manually create the file using Notepad:

1. Right-click in the project folder → New → Text Document
2. Name it `.env`
3. Add the environment variables
4. Save

**Step 3: Create Required Directories**

Using PowerShell:

```powershell
mkdir database
mkdir logs
```

**Note:** Windows handles directory permissions automatically through Docker Desktop, so `chmod` is not needed.

**Step 4: Build and Run**

```powershell
docker-compose build
docker-compose up
```

**Step 5: Access the Application**

Open your browser and go to: `http://localhost:8000`

### Windows-Specific Notes

- PowerShell is recommended; Command Prompt may have issues with multi-line commands
- Make sure Docker Desktop is running before executing `docker-compose` commands
- If you see `docker-compose: command not found`, restart PowerShell or your terminal
- Windows Line Endings (CRLF): Ensure `.env` uses proper formatting (UTF-8 without BOM)

## Common Commands (Mac & Windows)

The following commands work on both Mac and Windows once Docker is set up:

### Stopping the Application

To stop the Docker container:

```bash
docker-compose down
```

### Running in Background

To run the application in the background (detached mode):

```bash
docker-compose up -d
```

To view logs in detached mode:

```bash
docker-compose logs -f
```

### Rebuilding After Code Changes

If you make changes to the code and want to rebuild:

```bash
docker-compose build --no-cache
docker-compose up
```

## Troubleshooting

### Permission Denied Error

If you get a "Permission denied" error when creating directories, ensure the `database` and `logs` directories have proper permissions:

```bash
chmod 777 database logs
```

### Port Already in Use

If port 8000 is already in use, you can modify the port mapping in `docker-compose.yml`:

```yaml
ports:
  - '8001:8000' # Changes external port to 8001
```

Then access the app at `http://localhost:8001`

### Viewing Container Logs

To see detailed logs from the running container:

```bash
docker-compose logs
```

For continuous log streaming:

```bash
docker-compose logs -f
```

## Environment Variables

The application requires three environment variables (defined in `.env`):

| Variable               | Description                                  |
| ---------------------- | -------------------------------------------- |
| `NEW_RELIC_API_KEY`    | New Relic API key for metrics fetching       |
| `NEW_RELIC_ACCOUNT_ID` | New Relic account ID                         |
| `AI_ENDPOINT`          | Endpoint for AI/GWAM metrics summary service |

## Project Structure

After running, your project will have:

```
.
├── database/          # Mounted volume for deployment snapshots
├── logs/              # Mounted volume for application logs
├── .env              # Environment variables (not in git)
├── Dockerfile        # Docker image definition
├── docker-compose.yml # Docker Compose configuration
└── ... (other app files)
```

Data in `database/` and `logs/` persists between container restarts.
