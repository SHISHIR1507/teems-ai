# Eve AI Agent - Deployment Guide

## 🚀 Deployment Overview

The Eve AI Agent service is deployed to AWS ECS Fargate using GitHub Actions. The deployment automatically:
1. Builds a Docker image
2. Pushes to Amazon ECR
3. Deploys CloudFormation stack with ECS service
4. Uses shared VPC resources from Brandfetch stack

## 📋 Required GitHub Secrets

Configure these secrets in your GitHub repository settings:

### Core AWS Secrets (Shared)
- `AWS_REGION` - AWS region (e.g., `us-east-1`)
- `AWS_ACCOUNT_ID` - AWS account ID
- `AWS_ACCESS_KEY_ID` - AWS access key for GitHub Actions
- `AWS_SECRET_ACCESS_KEY` - AWS secret key for GitHub Actions

### Service-Specific Secrets

You can use either the generic secret name or the service-specific name:

#### Database
- `DATABASE_URL` or `EVE_DATABASE_URL`
  - Format: `postgresql+asyncpg://user:password@host:port/dbname`
  - Example: `postgresql+asyncpg://postgres:password@db.example.com:5432/eve_db`
  - **Note**: Database must have pgvector extension enabled

#### S3 Configuration
- `S3_BUCKET_NAME` or `EVE_S3_BUCKET_NAME` (optional)
  - Your S3 bucket name for storing uploaded documents
  - Example: `teems-agents`
  - If not provided, document uploads will fail but chat will work

- `S3_FOLDER_PREFIX` or `EVE_S3_FOLDER_PREFIX` (optional)
  - Default: `UserUploads`
  - Folder prefix inside bucket for organizing documents

- `AWS_ACCESS_KEY_ID` or `EVE_AWS_ACCESS_KEY_ID` (optional)
  - AWS access key (if not using IAM roles)
  - Usually not needed - service uses IAM roles in ECS

- `AWS_SECRET_ACCESS_KEY` or `EVE_AWS_SECRET_ACCESS_KEY` (optional)
  - AWS secret key (if not using IAM roles)
  - Usually not needed - service uses IAM roles in ECS

- `AWS_REGION` or `EVE_AWS_REGION` (optional)
  - Default: `us-east-1`
  - AWS region for S3 bucket

#### AI/ML API Keys
- `AIML_API_KEY` or `EVE_AIML_API_KEY` (required)
  - API key for AIML API (used for GPT-5.2 and embeddings)
  - Get from: https://aimlapi.com/

- `AIML_BASE_URL` or `EVE_AIML_BASE_URL` (optional)
  - Default: `https://api.aimlapi.com/v1`
  - AIML API base URL

#### MCP Server Configuration
- `TAVILY_API` or `EVE_TAVILY_API` (optional)
  - Tavily API key for web search MCP server
  - Get from: https://tavily.com/
  - If not provided, Tavily MCP server will not start (chat will still work)

#### Redis Configuration (for realtime notifications)
- `REDIS_URL` or `EVE_REDIS_URL` (optional)
  - Redis connection URL for realtime notifications
  - Format: `redis://user:password@host:port` or `rediss://` for TLS
  - Example: `redis://redis.example.com:6379`
  - If not provided, realtime notifications will be disabled (chat will still work)

#### Auth0 Configuration (Required)
- `AUTH0_DOMAIN` or `EVE_AUTH0_DOMAIN` (required)
  - Your Auth0 domain (e.g., `your-tenant.auth0.com`)
  - Already configured in your Auth0 account

- `AUTH0_AUDIENCE` or `EVE_AUTH0_AUDIENCE` (required)
  - Your Auth0 API audience identifier
  - Already configured in your Auth0 account

- `AUTH0_ALGORITHM` or `EVE_AUTH0_ALGORITHM` (optional)
  - Default: `RS256`
  - JWT signing algorithm

#### CORS Configuration
- `CORS_ALLOWED_ORIGINS` or `EVE_CORS_ALLOWED_ORIGINS` (optional)
  - Comma-separated list of allowed CORS origins (no wildcards allowed)
  - Example: `https://app.example.com,https://admin.example.com`
  - If not set, defaults to localhost origins for development
  - Default includes: `http://localhost:3000`, `http://localhost:5173`, `https://teems-web-app.vercel.app`
  - **Security**: Wildcards (`*`) are not allowed - specific origins must be listed

#### SSL Certificate (Optional)
- `SSL_CERTIFICATE_ARN` or `EVE_SSL_CERTIFICATE_ARN` (optional)
  - ACM certificate ARN for HTTPS
  - If not set, service will use HTTP only

## 🔐 IAM Permissions

The ECS task role automatically has S3 permissions for the specified bucket. **No AWS credentials need to be passed as environment variables** - the service uses IAM roles.

## 🔐 Authentication Setup

The service requires Auth0 authentication. Ensure your Auth0 configuration includes:

1. **API Configuration**: Create an API in Auth0 with:
   - Identifier (audience): Set as `AUTH0_AUDIENCE` environment variable
   - Signing Algorithm: RS256

2. **Custom Claims**: Add custom claims to tokens:
   - `https://teems.ai/tenant_id` (preferred) or `tenant_id` - Required for tenant isolation
   - `https://teems.ai/roles` (optional) - For role-based access

3. **Token Configuration**: Ensure tokens include:
   - `aud` (audience) matching your API identifier
   - `iss` (issuer) matching your Auth0 domain
   - Custom `tenant_id` claim

## 📦 Deployment Process

### Automatic Deployment

Deployment triggers automatically on push to `main` branch when:
- Files in `services/eve/` change
- `infra/ecs-eve-stack.yaml` changes
- `.github/workflows/deploy-eve-ecs.yml` changes

### Database Setup

Before deploying, set up the database:

1. **Create database with pgvector extension**:
   ```sql
   CREATE DATABASE eve_db;
   \c eve_db
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Run migrations**:
   ```bash
   # From services/eve directory
   python migrations/initial_schema_migration.py
   python migrations/add_tenant_isolation_migration.py
   ```

### Manual Deployment

You can also trigger deployment manually:
1. Go to GitHub Actions tab
2. Select "Deploy Eve AI to ECS"
3. Click "Run workflow"

## 🏗️ Infrastructure

### VPC Requirements

The service uses shared VPC resources from the **Brandfetch stack** (`teems-brandfetch-ecs`). The Brandfetch stack must be deployed first.

The workflow automatically:
1. Checks if Brandfetch stack exists
2. Retrieves VPC ID and subnet IDs
3. Validates resources exist
4. Passes them to the Eve stack

### Resources Created

- **ECS Cluster**: `teems-eve-cluster`
- **ECS Service**: `teems-eve-service`
- **Application Load Balancer**: `teems-eve-alb`
- **Target Group**: `teems-eve-tg`
- **Security Groups**: ALB and ECS task security groups
- **CloudWatch Log Group**: `/ecs/teems-eve`
- **IAM Roles**: Task execution and task roles with S3 permissions

### Resource Sizing

- **CPU**: 1024 (1 vCPU)
- **Memory**: 2048 MB (2 GB)
- **Desired Count**: 1 (configurable)

**Note**: MCP servers run as subprocesses within the container. Ensure sufficient memory for:
- Main application
- Tavily MCP server (Node.js)
- PostgreSQL MCP server (Node.js)
- Meeting RAG MCP server (Python)
- Document RAG MCP server (Python)

## 🔍 Verification

After deployment, verify the service:

```bash
# Get service URL from GitHub Actions output
# Or query CloudFormation stack
aws cloudformation describe-stacks \
  --stack-name teems-eve-ecs \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" \
  --output text

# Test health endpoint
curl https://<load-balancer-dns>/health
```

Expected response:
```json
{
  "status": "ok"
}
```

## 🐛 Troubleshooting

### Stack Deployment Fails

1. **Check CloudFormation events**:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name teems-eve-ecs \
     --max-items 20
   ```

2. **Common issues**:
   - Missing secrets → Check GitHub secrets are configured
   - VPC not found → Ensure Brandfetch stack is deployed
   - S3 bucket doesn't exist → Create bucket or update secret
   - Database connection fails → Verify DATABASE_URL format
   - pgvector extension missing → Run `CREATE EXTENSION vector;` in database

### Service Not Responding

1. **Check ECS service status**:
   ```bash
   aws ecs describe-services \
     --cluster teems-eve-cluster \
     --services teems-eve-service
   ```

2. **Check CloudWatch logs**:
   ```bash
   aws logs tail /ecs/teems-eve --follow
   ```

3. **Check target group health**:
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn <target-group-arn>
   ```

### Database Connection Issues

- Verify `DATABASE_URL` uses `postgresql+asyncpg://` format
- Ensure database allows connections from ECS security group
- Check database credentials are correct
- Verify pgvector extension is installed: `SELECT * FROM pg_extension WHERE extname = 'vector';`
- Run migration scripts if tables are missing: `python migrations/initial_schema_migration.py`

### MCP Server Connection Failures

- **Tavily MCP**: Check `TAVILY_API` is set (optional - service continues without it)
- **PostgreSQL MCP**: Verify `DATABASE_URL` is accessible from container
- **Meeting RAG MCP**: Check Python dependencies are installed
- **Document RAG MCP**: Check Python dependencies and S3 credentials

Check logs for MCP connection status:
```bash
aws logs tail /ecs/teems-eve --follow | grep "MCP"
```

### Authentication Issues

- Verify `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` are set correctly
- Check that Auth0 tokens include `tenant_id` claim
- Ensure tokens are not expired
- Verify API audience matches the token's `aud` claim

### CORS Issues

- Verify `CORS_ALLOWED_ORIGINS` includes your frontend domain
- Check that origins are comma-separated (no spaces)
- Ensure no wildcards (`*`) are used
- Verify `allow_credentials=True` is set (required for authenticated requests)

### S3 Access Issues

- Verify S3 bucket exists and name is correct
- Check IAM task role has S3 permissions
- Ensure bucket policy allows ECS task role access
- If S3 is not configured, document uploads will fail but chat will work

### Redis Connection Issues

- Verify `REDIS_URL` is correct (optional - service continues without it)
- Check Redis is accessible from ECS security group
- If Redis is not configured, realtime notifications will be disabled but chat will work
- Check logs for Redis connection status

### Document Processing Issues

- Verify S3 credentials and bucket access
- Check document file size limits
- Ensure sufficient memory for document processing
- Check logs for specific error messages during processing

## 📝 Notes

- **First Deployment**: May take 10-15 minutes for initial stack creation
- **Subsequent Deployments**: Usually 5-8 minutes for image build and service update
- **Rollback**: Enabled - failed deployments automatically rollback
- **Health Checks**: Service must respond to `/health` within 60 seconds
- **Logs**: Available in CloudWatch Logs group `/ecs/teems-eve`
- **MCP Servers**: Automatically started on container startup
- **Graceful Degradation**: Service continues to work even if optional components (Redis, Tavily, S3) are unavailable

## 🔗 Related Documentation

- [Local Development README](./README.md)
- [Database Migrations](./migrations/README.md)
- [CloudFormation Stack Template](../../infra/ecs-eve-stack.yaml)
- [GitHub Actions Workflow](../../.github/workflows/deploy-eve-ecs.yml)
