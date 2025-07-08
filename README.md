# Newsfeed-system <!-- omit from toc -->
*A real-time newsfeed system that aggregates IT-related news from selected public sourcers, filters them for relevance, and provides a simple web dashboard to display the latest updates. Dashboard available [here](https://newsfeed-dashboard-3197d34e.s3.eu-central-2.amazonaws.com/dashboard.html).*

## Table of contents <!-- omit from toc -->
- [Legacy Architecture: EC2-based](#legacy-architecture-ec2-based)
- [New Architecture: AWS Lambda-based (Serverless)](#new-architecture-aws-lambda-based-serverless)
  - [Overview](#overview)
  - [Ingestion](#ingestion)
  - [Deduplication](#deduplication)
  - [LLM-based relevance scoring](#llm-based-relevance-scoring)
  - [Storage](#storage)
  - [Web dashboard update](#web-dashboard-update)
  - [Mock NewsFeed API](#mock-newsfeed-api)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Deploy Infrastructure](#deploy-infrastructure)
  - [Outputs](#outputs)
  - [Testing](#testing)


## Legacy Architecture: EC2-based
The original EC2-based implementation is preserved in the `/legacy` directory.
This system is no longer maintained but serves as reference for the original design.

## New Architecture: AWS Lambda-based (Serverless)

### Overview
```
  ┌─────────────┐            ┌───────────┐             ┌───────────┐  
  │ EventBridge │  triggers  │ Ingestion │  writes to  │ Raw News  │  
  │ (schedule)  ├────────────►  Lambda   │─────────────► SQS Queue │  
  └─────────────┘            └───────────┘             └─────┬─────┘  
                                                             │  
                                                             │triggers  
                                                             │  
  ┌─────────────┐            ┌───────────┐           ┌───────▼───────┐  
  │ LLM Scoring │  triggers  │ New News  │ writes to │ Deduplication │  
  │ Lambda      ◄────────────┤ SQS Queue ◄───────────┤    Lambda     │  
  └─────┬───────┘            └───────────┘           └───────┬───────┘  
        │                                                    │  
        │writes to                                           │checks  
        │                                                    │  
   ┌────▼─────┐               ┌─────────┐              ┌─────▼─────┐  
   │ Filtered │    triggers   │ Storage │  writes to   │ DynamoDB  │  
   │ News SQS ├───────────────► Lambda  ├──────────────► (Storage) │  
   └──────────┘               └────┬────┘              └───────────┘  
                                   │  
                                   │triggers  
                                   │  
                             ┌─────▼─────┐  
                             │ Dashboard │            ┌────────────────┐
                             │ Update    │ writes to  │ Dashboard data │
                             │ Lambda    ├────────────► S3 Bucket      │
                             └───────────┘            └────────────────┘

```

**Key Technologies**: AWS Lambda, SQS, DynamoDB, S3, EventBridge, API Gateway, OpenAI API, Terraform

### Ingestion
EventBridge triggers Lambda functions at given frequency (currently set to daily) to fetch news from:
- **RSS feeds**: Tom's Hardware, Ars Technica using `feedparser`
- **Reddit API**: r/InfoSecNews via PRAW
- Raw news items sent to SQS queue for processing

### Deduplication  
Lambda function processes SQS messages in batches, checks DynamoDB for existing article IDs using `batch_get_item`, and forwards only new items to the next queue. Deduplication is performed before the relevance scoring step to avoid evaluating the same articles multiple times.

### LLM-based relevance scoring
Lambda function scores news items using OpenAI GPT-4.1-nano on a 1-5 scale for IT manager relevance. Items scoring below threshold (default: 2.0) are filtered out. The threshold is declared as a terraform variable in `\infrastructure\variables.tf` and can easily be modified. The relevance scale is the following:

- 1 = Not relevant (consumer tech, general business news)
- 2 = Slightly relevant (minor updates, product announcements)
- 3 = Moderately relevant (software releases, industry trends)
- 4 = Highly relevant (security vulnerabilities, major outages)
- 5 = Critical (major security breaches, widespread outages, critical bugs)

Temperature is set to a low value for idempotency.

### Storage
Lambda function batch-writes filtered news items to DynamoDB with relevance scores and metadata. Triggers dashboard update after successful storage.

### Web dashboard update
Lambda function queries recent articles from DynamoDB, generates JSON data, and uploads to S3 bucket. The JSON contains all articles from the past N days, with a relevance score higher than T. N and T are declared as terraform variables as `dashboard_lookback_days` and `dashboard_min_relevance_score`, respectively. Static HTML dashboard hosted on S3 displays filtered news with client-side sorting and filtering.

### Mock NewsFeed API
HTTP API Gateway exposes `/ingest` and `/retrieve` endpoints for automated testing. Lambda function applies same LLM filtering logic (`lambda_functions/shared/filters/llm_filter.py`) to synthetic test data and stores results in dedicated S3 bucket.

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ API Gateway │───▶│ Mock API     │───▶│ Mock S3     │
│ (Testing)   │    │ Lambda       │    │ Storage     │
└─────────────┘    └──────────────┘    └─────────────┘
```

## Installation

### Prerequisites
- AWS CLI configured with appropriate permissions
- Terraform >= 1.2
- Python 3.12
- [uv](https://github.com/astral-sh/uv) (currently only used for building lambda functions)
- OpenAI API key
- Reddit app credentials (for subreddit ingestion)

### Environment Variables
Create `secrets.tfvars` in the `infrastructure/` directory:
```hcl
reddit_app_id = "your_reddit_app_id"
reddit_app_secret = "your_reddit_app_secret"  
openai_api_key = "your_openai_api_key"
```

### Deploy Infrastructure
```bash
cd infrastructure
terraform init
terraform plan -var-file="secrets.tfvars"
terraform apply -var-file="secrets.tfvars"
```
Note: due to the way lambda builds are automated with Terraform, the terraform apply command needs to be run twice. This will be fixed in the future.

### Outputs
After deployment, Terraform provides:
- Dashboard URL for viewing filtered news
- Mock API endpoints for automated testing
- S3 bucket names for static hosting and data storage

### Testing
The Mock Newsfeed API can be tested with the simple script `tests/test_api.sh`
```bash
./tests/test_api.sh <mock_api_url>
```
At this point, there are no automated tests. I plan to work on this soon.
