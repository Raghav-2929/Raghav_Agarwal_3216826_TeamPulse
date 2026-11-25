# Demo recording

**Recording:** `<add the link here>`

GitHub refuses files over 100 MB, and a 5–10 minute screen recording is usually bigger. Upload it to
OneDrive, Google Drive or YouTube (unlisted), share it with "anyone with the link", and paste the link
above. A small file (under 100 MB) can also go in this folder as `teampulse-demo.mp4`.

## Suggested running order (about 8 minutes)

| Time | Show | Point out |
|---|---|---|
| 0:00 | Network diagram ([../network-architecture.md](../network-architecture.md)) | the 3 tiers, how a request travels |
| 0:45 | The app at `https://<cloudfront-domain>`: log in as an employee | HTTPS, dashboard tiles, today's habits, charts |
| 1:45 | Add a new habit, then **Mark complete** | streak, badge and challenge score update a moment later |
| 2:45 | Log in as a manager → **Team insights** | aggregated data only, hidden small days |
| 3:15 | VPC: subnets, route tables, security groups, NACLs | private app and data subnets, no internet route for data |
| 4:00 | ECS: cluster, services, a task definition, auto scaling | Fargate, Service Connect, secrets from Secrets Manager |
| 4:45 | ALB listener rules and target group | 403 unless the request comes from CloudFront |
| 5:15 | RDS and DynamoDB | public access No, TLS, on-demand table |
| 5:45 | EventBridge rules, SQS queues, Lambda | event routing, dead-letter queues, Lambda trigger |
| 6:30 | S3 + CloudFront | private bucket, `/api/*` behaviour |
| 7:00 | IAM roles, Secrets Manager, ECR | one role per service, immutable image tags |
| 7:30 | CloudWatch: dashboard, alarms, Logs Insights | follow one `request_id` through every service |
