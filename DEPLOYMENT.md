# Deployment Guide

## Prerequisites

- AWS CLI configured with credentials (`aws configure`)
- Node.js 18+ and npm
- Python 3.11+ with virtualenv set up at `bush-ranger-venv/`
- AWS CDK CLI installed (`npm install -g aws-cdk`) if not already installed

## Steps

### 1. Activate the virtualenv

```bash
source bush-ranger-venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Build the frontend

```bash
cd frontend && npm install && npm run build && cd ..
```

This produces `frontend/dist/` which the CDK stack deploys to S3.

### 4. Run linters and tests

```bash
make check-all
python -m pytest tests/ -v
cd frontend && npx vitest --run && cd ..
```

### 5. Bootstrap CDK (first time only)

Run once per AWS account/region. Creates the CDKToolkit stack with an S3 bucket and IAM roles needed for deployment.

```bash
cd infra && cdk bootstrap && cd ..
```

### 6. Synthesize (optional)

Preview the CloudFormation template before deploying:

```bash
cd infra && cdk synth && cd ..
```

### 7. Deploy

```bash
cd infra && cdk deploy && cd ..
```

CDK will show a summary of IAM changes and ask for confirmation. The stack outputs will display:

- CloudFront distribution URL (frontend)
- API Gateway endpoint URL
- Cognito User Pool ID and Client ID
- DynamoDB table name
- S3 bucket names

### 8. Create a ranger user

Self-signup is disabled. Create users via the AWS Console or CLI:

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username ranger@example.com \
  --temporary-password TempPass123! \
  --user-attributes Name=email,Value=ranger@example.com
```

The ranger will be prompted to set a permanent password on first sign-in.

## Teardown

```bash
cd infra && cdk destroy && cd ..
```

This removes all resources. The S3 buckets have `autoDeleteObjects` and `DESTROY` removal policy enabled for dev use.
