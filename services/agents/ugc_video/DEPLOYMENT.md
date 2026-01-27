# UGC Video Orchestrator - Deployment Guide

## 🚀 Deployment Overview

The UGC Video Orchestrator service is deployed to AWS ECS Fargate using GitHub Actions. The deployment automatically:
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
- `DATABASE_URL` or `UGC_VIDEO_DATABASE_URL`
  - Format: `postgresql+asyncpg://user:password@host:port/dbname`
  - Example: `postgresql+asyncpg://postgres:password@db.example.com:5432/ugc_db`

#### S3 Configuration
- `S3_BUCKET_NAME` or `UGC_VIDEO_S3_BUCKET_NAME`
  - Your S3 bucket name for storing assets
  - Example: `teems-agents`

- `S3_FOLDER_PREFIX` or `UGC_VIDEO_S3_FOLDER_PREFIX` (optional)
  - Default: `UGC_Agent`
  - Folder prefix inside bucket for organizing assets

#### AI/ML API Keys
- `AIML_API_KEY` or `UGC_VIDEO_AIML_API_KEY` (required)
  - API key for AIML API (used for GPT-5.2, image generation, TTS, video)

- `OPENAI_API_KEY` or `UGC_VIDEO_OPENAI_API_KEY` (optional)
  - Direct OpenAI API key (if not using AIML API for OpenAI)

#### LangSmith (Observability)
- `LANGCHAIN_API_KEY` or `UGC_VIDEO_LANGCHAIN_API_KEY` (required)
  - LangSmith API key for tracing agent workflows

- `LANGCHAIN_PROJECT` or `UGC_VIDEO_LANGCHAIN_PROJECT` (optional)
  - Default: `ugc-orchestrator`
  - LangSmith project name

#### Optional Features
- `LIPSYNC_API_KEY` or `UGC_VIDEO_LIPSYNC_API_KEY` (optional)
  - Sync API key for lipsync feature

#### Auth0 Configuration (Required)
- `AUTH0_DOMAIN` or `UGC_VIDEO_AUTH0_DOMAIN` (required)
  - Your Auth0 domain (e.g., `your-tenant.auth0.com`)
  - Already configured in your Auth0 account

- `AUTH0_AUDIENCE` or `UGC_VIDEO_AUTH0_AUDIENCE` (required)
  - Your Auth0 API audience identifier
  - Already configured in your Auth0 account

- `AUTH0_ALGORITHM` or `UGC_VIDEO_AUTH0_ALGORITHM` (optional)
  - Default: `RS256`
  - JWT signing algorithm

#### CORS Configuration
- `CORS_ALLOWED_ORIGINS` or `UGC_VIDEO_CORS_ALLOWED_ORIGINS` (optional)
  - Comma-separated list of allowed CORS origins (no wildcards allowed)
  - Example: `https://app.example.com,https://admin.example.com`
  - If not set, defaults to localhost origins for development
  - Default includes: `http://localhost:3000`, `http://localhost:5173`, `https://teems-web-app.vercel.app`
  - **Security**: Wildcards (`*`) are not allowed - specific origins must be listed

#### SSL Certificate (Optional)
- `SSL_CERTIFICATE_ARN` or `UGC_VIDEO_SSL_CERTIFICATE_ARN` (optional)
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
- Files in `services/agents/ugc_video/` change
- `infra/ecs-ugc-video-stack.yaml` changes
- `.github/workflows/deploy-ugc-video-ecs.yml` changes

### Database Migration

Before deploying, run the tenant isolation migration:

```bash
python migrations/add_tenant_isolation_migration.py
```

This adds `tenant_id` and `user_id` columns to existing tables and sets default values for existing data.

### Manual Deployment

You can also trigger deployment manually:
1. Go to GitHub Actions tab
2. Select "Deploy UGC Video Orchestrator to ECS"
3. Click "Run workflow"

## 🏗️ Infrastructure

### VPC Requirements

The service uses shared VPC resources from the **Brandfetch stack** (`teems-brandfetch-ecs`). The Brandfetch stack must be deployed first.

The workflow automatically:
1. Checks if Brandfetch stack exists
2. Retrieves VPC ID and subnet IDs
3. Validates resources exist
4. Passes them to the UGC Video stack

### Resources Created

- **ECS Cluster**: `teems-ugc-video-cluster`
- **ECS Service**: `teems-ugc-video-service`
- **Application Load Balancer**: `teems-ugc-video-alb`
- **Target Group**: `teems-ugc-video-tg`
- **Security Groups**: ALB and ECS task security groups
- **CloudWatch Log Group**: `/ecs/teems-ugc-video`
- **IAM Roles**: Task execution and task roles with S3 permissions

### Resource Sizing

- **CPU**: 1024 (1 vCPU)
- **Memory**: 2048 MB (2 GB)
- **Desired Count**: 1 (configurable)

## 🔍 Verification

After deployment, verify the service:

```bash
# Get service URL from GitHub Actions output
# Or query CloudFormation stack
aws cloudformation describe-stacks \
  --stack-name teems-ugc-video-ecs \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" \
  --output text

# Test health endpoint
curl https://<load-balancer-dns>/health
```

Expected response:
```json
{
  "status": "online",
  "service": "UGC Orchestrator API with DB & S3",
  "version": "2.0.0",
  "database": "PostgreSQL",
  "storage": "AWS S3"
}
```

## 🐛 Troubleshooting

### Stack Deployment Fails

1. **Check CloudFormation events**:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name teems-ugc-video-ecs \
     --max-items 20
   ```

2. **Common issues**:
   - Missing secrets → Check GitHub secrets are configured
   - VPC not found → Ensure Brandfetch stack is deployed
   - S3 bucket doesn't exist → Create bucket or update secret
   - Database connection fails → Verify DATABASE_URL format

### Service Not Responding

1. **Check ECS service status**:
   ```bash
   aws ecs describe-services \
     --cluster teems-ugc-video-cluster \
     --services teems-ugc-video-service
   ```

2. **Check CloudWatch logs**:
   ```bash
   aws logs tail /ecs/teems-ugc-video --follow
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
- Run migration script if tenant_id columns are missing: `python migrations/add_tenant_isolation_migration.py`

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

## 📝 Notes

- **First Deployment**: May take 10-15 minutes for initial stack creation
- **Subsequent Deployments**: Usually 5-8 minutes for image build and service update
- **Rollback**: Enabled - failed deployments automatically rollback
- **Health Checks**: Service must respond to `/health` within 60 seconds
- **Logs**: Available in CloudWatch Logs group `/ecs/teems-ugc-video`

## 🔗 Related Documentation

- [Local Development README](./README.md)
- [CloudFormation Stack Template](../../infra/ecs-ugc-video-stack.yaml)
- [GitHub Actions Workflow](../../.github/workflows/deploy-ugc-video-ecs.yml)
