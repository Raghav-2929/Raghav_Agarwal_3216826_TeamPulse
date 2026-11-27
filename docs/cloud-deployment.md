# Cloud deployment (AWS)

| | |
|---|---|
| Region | `ap-south-1` (Mumbai), two Availability Zones |
| Built from | [aws-deployment-guide.md](aws-deployment-guide.md), with demo-size settings |
| Network diagram | [network-architecture.md](network-architecture.md) |

## Case-study requirements → what is deployed

| Requirement (Session 3) | Deployed as | Section |
|---|---|---|
| S3 for hosting the frontend, distributed globally | Private S3 bucket behind CloudFront | [7](#7-frontend-s3--cloudfront) |
| Separate VPC segments: public, application, data | 6 subnets in 3 tiers over 2 zones | [2](#2-network) |
| ALB in public subnets → services in private subnets | `teampulse-alb` → gateway on ECS | [5](#5-compute-ecs-alb-lambda) |
| ECS with auto scaling | Fargate cluster `teampulse`, 7 services, 1–2 tasks each | [5](#5-compute-ecs-alb-lambda) |
| ECR private registry | 8 repositories `teampulse/*` | [4](#4-container-images-ecr) |
| RDS for transactions, DynamoDB for analytics | `teampulse-db` (5 databases), `teampulse-analytics` | [3](#3-data) |
| EventBridge and Lambda | bus `teampulse-events`, 4 rules, `teampulse-streak-processor` | [6](#6-messaging-eventbridge-sqs) |
| Secrets Manager + configuration as environment variables | 7 secrets; plain settings in task definitions | [1](#1-identity-and-access), [5](#5-compute-ecs-alb-lambda) |
| Least-privilege IAM per service | 2 roles per service + 1 Lambda role | [1](#1-identity-and-access) |
| Security groups, NACLs, private subnets, HTTPS/TLS | 5 security groups, 3 NACLs, HTTPS at CloudFront, TLS to RDS | [2](#2-network) |
| CloudWatch logs, metrics, dashboards, alerts | JSON logs, dashboard, 10 alarms, restart alerts | [8](#8-monitoring-cloudwatch) |

---

## 1. Identity and access

- **People:** groups `teampulse-deployers` (ship new versions only) and `teampulse-developers`
  (read only), both requiring MFA.
- **Workloads:** each service has an *execution role* (pull its image, write logs, read **only its own**
  secrets) and a *task role* (only what its code needs, e.g. insight-service may only read DynamoDB).
- **Secrets Manager:** the JWT signing key (identity-service only), one database password per
  service, and the RDS master password (managed by RDS). ECS injects them when a task starts; they are
  never in images or code.

![IAM groups](screenshots/01-iam-groups.png)
![IAM roles](screenshots/02-iam-roles-top.png)
![IAM roles (continued)](screenshots/02-iam-roles.png)
![Secrets Manager](screenshots/03-secrets-manager.png)

## 2. Network

- VPC `teampulse-vpc` `10.20.0.0/16` with public, private-app and private-data subnets in two zones.
- Route tables: public → internet gateway; app → NAT instance + S3/DynamoDB gateway endpoints; data →
  no internet route.
- NAT instance `teampulse-nat-a` (`t4g.micro`, Amazon Linux, no SSH, source/destination check off)
  instead of a NAT gateway, to keep the cost low.
- Security groups chain the tiers: internet → `alb-sg` → `gateway-sg` → `services-sg` → `rds-sg`.
  NACLs repeat the rules at subnet level.

![VPC resource map](screenshots/04-vpc-resource-map.png)
![Subnets](screenshots/04-vpc-subnets.png)
![Route tables](screenshots/05-route-tables.png)
![Security groups](screenshots/06-security-groups.png)
![Network ACLs](screenshots/07-network-acls.png)
![VPC endpoints](screenshots/08-vpc-endpoints.png)

## 3. Data

- **RDS PostgreSQL** `teampulse-db`: db.t4g.micro, Single-AZ, encrypted, **public access: No**, data
  subnets only, `rds-sg`. Five databases, each with its own login. TLS is required (`rds.force_ssl = 1`).
- **DynamoDB** `teampulse-analytics`: keys `pk` / `sk`, on-demand capacity, TTL on `expires_at`.
  Written only by the Lambda, read only by insight-service.

![RDS](screenshots/09-rds.png)
![DynamoDB](screenshots/10-dynamodb.png)

## 4. Container images (ECR)

- 8 private repositories: 7 services + the Lambda image.
- Tag immutability on, scan on push on, keep the last 3 images.

![ECR repositories](screenshots/11-ecr.png)
![ECR repositories (continued)](screenshots/11-ecr-more.png)

## 5. Compute (ECS, ALB, Lambda)

- **ECS cluster** `teampulse` (Fargate, Service Connect namespace `teampulse.local`), 7 services in the
  private app subnets, no public IPs, 0.25 vCPU / 0.5 GB each, Fargate Spot.
- **Auto scaling:** 1–2 tasks per service on CPU 60 %; the gateway also on ALB requests per target.
- **Task definitions:** plain settings as environment variables, secrets from Secrets Manager
  (`valueFrom`), non-root user, read-only root filesystem, health check `/health/live`.
- **ALB** `teampulse-alb`: listener HTTP:80, default answer **403**; forwards to the gateway only when
  the CloudFront secret header is present.
- **Lambda** `teampulse-streak-processor`: container image, inside the VPC (app subnets), 512 MB,
  30 s timeout, 2 retries, failures go to an SQS dead-letter queue.

![ECS services](screenshots/12-ecs-services.png)
![ECS auto scaling](screenshots/13-ecs-autoscaling.png)
![Task definition: environment variables](screenshots/14-task-definition-env.png)
![Task definition: secrets, non-root user, read-only file system](screenshots/14-task-definition.png)
![ALB listener rules](screenshots/15-alb-listener-rules.png)
![Target group health](screenshots/16-target-group.png)
![Lambda](screenshots/17-lambda.png)

## 6. Messaging (EventBridge, SQS)

- Bus `teampulse-events` with 4 rules: to challenge, notification and habit queues, and to the Lambda.
- SQS queues `teampulse-{challenge,notification,habit}-events`, each with a dead-letter queue after
  5 failed receives; long polling 20 s.
- EventBridge Scheduler sends `reminder.tick` every hour for habit reminders.

![EventBridge rules](screenshots/18-eventbridge-rules.png)
![EventBridge Scheduler](screenshots/19-eventbridge-scheduler.png)
![SQS queues](screenshots/20-sqs.png)

## 7. Frontend (S3 + CloudFront)

- S3 bucket `teampulse-frontend-<account-id>`: **block all public access on**, readable only by
  CloudFront (Origin Access Control).
- CloudFront: HTTPS for viewers, security headers, SPA rewrite function; `/api/*` and
  `/.well-known/*` go to the ALB with caching off.

![S3 bucket objects](screenshots/21-s3-bucket-objects.png)
![S3 bucket permissions](screenshots/21-s3-bucket.png)
![CloudFront behaviours](screenshots/22-cloudfront.png)

## 8. Monitoring (CloudWatch)

- One log group per service (`/ecs/teampulse/<service>`) with JSON logs carrying a `request_id`.
- Dashboard `TeamPulse`; 10 alarms (API latency, 5xx errors, login failures, queue depth, stuck
  queue, 4 dead-letter queues, Lambda errors) e-mail through SNS `teampulse-alerts`.
- An EventBridge rule e-mails when an ECS task stops (service restarts).
- To save credits, Container Insights and the services' own latency metrics (EMF) are off, so the
  dashboard's "ECS running tasks" and "Service latency" widgets stay empty. The free ALB, SQS, Lambda
  and RDS metrics fill the rest.

![CloudWatch dashboard](screenshots/23-cloudwatch-dashboard.png)
![CloudWatch dashboard (continued)](screenshots/23-cloudwatch-dashboard-lower.png)
![CloudWatch alarms](screenshots/24-cloudwatch-alarms.png)
![ECS task-stopped rule](screenshots/18-eventbridge-task-stopped-rule.png)
![Log groups](screenshots/25-log-groups.png)
![Same request ID in the gateway and service logs](screenshots/25-logs-insights.png)

## 9. The running application

![Login page](screenshots/26-app-login.png)
![Employee dashboard](screenshots/27-app-dashboard.png)
![Manager's aggregated team view](screenshots/28-app-team-insights.png)
![Team members and activity types](screenshots/28-app-team-insights-members.png)
