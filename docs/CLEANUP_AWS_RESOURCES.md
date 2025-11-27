# Cleaning Up AWS Resources

This guide explains how to remove AWS resources created by the ECS deployments.

## Quick Cleanup (Automated Script)

The easiest way is to use the provided cleanup script:

```bash
# Make script executable
chmod +x scripts/cleanup-aws-resources.sh

# Clean up a specific service
./scripts/cleanup-aws-resources.sh eve-core
./scripts/cleanup-aws-resources.sh auth
./scripts/cleanup-aws-resources.sh brandfetch
./scripts/cleanup-aws-resources.sh realtime

# Clean up ALL services
./scripts/cleanup-aws-resources.sh all
```

The script requires AWS credentials configured (via `aws configure` or environment variables).

**What it removes:**
- CloudFormation stacks (and all associated resources: VPC, subnets, ALB, ECS cluster, etc.)
- ECR repositories (and all Docker images)
- CloudWatch Log Groups

---

## Manual Cleanup via AWS Console

If you prefer to clean up manually or the script doesn't work:

### 1. Delete CloudFormation Stacks

1. Go to **AWS Console** → **CloudFormation**
2. Find and select the stack you want to delete:
   - `teems-eve-core-ecs`
   - `teems-auth-ecs`
   - `teems-brandfetch-ecs`
   - `teems-realtime-ecs`
3. Click **Delete**
4. Wait for deletion to complete (may take 5-10 minutes)

**Note:** Deleting a CloudFormation stack automatically removes:
- VPC, subnets, internet gateway, route tables
- Application Load Balancer (ALB)
- ECS cluster and services
- Security groups
- IAM roles (task execution and task roles)
- CloudWatch Log Groups

### 2. Delete ECR Repositories (Optional)

If you want to remove Docker images:

1. Go to **AWS Console** → **ECR** (Elastic Container Registry)
2. Select repositories:
   - `teems-eve-core`
   - `teems-auth`
   - `teems-brandfetch`
   - `teems-realtime`
3. Click **Delete**
4. Confirm deletion

---

## Manual Cleanup via AWS CLI

### Delete a specific service:

```bash
# Set your region
export AWS_REGION=us-east-1

# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name teems-eve-core-ecs \
  --region $AWS_REGION

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name teems-eve-core-ecs \
  --region $AWS_REGION

# Delete ECR repository (optional)
aws ecr delete-repository \
  --repository-name teems-eve-core \
  --region $AWS_REGION \
  --force
```

### Delete all services:

```bash
export AWS_REGION=us-east-1

# Delete all stacks
for stack in teems-eve-core-ecs teems-auth-ecs teems-brandfetch-ecs teems-realtime-ecs; do
  echo "Deleting $stack..."
  aws cloudformation delete-stack --stack-name "$stack" --region $AWS_REGION
done

# Wait for all deletions
for stack in teems-eve-core-ecs teems-auth-ecs teems-brandfetch-ecs teems-realtime-ecs; do
  aws cloudformation wait stack-delete-complete --stack-name "$stack" --region $AWS_REGION
done

# Delete all ECR repositories
for repo in teems-eve-core teems-auth teems-brandfetch teems-realtime; do
  aws ecr delete-repository --repository-name "$repo" --region $AWS_REGION --force 2>/dev/null || true
done
```

---

## Preventing Unnecessary Deployments

The workflows are now configured to **only run when relevant files change**:

- **Eve Core** workflow runs only when:
  - Files in `services/eve-core/` change
  - `infra/ecs-eve-core-stack.yaml` changes
  - The workflow file itself changes

- **Auth** workflow runs only when:
  - Files in `services/user-service/` change
  - `infra/ecs-auth-stack.yaml` changes
  - The workflow file itself changes

- **Brandfetch** workflow runs only when:
  - Files in `services/workflow-service/BrandfetchAPI/` change
  - `infra/ecs-brandfetch-stack.yaml` changes
  - The workflow file itself changes

- **Realtime** workflow runs only when:
  - Files in `services/workflow-service/realtime/` change
  - `infra/ecs-realtime-stack.yaml` changes
  - The workflow file itself changes

### Manual Deployment

If you need to manually trigger a deployment (even when files haven't changed):

1. Go to **GitHub** → **Actions** tab
2. Select the workflow you want to run (e.g., "Deploy Eve Core to ECS")
3. Click **Run workflow** → **Run workflow**
4. This will trigger the deployment manually

---

## Troubleshooting

### Stack deletion stuck

If a CloudFormation stack deletion is stuck:

1. Check the stack events in AWS Console for errors
2. Common issues:
   - ECS service still has running tasks → Manually stop tasks first
   - ALB has active connections → Wait a few minutes
   - Security groups in use → Check for dependencies

### Force delete a stuck stack

If you need to force delete (not recommended):

```bash
# First, try to delete the stack normally
aws cloudformation delete-stack --stack-name <stack-name> --region <region>

# If stuck, you may need to manually delete resources in the console first
# Then retry stack deletion
```

### ECR repository deletion fails

ECR repositories can only be deleted if they're empty or you use `--force`:

```bash
aws ecr delete-repository \
  --repository-name <repo-name> \
  --region <region> \
  --force
```

---

## Cost Implications

After cleanup, you should see:

- **No ECS charges** (no running tasks/clusters)
- **No ALB charges** (load balancers deleted)
- **No VPC charges** (VPCs are free, but associated resources are deleted)
- **No ECR storage charges** (images deleted)
- **Minimal CloudWatch charges** (log groups deleted, but may retain logs for retention period)

**Note:** Some resources may continue to incur charges for a short period after deletion (e.g., ALB data transfer charges for the current billing cycle).

---

## Summary

- ✅ **Automated cleanup**: Use `scripts/cleanup-aws-resources.sh`
- ✅ **Manual cleanup**: Delete CloudFormation stacks in AWS Console
- ✅ **Selective deployments**: Workflows only run when relevant files change
- ✅ **Manual triggers**: Use GitHub Actions "Run workflow" button when needed

