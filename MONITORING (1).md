# API Sentinel: Monitoring and Cost Awareness

API Sentinel compares an old and a new OpenAPI/Swagger spec and flags breaking changes. This document covers how the deployment is monitored, one alert idea, and a short cost and access-control checklist.

## Deployment overview

| Layer | Service | Purpose |
|---|---|---|
| Frontend | S3 static hosting (optionally behind CloudFront) | Serves the HTML/CSS/JS app |
| API | API Gateway | Receives spec-comparison requests |
| Compute | Lambda | Runs the breaking-change diff logic |
| Storage | S3 (uploaded specs), DynamoDB (comparison history) | Stores specs and results |

## 1. Logs and status checks

**Logs**
- Lambda writes logs to CloudWatch Logs automatically (one log group per function). Each run logs the request ID, spec sizes, number of breaking changes found, and any error.
- API Gateway access logging is enabled to record method, path, status code and latency for every request.
- Specs and their contents are never logged, only sizes and counts.

**Status checks**
- *Uptime check:* an external monitor (UptimeRobot free tier, or a Route 53 health check) requests the site URL every 5 minutes and expects HTTP 200.
- *API health check:* a `GET /health` route on API Gateway, backed by Lambda, returns `{"status":"ok"}`. The same monitor checks it.
- *Manual smoke test (after every deploy):* open the site, upload two small sample specs (one with a removed endpoint), and confirm a breaking change is reported.

**Status check script (included in this repo):** `scripts/health_check.py` checks the frontend and the API `/health` endpoint, prints PASS/FAIL with response time, and exits non-zero on failure so it can run from cron or GitHub Actions.

```
SITE_URL=https://your-site SENTINEL_API_URL=https://your-api/health python scripts/health_check.py
```

**Metrics to watch in CloudWatch**
- Lambda: Invocations, Errors, Duration, Throttles
- API Gateway: 4XX count, 5XX count, Latency
- DynamoDB: Throttled requests, consumed capacity

## 2. Simple alert idea

**Alert: Lambda error spike**
- Condition: CloudWatch alarm on the Lambda `Errors` metric, 5 or more errors in 5 minutes.
- Action: send an email through an SNS topic.
- Why: this means users are hitting failures while comparing specs, and it is the most direct sign the product is broken.

**Implementation:** `infra/monitoring.yaml` is a CloudFormation template that creates the SNS email topic, this alarm, 14-day log retention, and a monthly cost budget alert.

```
aws cloudformation deploy --template-file infra/monitoring.yaml --stack-name api-sentinel-monitoring \
  --parameter-overrides AlertEmail=you@example.com LambdaFunctionName=api-sentinel-compare
```

**Optional second alert:** the uptime monitor emails me if the site or `/health` is down for more than 2 minutes.

## 3. Cost checklist

- [ ] Create an AWS Budget (for example $5/month) with email alerts at 50% and 100%.
- [ ] Enable Cost Explorer and check it weekly.
- [ ] Use DynamoDB on-demand billing, since traffic is low and unpredictable.
- [ ] Set CloudWatch log retention to 7-14 days, because the default "never expire" keeps accruing cost.
- [ ] Add an S3 lifecycle rule to delete uploaded specs after 30 days.
- [ ] Set a Lambda memory and timeout limit (for example 256 MB, 10 s) so a bad request cannot run up cost.
- [ ] Add API Gateway throttling (for example 10 requests/second) to prevent runaway usage.
- [ ] Delete unused resources (test buckets, old Lambda versions, unused tables).
- [ ] Stay within the free tier where possible (Lambda, API Gateway, DynamoDB, S3 all have one).

## 4. Access-control and security checklist

- [ ] Enable MFA on the root account and do not use root for daily work.
- [ ] Use least-privilege IAM roles. The Lambda role gets only read/write on its own S3 bucket and DynamoDB table, with no `*` permissions.
- [ ] Keep the S3 specs bucket private, with Block Public Access turned on. Only the static-site bucket is public (or served via CloudFront).
- [ ] Never commit access keys or secrets to GitHub. Use environment variables or AWS Secrets Manager, and add `.env` to `.gitignore`.
- [ ] Restrict CORS on API Gateway to the app's own domain instead of `*`.
- [ ] Limit upload size and validate that uploaded files are valid JSON/YAML OpenAPI specs.
- [ ] Use HTTPS only (CloudFront or API Gateway default endpoints).
- [ ] Review IAM users and roles monthly and remove anything unused.

## Review routine

| When | What |
|---|---|
| After each deploy | Run the manual smoke test |
| Weekly | Check Cost Explorer and CloudWatch error graphs |
| Monthly | Review IAM roles and S3 bucket policies |
