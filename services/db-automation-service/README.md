# DB Automation Service

A lightweight ECS service that automatically terminates idle PostgreSQL database connections.

## Purpose

Prevents accumulation of idle database connections that consume RDS resources and connection limits.

## How It Works

1. Runs on a configurable schedule (default: every 5 minutes)
2. Queries `pg_stat_activity` for idle connections
3. Terminates connections that have been idle longer than the threshold
4. Logs all actions to CloudWatch

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | - | PostgreSQL host (RDS endpoint) |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | - | Database name |
| `DB_USER` | - | Database user with termination privileges |
| `DB_PASSWORD` | - | Database password |
| `IDLE_THRESHOLD_MINUTES` | `10` | Terminate connections idle longer than this |
| `CHECK_INTERVAL_MINUTES` | `30` | How often to check for idle connections |
| `DRY_RUN` | `false` | Set to `true` to log only without terminating |
| `EXCLUDED_USERS` | `rdsadmin` | Comma-separated list of users to never terminate |

## Local Development

```bash
# Copy example env file
cp .env.example .env

# Edit with your database credentials
nano .env

# Build Docker image
docker build -t db-automation-service .

# Run locally (dry run mode recommended)
docker run --env-file .env -e DRY_RUN=true db-automation-service
```

## Deployment

Deploy using the CloudFormation stack:

```bash
aws cloudformation deploy \
  --template-file infra/ecs-db-automation-stack.yaml \
  --stack-name teems-db-automation \
  --parameter-overrides \
    DatabaseUrl="postgresql://user:pass@host:5432/dbname" \
    DryRun="true" \
  --capabilities CAPABILITY_NAMED_IAM
```

## Safety Features

- **Dry Run Mode**: Test first with `DRY_RUN=true` to see what would be terminated
- **Excluded Users**: Never terminates `rdsadmin` or other specified users
- **Self-Protection**: Never terminates its own connection
- **CloudWatch Logging**: All actions are logged for audit

## CloudWatch Logs

View logs in AWS Console:
- Log Group: `/ecs/teems-db-automation`

Example log output:
```
2026-01-23 15:30:00 - INFO - Starting idle connection check (threshold: 10 min)...
2026-01-23 15:30:01 - INFO - Terminated 12 idle connections:
2026-01-23 15:30:01 - INFO -   - PID: 1234, User: postgres, App: pgAdmin 4 - CONN:12345
```
