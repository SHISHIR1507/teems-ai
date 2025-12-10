## Deployment TODOs for new services

- Add ECS task definitions/services for:
  - gateway
  - vector-store-service
  - parsers-service
  - recommender-service
  - billing-service
- Wire Redis (ElastiCache) endpoint into realtime and Eve Core.
- Expose appropriate ALB listeners/target groups and security groups.
- Ensure S3 bucket for parsers artifacts is configured and permissions granted.


