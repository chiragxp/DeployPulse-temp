import argparse
import requests
import json
import time
import os
import logging
from datetime import datetime
from collections import OrderedDict
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
try:
    load_dotenv()
    logger.debug("Environment variables loaded from .env file")
except Exception as e:
    logger.warning(f"Could not load .env file: {e}")

# Validate and load configuration constants
def validate_environment_variables():
    """Validate that all required environment variables are set"""
    api_key = os.getenv("NEW_RELIC_API_KEY")
    account_id_str = os.getenv("NEW_RELIC_ACCOUNT_ID")

    if not api_key:
        logger.error("ERROR: NEW_RELIC_API_KEY environment variable is not set")
        logger.error("Please set NEW_RELIC_API_KEY in your .env file or as an environment variable")
        return None, None

    if not account_id_str:
        logger.error("ERROR: NEW_RELIC_ACCOUNT_ID environment variable is not set")
        logger.error("Please set NEW_RELIC_ACCOUNT_ID in your .env file or as an environment variable")
        return None, None

    try:
        account_id = int(account_id_str)
    except (ValueError, TypeError) as e:
        logger.error(f"ERROR: NEW_RELIC_ACCOUNT_ID must be a valid integer, got: {account_id_str}")
        logger.error(f"Conversion error: {e}")
        return None, None

    logger.debug(f"Environment variables validated successfully")
    return api_key, account_id

API_KEY, ACCOUNT_ID = validate_environment_variables()
if API_KEY is None or ACCOUNT_ID is None:
    logger.error("\nFATAL ERROR: Required environment variables are missing or invalid.")
    logger.error("Exiting application.\n")
    exit(1)

HEADERS = {"Api-Key": API_KEY, "Content-Type": "application/json"}

# Query and retry configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_SLEEP_TIME = 2  # seconds
BETWEEN_QUERY_SLEEP = 0  # Parallel requests don't need sleep between queries
TIME_WINDOW = "5 minutes ago"
QUERY_LIMIT = 100
APDEX_THRESHOLD = 0.5  # seconds - threshold for satisfactory response time
ERROR_RATE_MULTIPLIER = 100  # convert to percentage
MAX_WORKERS = 5  # Number of concurrent threads for API calls (reduced for rate limiting)
API_CALL_SEMAPHORE = threading.Semaphore(3)  # Limit concurrent API calls to 3

grouped_apms = OrderedDict([
    ("DEV", OrderedDict([
        ("Author", ["jhinv-dev65-author"]),
        ("Publisher", ["jhinv-dev65-publish"])
    ])),
    ("QA", OrderedDict([
        ("Author", ["jhinv-qa65-author"]),
        ("Publisher", ["jhinv-qa65-publish"])
    ])),
    ("STG", OrderedDict([
        ("Author", ["jhinv-stg65-author"]),
        ("Publisher", ["jhinv-stg65-publish"])
    ])),
    ("PROD", OrderedDict([
        ("Author", ["jhinv-prod65-author"]),
        ("Publisher", ["jhinv-prod65-publish"])
    ])),
])

grouped_hosts = OrderedDict([
    ("DEV", OrderedDict([
        ("Author", ["jhinv-dev65-author1useast1-28524823"]),
        # ("Dispatcher", ["jhinv-dev65-dispatcher1useast1-28524823"]),
        ("Publisher", ["jhinv-dev65-publish1useast1-28524823"])
    ])),
    ("QA", OrderedDict([
        ("Author", ["jhinv-qa65-author1useast1-28576614"]),
        # ("Dispatcher", [
        #     "jhinv-qa65-dispatcher1useast1-28576614",
        #     "jhinv-qa65-dispatcher2useast1-28578312"
        # ]),
        ("Publisher", [
            "jhinv-qa65-publish1useast1-28576614",
            "jhinv-qa65-publish2useast1-28578312"
        ])
    ])),
    ("STG", OrderedDict([
        ("Author", [
            "jhinv-stg65-author1useast1-28599991",
            "jhinv-stg65-author1useast1-2standby"
        ]),
        # ("Dispatcher", [
        #     "jhinv-stg65-dispatcher1useast1-28599991",
        #     "jhinv-stg65-dispatcher1uswest2-28604004",
        #     "jhinv-stg65-dispatcher2useast1-28604004",
        #     "jhinv-stg65-dispatcher2uswest2-28604004"
        # ]),
        ("Publisher", [
            "jhinv-stg65-publish1useast1-28599991",
            "jhinv-stg65-publish1uswest2-28604004",
            "jhinv-stg65-publish2useast1-28604004",
            "jhinv-stg65-publish2uswest2-28604004"
        ])
    ])),
    ("PROD", OrderedDict([
        ("Author", [
            "jhinv-prod65-author1useast1-b80",
            "jhinv-prod65-author1useast1-b80-2standby"
        ]),
        # ("Dispatcher", [
        #     "jhinv-prod65-dispatcher1useast1-b80",
        #     "jhinv-prod65-dispatcher1uswest2-b80",
        #     "jhinv-prod65-dispatcher2useast1-b80",
        #     "jhinv-prod65-dispatcher2uswest2-b80"
        # ]),
        ("Publisher", [
            "jhinv-prod65-publish1useast1-b80",
            "jhinv-prod65-publish1uswest2-b80",
            "jhinv-prod65-publish2useast1-b80",
            "jhinv-prod65-publish2uswest2-b80"
        ])
    ])),
])


def invoke_nrql_query(nrql: str) -> float | None:

    query = {
        "query": (
            f'{{actor{{account(id:{ACCOUNT_ID}){{nrql(query:"{nrql}"){{results}}}}}}}}'
        )
    }
    json_body = json.dumps(query, separators=(',', ':'))

    attempt = 0
    while attempt < MAX_RETRY_ATTEMPTS:
        try:
            # Rate limiting: Use semaphore to prevent overwhelming New Relic API
            acquired = API_CALL_SEMAPHORE.acquire(timeout=5)
            if not acquired:
                logger.warning(f"Rate limit semaphore timeout (attempt {attempt+1}), retrying...")
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_SLEEP_TIME)
                attempt += 1
                continue
            
            try:
                response = requests.post(
                    "https://api.newrelic.com/graphql",
                    headers=HEADERS,
                    data=json_body,
                    timeout=30
                )
                response.raise_for_status()  # Raise exception for bad HTTP status
                resp_json = response.json()

                logger.debug(f"Query: {query}")
                logger.debug(f"Response: {resp_json}")

                if 'errors' in resp_json:
                    error_msg = json.dumps(resp_json['errors'])
                    logger.warning(f"GraphQL error (attempt {attempt+1}): {error_msg}")
                    if "NRDB:1109" in error_msg:  # Rate limit error
                        time.sleep(RETRY_SLEEP_TIME)
                        attempt += 1
                        continue
                    logger.error(f"Non-retryable GraphQL error: {error_msg}")
                    return None

                results = resp_json.get('data', {}).get('actor', {}).get('account', {}).get('nrql', {}).get('results', [])
                if results and isinstance(results[0], dict) and results[0]:
                    first_key = list(results[0].keys())[0]
                    val = results[0][first_key]
                    if first_key.startswith("apdex") and isinstance(val, dict) and "score" in val:
                        return val["score"]
                    else:
                        return val
                else:
                    logger.warning(f"No results from query (attempt {attempt+1})")
                    return None
            except requests.exceptions.Timeout as e:
                logger.error(f"Request timeout (attempt {attempt+1}): {e}")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error (attempt {attempt+1}): {e}")
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error (attempt {attempt+1}): {e}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (attempt {attempt+1}): {e}")
            finally:
                # Always release semaphore to prevent deadlock
                API_CALL_SEMAPHORE.release()
        except Exception as e:
            logger.error(f"Unexpected error with rate limiting (attempt {attempt+1}): {type(e).__name__} - {e}")

        if attempt < MAX_RETRY_ATTEMPTS - 1:
            time.sleep(RETRY_SLEEP_TIME)
        attempt += 1

    logger.error(f"Failed to fetch metric after {MAX_RETRY_ATTEMPTS} attempts")
    return None

def get_apm_metrics(app_name: str) -> dict:

    metric_results = {}

    queries = {
        "Apdex": f"SELECT apdex(duration, t:{APDEX_THRESHOLD}) FROM Transaction WHERE appName = '{app_name}' SINCE {TIME_WINDOW} LIMIT {QUERY_LIMIT}",
        "ResponseTime": f"SELECT average(duration) FROM Transaction WHERE appName = '{app_name}' SINCE {TIME_WINDOW} LIMIT {QUERY_LIMIT}",
        "ErrorRate": f"SELECT sum(apm.service.error.count['count']) / count(apm.service.transaction.duration) * {ERROR_RATE_MULTIPLIER} FROM Metric WHERE appName = '{app_name}' SINCE {TIME_WINDOW}",
        "Throughput": f"SELECT rate(count(*), 1 minute) FROM Transaction WHERE appName = '{app_name}' SINCE {TIME_WINDOW} LIMIT {QUERY_LIMIT}"
    }

    # Execute all queries in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_metric = {
            executor.submit(invoke_nrql_query, nrql): metric 
            for metric, nrql in queries.items()
        }
        
        for future in as_completed(future_to_metric):
            metric = future_to_metric[future]
            try:
                value = future.result()
                if value is not None:
                    metric_results[metric] = round(float(value), 3)
                else:
                    logger.warning(f"Could not fetch {metric} for '{app_name}' - setting to N/A")
                    metric_results[metric] = "N/A"
            except (TypeError, ValueError) as e:
                logger.error(f"Error converting {metric} value to float for '{app_name}': {e}")
                metric_results[metric] = "N/A"
            except Exception as e:
                logger.error(f"Error fetching {metric} for '{app_name}': {e}")
                metric_results[metric] = "N/A"
    
    return metric_results

def get_host_metrics(hostname: str) -> dict:

    results = {}

    queries = {
        "CPU_Usage": f"SELECT average(cpuPercent) FROM SystemSample WHERE hostname = '{hostname}' SINCE {TIME_WINDOW} LIMIT {QUERY_LIMIT}",
        "Memory_Usage": f"SELECT average(memoryUsedBytes/memoryTotalBytes) * {ERROR_RATE_MULTIPLIER} FROM SystemSample WHERE hostname = '{hostname}' SINCE {TIME_WINDOW} LIMIT {QUERY_LIMIT}",
        "Disk_Usage": f"SELECT average(diskUsedPercent) FROM StorageSample WHERE hostname = '{hostname}' SINCE {TIME_WINDOW} LIMIT {QUERY_LIMIT}"
    }

    # Execute all queries in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_metric = {
            executor.submit(invoke_nrql_query, nrql): metric 
            for metric, nrql in queries.items()
        }
        
        for future in as_completed(future_to_metric):
            metric = future_to_metric[future]
            try:
                value = future.result()
                if value is not None:
                    results[metric] = round(float(value), 2)
                else:
                    logger.warning(f"Could not fetch {metric} for host '{hostname}' - setting to N/A")
                    results[metric] = "N/A"
            except (TypeError, ValueError) as e:
                logger.error(f"Error converting {metric} value to float for host '{hostname}': {e}")
                results[metric] = "N/A"
            except Exception as e:
                logger.error(f"Error fetching {metric} for host '{hostname}': {e}")
                results[metric] = "N/A"
    
    return results

def ensure_directories_exist(path: str) -> bool:

    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ensured: {path}")
        return True
    except PermissionError as e:
        logger.error(f"Permission denied when creating directory '{path}': {e}")
        return False
    except OSError as e:
        logger.error(f"OS error when creating directory '{path}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error when creating directory '{path}': {type(e).__name__} - {e}")
        return False

def update_log_file(deployment_id: str, environment: str, snapshot_path: str, deployment_tag: str) -> bool:

    logs_dir = "logs"

    # Ensure logs directory exists
    if not ensure_directories_exist(logs_dir):
        logger.error(f"Failed to create logs directory, cannot update log file")
        return False

    log_file = os.path.join(logs_dir, f"{deployment_id}.json")

    try:
        # Load existing log data or create new
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.warning(f"Log file {log_file} is corrupted, starting fresh: {e}")
                log_data = {}
        else:
            log_data = {}

        # Initialize deployment entry if not exists
        if deployment_id not in log_data:
            log_data[deployment_id] = {
                "environment": environment.upper(),
                "pre_snapshot": None,
                "post_snapshot": None
            }

        # Update based on deployment tag
        if deployment_tag == "pre-deploy":
            log_data[deployment_id]["pre_snapshot"] = snapshot_path
        elif deployment_tag == "post-deploy":
            log_data[deployment_id]["post_snapshot"] = snapshot_path
        else:
            logger.warning(f"Unknown deployment tag: {deployment_tag}")
            return False

        # Save updated log data
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Log file updated: {log_file}")
        return True
    except FileNotFoundError as e:
        logger.error(f"Log file not found and could not be created {log_file}: {e}")
        return False
    except IOError as e:
        logger.error(f"IO error when updating log file {log_file}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error updating log file {log_file}: {type(e).__name__} - {e}")
        return False

def main():
    try:
        parser = argparse.ArgumentParser(description='Fetch deployment metrics and optionally compare snapshots.')
        parser.add_argument('deployment_id', type=str, help='Deployment ID (e.g., CHG01250744)')
        parser.add_argument('environment', type=str, choices=['DEV', 'QA', 'STG', 'PROD'], help='Environment name: DEV, QA, STG, or PROD')
        parser.add_argument('deployment_tag', type=str, choices=['pre-deploy', 'post-deploy'], help='Deployment stage: pre-deploy or post-deploy')
        args = parser.parse_args()

        deployment_id = args.deployment_id
        deployment_tag = args.deployment_tag
        env_selected = args.environment

        logger.info(f"Starting metrics fetch for deployment: {deployment_id}")
        logger.info(f"Environment: {env_selected}, Tag: {deployment_tag}")
        timestamp = datetime.now().strftime('%Y%m%d-%H%M')

        # Prepare all fetch tasks for parallel execution
        fetch_tasks = []
        apm_task_map = {}
        host_task_map = {}

        # Fetch APM metrics
        logger.info(f"Fetching APM metrics...")
        apm_results = {env_selected: {}}
        runmodes = grouped_apms[env_selected]
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for runmode, apms in runmodes.items():
                apm_results[env_selected][runmode] = {}
                for apm in apms:
                    logger.info(f"Queuing APM metrics - [{env_selected}][{runmode}] - {apm}")
                    future = executor.submit(get_apm_metrics, apm)
                    apm_task_map[future] = (runmode, apm)
            
            # Collect results as they complete
            for future in as_completed(apm_task_map):
                runmode, apm = apm_task_map[future]
                try:
                    result = future.result()
                    apm_results[env_selected][runmode][apm] = result
                except Exception as e:
                    logger.error(f"Error fetching APM metrics for {apm}: {e}")
                    apm_results[env_selected][runmode][apm] = {
                        "Apdex": "N/A", "ResponseTime": "N/A", 
                        "ErrorRate": "N/A", "Throughput": "N/A"
                    }

        # Fetch Host metrics
        logger.info(f"Fetching host metrics...")
        host_results = {env_selected: {}}
        roles = grouped_hosts[env_selected]
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for role, hosts in roles.items():
                host_results[env_selected][role] = {}
                for hn in hosts:
                    logger.info(f"Queuing host metrics - [{env_selected}][{role}] - {hn}")
                    future = executor.submit(get_host_metrics, hn)
                    host_task_map[future] = (role, hn)
            
            # Collect results as they complete
            for future in as_completed(host_task_map):
                role, hn = host_task_map[future]
                try:
                    result = future.result()
                    host_results[env_selected][role][hn] = result
                except Exception as e:
                    logger.error(f"Error fetching host metrics for {hn}: {e}")
                    host_results[env_selected][role][hn] = {
                        "CPU_Usage": "N/A", "Memory_Usage": "N/A", "Disk_Usage": "N/A"
                    }

        final_results = {"apmMetrics": apm_results, "hostMetrics": host_results}

        # Create folder structure: database/{deployment_id}
        snapshot_dir = os.path.join("database", deployment_id)
        if not ensure_directories_exist(snapshot_dir):
            logger.error(f"Failed to create snapshot directory: {snapshot_dir}")
            logger.error("Cannot proceed without directory. Exiting.")
            return False

        filename = f"Snapshot-{deployment_id}-{env_selected}-{deployment_tag}-{timestamp}.json"
        filepath = os.path.join(snapshot_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, ensure_ascii=False, indent=2)
            logger.info(f"Snapshot saved as: {filepath}")
        except IOError as e:
            logger.error(f"Failed to write snapshot file {filepath}: {e}")
            logger.error("Cannot proceed without saving snapshot. Exiting.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing snapshot file {filepath}: {type(e).__name__} - {e}")
            return False

        # Update log file with metadata
        relative_path = os.path.join("database", deployment_id, filename)
        if not update_log_file(deployment_id, env_selected, relative_path, deployment_tag):
            logger.warning(f"Failed to update log file for {deployment_id}, but snapshot was saved")

        logger.info(f"Metrics fetch completed successfully for deployment: {deployment_id}")
        return True

    except KeyError as e:
        logger.error(f"Configuration error: Missing key {e}")
        logger.error(f"Ensure environment '{env_selected}' is properly configured")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during metrics fetch: {type(e).__name__} - {e}")
        logger.error("Deployment metrics fetch failed. Please check logs for details.")
        return False

if __name__ == '__main__':
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nExecution cancelled by user")
        exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {type(e).__name__} - {e}")
        exit(1)
