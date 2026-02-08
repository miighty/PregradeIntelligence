# PreGrade API — AWS CDK (deployable IaC)

This CDK app deploys a **real** API backend (no Netlify stub) using:
- **Lambda (container image)** for the Python API handler
- **API Gateway HTTP API** (optional, but recommended for a stable `/v1/*` surface)
- **S3 bucket** (optional; placeholder for uploads)

## Prereqs
- AWS account + credentials configured (recommended: AWS SSO or access keys)
- Node.js 18+ (you have Node 22)
- Docker running (for Lambda container image build)

## Install
```bash
cd infrastructure/cdk-pregrade-api
npm i
```

## Deploy (dev)
```bash
# Set your AWS env (example)
export AWS_PROFILE=default
export AWS_REGION=eu-west-2

# Bootstrap once per account/region
npx cdk bootstrap

# Deploy
npx cdk deploy
```

## Outputs
- API base URL (HTTP API)
- Bucket name

## Notes
- The Lambda image is built from `infrastructure/cdk-pregrade-api/docker/`.
- The handler is `api/handler.lambda_handler` from the repo.
- Update env vars in the stack (`PREGRADE_API_KEYS`, rate limits, etc.) before real external use.
