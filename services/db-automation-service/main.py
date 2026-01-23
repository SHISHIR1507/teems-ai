import psycopg
import os
import logging
import re
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

# Configure logging (goes to CloudWatch automatically in ECS)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
# Support DATABASE_URL format: postgresql://user:pass@host:port/dbname
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Parse DATABASE_URL if provided, otherwise use individual params
if DATABASE_URL:
    # Remove asyncpg driver prefix if present (postgresql+asyncpg:// -> postgresql://)
    clean_url = re.sub(r'postgresql\+\w+://', 'postgresql://', DATABASE_URL)
    parsed = urlparse(clean_url)
    DB_HOST = parsed.hostname
    DB_PORT = str(parsed.port or 5432)
    DB_NAME = parsed.path.lstrip('/')
    DB_USER = parsed.username
    DB_PASSWORD = parsed.password
else:
    DB_HOST = os.environ.get("DB_HOST")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME")
    DB_USER = os.environ.get("DB_USER")
    DB_PASSWORD = os.environ.get("DB_PASSWORD")

IDLE_THRESHOLD_MINUTES = int(os.environ.get("IDLE_THRESHOLD_MINUTES", "10"))
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "5"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
EXCLUDED_USERS = os.environ.get("EXCLUDED_USERS", "rdsadmin").split(",")


def terminate_idle_connections():
    """Find and terminate idle database connections."""
    logger.info(f"Starting idle connection check (threshold: {IDLE_THRESHOLD_MINUTES} min)...")
    
    try:
        # Build connection string
        conn_string = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"
        conn = psycopg.connect(conn_string, autocommit=True)
        cur = conn.cursor()

        # Build excluded users list for SQL
        excluded_users_str = ",".join([f"'{u.strip()}'" for u in EXCLUDED_USERS])

        if DRY_RUN:
            # Dry run: just show what WOULD be terminated
            # Include both 'idle' and 'idle in transaction' states (per manager feedback)
            cur.execute(f"""
                SELECT pid, usename, application_name, state, 
                       ROUND(EXTRACT(EPOCH FROM (now() - state_change))/60, 1) as idle_minutes
                FROM pg_stat_activity 
                WHERE state IN ('idle', 'idle in transaction') 
                  AND state_change < now() - interval '{IDLE_THRESHOLD_MINUTES} minutes'
                  AND pid <> pg_backend_pid()
                  AND usename NOT IN ({excluded_users_str});
            """)
            idle_connections = cur.fetchall()
            
            if idle_connections:
                logger.info(f"[DRY RUN] Would terminate {len(idle_connections)} connections:")
                for row in idle_connections:
                    logger.info(f"  - PID: {row[0]}, User: {row[1]}, App: {row[2]}, Idle: {row[4]} min")
            else:
                logger.info("[DRY RUN] No idle connections to terminate")
        else:
            # Production: actually terminate
            # Include both 'idle' and 'idle in transaction' states (per manager feedback)
            cur.execute(f"""
                SELECT pg_terminate_backend(pid), pid, usename, application_name
                FROM pg_stat_activity 
                WHERE state IN ('idle', 'idle in transaction') 
                  AND state_change < now() - interval '{IDLE_THRESHOLD_MINUTES} minutes'
                  AND pid <> pg_backend_pid()
                  AND usename NOT IN ({excluded_users_str});
            """)
            terminated = cur.fetchall()
            
            if terminated:
                logger.info(f"Terminated {len(terminated)} idle connections:")
                for row in terminated:
                    logger.info(f"  - PID: {row[1]}, User: {row[2]}, App: {row[3]}")
            else:
                logger.info("No idle connections to terminate")

        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error terminating connections: {str(e)}")


def main():
    """Main entry point - starts the scheduler."""
    logger.info("=" * 50)
    logger.info("DB Automation Service Starting")
    logger.info(f"  Check interval: {CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"  Idle threshold: {IDLE_THRESHOLD_MINUTES} minutes")
    logger.info(f"  Dry run mode: {DRY_RUN}")
    logger.info(f"  Excluded users: {EXCLUDED_USERS}")
    logger.info("=" * 50)

    # Run once immediately on startup
    terminate_idle_connections()
    
    # Schedule periodic runs
    scheduler = BlockingScheduler()
    scheduler.add_job(
        terminate_idle_connections, 
        'interval', 
        minutes=CHECK_INTERVAL_MINUTES,
        next_run_time=datetime.now()
    )
    
    logger.info(f"Scheduler started. Next check in {CHECK_INTERVAL_MINUTES} minutes...")
    scheduler.start()


if __name__ == "__main__":
    main()
