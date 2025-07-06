# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "ingestion_lambda_logs" {
  name              = "/aws/lambda/newsfeed-ingestion"
  retention_in_days = 7
}

# IAM Role for Lambda - declares a role that can only be assumed by lambda
resource "aws_iam_role" "ingestion_lambda_role" {
  name = "newsfeed-ingestion-lambda-role"

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

# IAM Policy for Lambda - SQS and Logs permissions
# Actually defines the permissions granted by the role
resource "aws_iam_role_policy" "ingestion_lambda_policy" {
  name = "newsfeed-ingestion-lambda-policy"
  role = aws_iam_role.ingestion_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.raw_news.arn
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

# Lambda function
resource "aws_lambda_function" "ingestion" {
  filename         = "${path.module}/builds/ingestion_lambda.zip"
  function_name    = "newsfeed-ingestion"
  role            = aws_iam_role.ingestion_lambda_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.12"
  timeout         = 300  # 5 minutes
  memory_size     = 512

# Calculate hash from the ZIP file created by the build script
  source_code_hash = filebase64sha256("${path.module}/builds/ingestion_lambda.zip")

  environment {
    variables = {
      SQS_QUEUE_URL     = aws_sqs_queue.raw_news.url
      REDDIT_APP_ID     = var.reddit_app_id
      REDDIT_APP_SECRET = var.reddit_app_secret
    }
  }

  depends_on = [
    null_resource.build_ingestion_lambda,
    aws_cloudwatch_log_group.ingestion_lambda_logs,
    aws_iam_role_policy.ingestion_lambda_policy
  ]
}

# Output Lambda function name for EventBridge rules
output "ingestion_lambda_arn" {
  description = "ARN of the ingestion Lambda function"
  value       = aws_lambda_function.ingestion.arn
}
