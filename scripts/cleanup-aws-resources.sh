#!/bin/bash
# Cleanup script to remove AWS resources created by ECS deployments
# Usage: ./scripts/cleanup-aws-resources.sh [service-name]
#   service-name: eve-core, auth, brandfetch, realtime, or 'all' (default)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get AWS region from environment or prompt
AWS_REGION="${AWS_REGION:-}"
if [ -z "$AWS_REGION" ]; then
  echo -e "${YELLOW}AWS_REGION not set. Please enter your AWS region:${NC}"
  read -r AWS_REGION
fi

export AWS_REGION

# Service names
SERVICES=("eve-core" "auth" "brandfetch" "realtime")
SERVICE_TO_CLEAN="${1:-all}"

cleanup_service() {
  local service=$1
  local stack_name="teems-${service}-ecs"
  local ecr_repo="teems-${service}"
  
  echo -e "\n${YELLOW}=== Cleaning up ${service} service ===${NC}"
  
  # Check if CloudFormation stack exists
  if aws cloudformation describe-stacks --stack-name "${stack_name}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    echo -e "${YELLOW}Deleting CloudFormation stack: ${stack_name}${NC}"
    
    # Delete the stack
    aws cloudformation delete-stack --stack-name "${stack_name}" --region "${AWS_REGION}"
    
    echo -e "${GREEN}Stack deletion initiated. Waiting for completion...${NC}"
    aws cloudformation wait stack-delete-complete --stack-name "${stack_name}" --region "${AWS_REGION}" || {
      echo -e "${RED}Stack deletion failed or timed out. Check AWS Console.${NC}"
      return 1
    }
    
    echo -e "${GREEN}✓ CloudFormation stack deleted: ${stack_name}${NC}"
  else
    echo -e "${YELLOW}Stack ${stack_name} does not exist, skipping...${NC}"
  fi
  
  # Check if ECR repository exists
  if aws ecr describe-repositories --repository-names "${ecr_repo}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    echo -e "${YELLOW}Deleting ECR repository: ${ecr_repo}${NC}"
    
    # Delete all images first (required before deleting repo)
    echo -e "${YELLOW}Deleting all images in repository...${NC}"
    aws ecr list-images --repository-name "${ecr_repo}" --region "${AWS_REGION}" --query 'imageIds[*]' --output json > /tmp/images.json
    
    if [ "$(cat /tmp/images.json)" != "[]" ]; then
      aws ecr batch-delete-image \
        --repository-name "${ecr_repo}" \
        --region "${AWS_REGION}" \
        --image-ids file:///tmp/images.json >/dev/null 2>&1 || true
    fi
    
    # Delete the repository
    aws ecr delete-repository \
      --repository-name "${ecr_repo}" \
      --region "${AWS_REGION}" \
      --force >/dev/null 2>&1 || true
    
    echo -e "${GREEN}✓ ECR repository deleted: ${ecr_repo}${NC}"
    rm -f /tmp/images.json
  else
    echo -e "${YELLOW}ECR repository ${ecr_repo} does not exist, skipping...${NC}"
  fi
  
  # Clean up CloudWatch Log Groups
  local log_group="/ecs/teems-${service}"
  if aws logs describe-log-groups --log-group-name-prefix "${log_group}" --region "${AWS_REGION}" --query "logGroups[?logGroupName=='${log_group}']" --output text | grep -q "${log_group}"; then
    echo -e "${YELLOW}Deleting CloudWatch Log Group: ${log_group}${NC}"
    aws logs delete-log-group --log-group-name "${log_group}" --region "${AWS_REGION}" >/dev/null 2>&1 || true
    echo -e "${GREEN}✓ CloudWatch Log Group deleted: ${log_group}${NC}"
  else
    echo -e "${YELLOW}Log group ${log_group} does not exist, skipping...${NC}"
  fi
}

# Main cleanup logic
if [ "$SERVICE_TO_CLEAN" = "all" ]; then
  echo -e "${YELLOW}Cleaning up ALL services...${NC}"
  for service in "${SERVICES[@]}"; do
    cleanup_service "$service"
  done
  echo -e "\n${GREEN}=== All services cleaned up ===${NC}"
else
  # Validate service name
  if [[ ! " ${SERVICES[*]} " =~ " ${SERVICE_TO_CLEAN} " ]]; then
    echo -e "${RED}Error: Invalid service name '${SERVICE_TO_CLEAN}'${NC}"
    echo -e "Valid services: ${SERVICES[*]} or 'all'"
    exit 1
  fi
  
  cleanup_service "$SERVICE_TO_CLEAN"
  echo -e "\n${GREEN}=== ${SERVICE_TO_CLEAN} service cleaned up ===${NC}"
fi

echo -e "\n${GREEN}Cleanup complete!${NC}"
echo -e "${YELLOW}Note: Some resources may take a few minutes to fully delete.${NC}"
echo -e "${YELLOW}Check AWS Console to verify all resources are removed.${NC}"

