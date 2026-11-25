# Screenshots

Save each screenshot here as PNG with the exact name below; [../cloud-deployment.md](../cloud-deployment.md)
already shows them under the right heading.

**Before you save:** this repository is public. Blur your **AWS account ID**, e-mail address, the ALB
secret header value and any secret values.

| File | Console page | Make sure it shows |
|---|---|---|
| `01-iam-groups.png` | IAM → User groups | `teampulse-deployers`, `teampulse-developers` |
| `02-iam-roles.png` | IAM → Roles (search `teampulse`) | execution, task and Lambda roles |
| `03-secrets-manager.png` | Secrets Manager → Secrets | JWT key and the database passwords |
| `04-vpc-subnets.png` | VPC → Subnets | 6 subnets, CIDRs, two zones |
| `05-route-tables.png` | VPC → Route tables → `teampulse-app-rt` → Routes | `0.0.0.0/0 → NAT`, the two endpoints |
| `06-security-groups.png` | VPC → Security groups → `teampulse-rds-sg` → Inbound | 5432 from `teampulse-services-sg` only |
| `07-network-acls.png` | VPC → Network ACLs → `teampulse-data-nacl` → Inbound | 5432 from the app subnets only |
| `08-vpc-endpoints.png` | VPC → Endpoints | S3 and DynamoDB gateway endpoints |
| `09-rds.png` | RDS → `teampulse-db` → Connectivity & security | Publicly accessible: No, data subnets, `rds-sg` |
| `10-dynamodb.png` | DynamoDB → `teampulse-analytics` → Overview | keys `pk` / `sk`, on-demand |
| `11-ecr.png` | ECR → Private repositories | 8 repositories, tag immutability, scan on push |
| `12-ecs-services.png` | ECS → `teampulse` → Services | 7 services, running tasks |
| `13-ecs-autoscaling.png` | ECS → a service → Service auto scaling | min 1, max 2, CPU 60 % |
| `14-task-definition.png` | ECS → Task definitions → a service → JSON or Containers | env vars, secrets `valueFrom`, read-only root filesystem |
| `15-alb-listener-rules.png` | EC2 → Load balancers → `teampulse-alb` → Listener rules | default 403, header rule → target group |
| `16-target-group.png` | EC2 → Target groups → `teampulse-gateway-tg` → Targets | healthy targets |
| `17-lambda.png` | Lambda → `teampulse-streak-processor` | EventBridge trigger, VPC, memory and timeout |
| `18-eventbridge-rules.png` | EventBridge → Rules → bus `teampulse-events` | the 4 rules |
| `19-eventbridge-scheduler.png` | EventBridge → Scheduler → Schedules | `teampulse-reminder-tick`, hourly |
| `20-sqs.png` | SQS → Queues | 3 queues + dead-letter queues |
| `21-s3-bucket.png` | S3 → bucket → Permissions | Block all public access: On, CloudFront bucket policy |
| `22-cloudfront.png` | CloudFront → distribution → Behaviors | `/api/*`, `/.well-known/*`, default → S3 |
| `23-cloudwatch-dashboard.png` | CloudWatch → Dashboards → `TeamPulse` | the widgets with data |
| `24-cloudwatch-alarms.png` | CloudWatch → Alarms | the 10 alarms |
| `25-logs-insights.png` | CloudWatch → Logs Insights | one `request_id` in several services' logs |
| `26-app-login.png` | `https://<cloudfront-domain>` | login page over HTTPS |
| `27-app-dashboard.png` | the app, signed in as an employee | dashboard with data |
| `28-app-team-insights.png` | the app, signed in as a manager | Team insights with the privacy notice |
