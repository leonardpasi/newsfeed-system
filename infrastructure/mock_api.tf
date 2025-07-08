# S3 bucket for Mock API batch storage
resource "aws_s3_bucket" "mock_api_bucket" {
  bucket = "newsfeed-mock-api-${random_id.mock_api_suffix.hex}"
}

# Random suffix for bucket name uniqueness
resource "random_id" "mock_api_suffix" {
  byte_length = 4
}

# CloudWatch Log Group for Mock API Lambda
resource "aws_cloudwatch_log_group" "mock_api_lambda_logs" {
  name              = "/aws/lambda/newsfeed-mock-api"
  retention_in_days = 7
}

# IAM Role for Mock API Lambda
resource "aws_iam_role" "mock_api_lambda_role" {
  name = "newsfeed-mock-api-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Mock API Lambda
resource "aws_iam_role_policy" "mock_api_lambda_policy" {
  name = "newsfeed-mock-api-lambda-policy"
  role = aws_iam_role.mock_api_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.mock_api_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Lambda function for Mock API
resource "aws_lambda_function" "mock_api" {
  filename         = "${path.module}/builds/mock_api_lambda.zip"
  function_name    = "newsfeed-mock-api"
  role            = aws_iam_role.mock_api_lambda_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.12"
  timeout         = 300  # 5 minutes for OpenAI API calls
  memory_size     = 512  # More memory for LLM processing

  source_code_hash = fileexists("${path.module}/builds/mock_api_lambda.zip") ? filebase64sha256("${path.module}/builds/mock_api_lambda.zip") : null

  environment {
    variables = {
      S3_BUCKET_NAME        = aws_s3_bucket.mock_api_bucket.bucket
      S3_KEY               = "current-batch.json"
      RELEVANCE_THRESHOLD  = var.relevance_score_threshold
      OPENAI_API_KEY       = var.openai_api_key
    }
  }

  depends_on = [
    null_resource.build_mock_api_lambda,
    aws_cloudwatch_log_group.mock_api_lambda_logs,
    aws_iam_role_policy.mock_api_lambda_policy
  ]
}

# HTTP API Gateway
resource "aws_apigatewayv2_api" "mock_api" {
  name          = "newsfeed-mock-api"
  protocol_type = "HTTP"
  description   = "Mock Newsfeed API for automated testing"
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "mock_api" {
  api_id      = aws_apigatewayv2_api.mock_api.id
  name        = "v1"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.mock_api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      error          = "$context.error.message"
      responseLength = "$context.responseLength"
    })
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "mock_api_gateway_logs" {
  name              = "/aws/apigateway/newsfeed-mock-api"
  retention_in_days = 7
}

# Lambda integration
resource "aws_apigatewayv2_integration" "mock_api_lambda" {
  api_id = aws_apigatewayv2_api.mock_api.id

  integration_uri    = aws_lambda_function.mock_api.invoke_arn
  integration_type   = "AWS_PROXY"
  integration_method = "POST"
}

# POST /ingest route
resource "aws_apigatewayv2_route" "ingest" {
  api_id    = aws_apigatewayv2_api.mock_api.id
  route_key = "POST /ingest"
  target    = "integrations/${aws_apigatewayv2_integration.mock_api_lambda.id}"
}

# GET /retrieve route
resource "aws_apigatewayv2_route" "retrieve" {
  api_id    = aws_apigatewayv2_api.mock_api.id
  route_key = "GET /retrieve"
  target    = "integrations/${aws_apigatewayv2_integration.mock_api_lambda.id}"
}

# Lambda permission for API Gateway to invoke the function
resource "aws_lambda_permission" "mock_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.mock_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.mock_api.execution_arn}/*/*"
}

# Outputs
output "mock_api_url" {
  description = "URL of the Mock Newsfeed API"
  value       = "${aws_apigatewayv2_api.mock_api.api_endpoint}/v1"
}

output "mock_api_endpoints" {
  description = "Mock API endpoints for testing"
  value = {
    ingest   = "${aws_apigatewayv2_api.mock_api.api_endpoint}/v1/ingest"
    retrieve = "${aws_apigatewayv2_api.mock_api.api_endpoint}/v1/retrieve"
  }
}

output "mock_api_bucket_name" {
  description = "Name of the S3 bucket for Mock API storage"
  value       = aws_s3_bucket.mock_api_bucket.bucket
}
