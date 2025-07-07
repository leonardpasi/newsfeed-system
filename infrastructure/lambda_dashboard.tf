# CloudWatch Log Group for Dashboard Lambda
resource "aws_cloudwatch_log_group" "dashboard_lambda_logs" {
  name              = "/aws/lambda/newsfeed-dashboard-update"
  retention_in_days = 7
}

# IAM Role for Dashboard Lambda
resource "aws_iam_role" "dashboard_lambda_role" {
  name = "newsfeed-dashboard-lambda-role"

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

# IAM Policy for Dashboard Lambda
resource "aws_iam_role_policy" "dashboard_lambda_policy" {
  name = "newsfeed-dashboard-lambda-policy"
  role = aws_iam_role.dashboard_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.news_items.arn,
          "${aws_dynamodb_table.news_items.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.dashboard_bucket.arn}/*"
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

# Lambda function for dashboard updates
resource "aws_lambda_function" "dashboard_update" {
  filename         = "${path.module}/builds/dashboard_update_lambda.zip"
  function_name    = "newsfeed-dashboard-update"
  role            = aws_iam_role.dashboard_lambda_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.12"
  timeout         = 60
  memory_size     = 256

  source_code_hash = fileexists("${path.module}/builds/dashboard_update_lambda.zip") ? filebase64sha256("${path.module}/builds/dashboard_update_lambda.zip") : null

  environment {
    variables = {
      DYNAMODB_TABLE_NAME   = aws_dynamodb_table.news_items.name
      S3_BUCKET_NAME        = aws_s3_bucket.dashboard_bucket.bucket
      JSON_KEY              = "news-data.json"
      LOOKBACK_DAYS         = var.dashboard_lookback_days
      MIN_RELEVANCE_SCORE   = var.dashboard_min_relevance_score
    }
  }

  depends_on = [
    null_resource.build_dashboard_update_lambda,
    aws_cloudwatch_log_group.dashboard_lambda_logs,
    aws_iam_role_policy.dashboard_lambda_policy
  ]
}
