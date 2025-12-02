# Environment Variables Setup Guide

This guide explains how to configure environment variables for all services when deploying to AWS ECS.

## Overview

**You do NOT need to create `.env` files in your repository.** Instead, you'll set environment variables as GitHub repository secrets, which will be automatically passed to your ECS containers when you push to `main`.

## Quick Start

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**
2. Add the secrets listed below for each service
3. Push to `main` - the workflows will automatically use these secrets

---

## Required GitHub Secrets

### 1. AWS Credentials (Required for all services)

These are the only secrets you mentioned you can provide:

- `AWS_ACCESS_KEY_ID` - Your AWS access key
- `AWS_SECRET_ACCESS_KEY` - Your AWS secret key
- `AWS_REGION` - AWS region (e.g., `us-east-1`)
- `AWS_ACCOUNT_ID` - Your 12-digit AWS account ID

---

## Service-Specific Secrets

### Eve Core Service (`eve-core`)

**Required:**
- `EVE_CORE_DATABASE_URL` - PostgreSQL connection string  
  - Format: `postgresql://username:password@host:5432/database_name`  
  - Example: `postgresql://admin:mypass@my-rds-instance.region.rds.amazonaws.com:5432/evacore`
- `EVE_CORE_AIML_API_KEY` - AIML API key, used for both OpenAI and Gemini-compatible models  
  - See AIML docs: https://docs.aimlapi.com/quickstart/setting-up

**Optional (with defaults):**
- `EVE_CORE_AIML_BASE_URL` - Base URL for AIML API (default `https://api.aimlapi.com/v1`)
- `EVE_CORE_EMBEDDING_PROVIDER` - `openai` or `gemini` (default: `openai`)
- `EVE_CORE_EMBEDDING_MODEL` - Embedding model name (default: `text-embedding-3-small`)
- `EVE_CORE_DEFAULT_LLM_PROVIDER` - `openai` or `gemini` (default: `openai`)
- `EVE_CORE_DEFAULT_LLM_MODEL` - LLM model name (default: `gpt-4o-mini`)

**Example values:**
```
EVE_CORE_DATABASE_URL=postgresql://user:pass@db.example.com:5432/eve_db
EVE_CORE_AIML_API_KEY=aiml-...
EVE_CORE_AIML_BASE_URL=https://api.aimlapi.com/v1
EVE_CORE_EMBEDDING_PROVIDER=openai
EVE_CORE_EMBEDDING_MODEL=text-embedding-3-small
EVE_CORE_DEFAULT_LLM_PROVIDER=openai
EVE_CORE_DEFAULT_LLM_MODEL=gpt-4o
```

---

### Auth Service (`user-service`)

**Required:**
- `AUTH_AUTH0_DOMAIN` - Your Auth0 domain
  - Format: `your-tenant.auth0.com`
  - Example: `mycompany.auth0.com`

- `AUTH_AUTH0_AUDIENCE` - Auth0 API audience/identifier
  - Example: `https://api.mycompany.com`

- `AUTH_AUTH0_CLIENT_ID` - Auth0 application client ID

- `AUTH_AUTH0_CLIENT_SECRET` - Auth0 application client secret

- `AUTH_AUTH0_MANAGEMENT_AUDIENCE` - Auth0 Management API audience
  - Example: `https://your-tenant.auth0.com/api/v2/`

**Optional (for PostgreSQL):**
- `AUTH_POSTGRES_HOST` - PostgreSQL host
- `AUTH_POSTGRES_DB` - Database name
- `AUTH_POSTGRES_USER` - Database username
- `AUTH_POSTGRES_PASSWORD` - Database password

**Example values:**
```
AUTH_AUTH0_DOMAIN=mycompany.auth0.com
AUTH_AUTH0_AUDIENCE=https://api.mycompany.com
AUTH_AUTH0_CLIENT_ID=abc123xyz
AUTH_AUTH0_CLIENT_SECRET=secret123
AUTH_AUTH0_MANAGEMENT_AUDIENCE=https://mycompany.auth0.com/api/v2/
AUTH_POSTGRES_HOST=my-db.example.com
AUTH_POSTGRES_DB=auth_db
AUTH_POSTGRES_USER=admin
AUTH_POSTGRES_PASSWORD=securepass
```

---

### Brandfetch Workflow Service (`workflow-service/BrandfetchAPI`)

**Required:**
- `BRANDFETCH_API_KEY` - Your Brandfetch API key
- `BRANDFETCH_DATABASE_URL` - PostgreSQL connection string
  - Format: `postgresql://username:password@host:5432/database_name`

**Example values:**
```
BRANDFETCH_API_KEY=bf_abc123xyz
BRANDFETCH_DATABASE_URL=postgresql://user:pass@db.example.com:5432/brandfetch_db
```

---

### Realtime Workflow Service (`workflow-service/realtime`)

**No secrets required!** This service has sensible defaults:
- `DEFAULT_JOB_DURATION_SECONDS=3.0`
- `MAX_CONNECTIONS=500`

If you want to customize, you can add these as CloudFormation parameters later.

---

## How It Works

1. **GitHub Secrets** → Stored securely in your repository settings
2. **GitHub Actions Workflows** → Read secrets and pass them as CloudFormation parameters
3. **CloudFormation** → Creates ECS task definitions with environment variables
4. **ECS Containers** → Receive environment variables at runtime (no `.env` files needed)

---

## Setting Up Secrets in GitHub

### Step-by-Step:

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Enter the secret name (exactly as listed above, e.g., `EVE_CORE_DATABASE_URL`)
5. Enter the secret value
6. Click **Add secret**
7. Repeat for all required secrets

### Example: Setting up Eve Core

```
Secret Name: EVE_CORE_DATABASE_URL
Secret Value: postgresql://admin:password@my-rds.region.rds.amazonaws.com:5432/eve_db

Secret Name: EVE_CORE_OPENAI_API_KEY
Secret Value: sk-proj-abc123...
```

---

## Testing Your Setup

After adding secrets and pushing to `main`:

1. Check GitHub Actions → Your workflow runs should complete successfully
2. Each workflow will output a service URL at the end
3. Test the endpoints:
   - **Eve Core**: `http://<alb-dns>/docs` (FastAPI docs)
   - **Auth**: `http://<alb-dns>/health` (health check)
   - **Brandfetch**: `http://<alb-dns>/health` (health check)
   - **Realtime**: `http://<alb-dns>/health` (health check)

---

## Troubleshooting

### Service fails to start

1. Check CloudWatch Logs:
   - Go to AWS Console → CloudWatch → Log Groups
   - Look for `/ecs/teems-<service-name>`
   - Check for errors about missing environment variables

2. Verify secrets are set:
   - Go to GitHub → Settings → Secrets and variables → Actions
   - Ensure all required secrets are present

3. Check ECS Task Definition:
   - Go to AWS Console → ECS → Task Definitions
   - Find `teems-<service-name>-task`
   - Check the "Environment" section to see what variables were set

### Database connection errors

- Verify your database is accessible from the ECS VPC
- Check security groups allow connections from ECS tasks
- Ensure the connection string format is correct: `postgresql://user:pass@host:port/db`

### Missing environment variables

- Services use `pydantic-settings` which will show clear errors if required variables are missing
- Check CloudWatch logs for specific error messages

---

## Security Best Practices

1. **Never commit `.env` files** to git (they're already in `.gitignore`)
2. **Use GitHub Secrets** for all sensitive values
3. **Rotate secrets regularly** (especially API keys and database passwords)
4. **Use AWS Secrets Manager** for production (future enhancement - see below)

---

## Future: Using AWS Secrets Manager

For production, consider migrating to AWS Secrets Manager instead of GitHub secrets:

1. Store secrets in AWS Secrets Manager (one JSON secret per service)
2. Update CloudFormation stacks to reference Secrets Manager ARNs
3. ECS will automatically fetch secrets at runtime

This provides:
- Automatic rotation
- Better audit trails
- Integration with AWS IAM
- No secrets in CloudFormation parameters

---

## Summary Checklist

Before pushing to `main`, ensure you have:

- [ ] `AWS_ACCESS_KEY_ID`
- [ ] `AWS_SECRET_ACCESS_KEY`
- [ ] `AWS_REGION`
- [ ] `AWS_ACCOUNT_ID`
- [ ] `EVE_CORE_DATABASE_URL` and `EVE_CORE_AIML_API_KEY` (and optionally `EVE_CORE_AIML_BASE_URL`)
- [ ] `AUTH_AUTH0_DOMAIN`, `AUTH_AUTH0_AUDIENCE`, `AUTH_AUTH0_CLIENT_ID`, `AUTH_AUTH0_CLIENT_SECRET`, `AUTH_AUTH0_MANAGEMENT_AUDIENCE`
- [ ] `BRANDFETCH_API_KEY` and `BRANDFETCH_DATABASE_URL`
- [ ] (Realtime service needs no secrets)

Once all secrets are set, push to `main` and watch the magic happen! 🚀

