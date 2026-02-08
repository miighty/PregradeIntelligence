# Lambda container image for PregradeIntelligence Python handler
# Uses AWS Lambda Python base image.
FROM public.ecr.aws/lambda/python:3.11

# Install python deps if you have a pinned requirements file.
# We copy repo requirements.txt (top-level) which already exists in this repo.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the minimal code needed for api handler
COPY api ./api
COPY domain ./domain
COPY services ./services
COPY data ./data

# Lambda entrypoint
CMD ["api.handler.lambda_handler"]
