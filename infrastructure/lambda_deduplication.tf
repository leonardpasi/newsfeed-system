# CloudWatch Log Group for Deduplication Lambda
resource "aws_cloudwatch_log_group" "deduplication_lambda_logs" {
  name              = "/aws/lambda/newsfeed-deduplication"
  retention_in_days = 7
}

# IAM Role for Deduplication Lambda
resource "aws_iam_role" "deduplication_lambda_role" {
  name = "newsfeed-deduplication-lambda-role"

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

# IAM Policy for Deduplication Lambda
resource "aws_iam_role_policy" "deduplication_lambda_policy" {
  name = "newsfeed-deduplication-lambda-policy"
  role = aws_iam_role.deduplication_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.raw_news.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.new_news.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:BatchGetItem",
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.news_items.arn
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
resource "aws_lambda_function" "deduplication" {
  filename         = "${path.module}/builds/deduplication_lambda.zip"
  function_name    = "newsfeed-deduplication"
  role            = aws_iam_role.deduplication_lambda_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.12"
  timeout         = 60  # 1 minute should be enough for batch processing
  memory_size     = 256  # Minimal memory needed

  source_code_hash = filebase64sha256("${path.module}/builds/deduplication_lambda.zip")

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.news_items.name
      NEW_NEWS_QUEUE_URL  = aws_sqs_queue.new_news.url
    }
  }

  depends_on = [
    null_resource.build_deduplication_lambda,
    aws_cloudwatch_log_group.deduplication_lambda_logs,
    aws_iam_role_policy.deduplication_lambda_policy
  ]
}

# SQS Event Source Mapping - triggers Lambda from raw_news queue
resource "aws_lambda_event_source_mapping" "raw_news_trigger" {
  event_source_arn = aws_sqs_queue.raw_news.arn
  function_name    = aws_lambda_function.deduplication.arn
  batch_size       = 10

  # Only process messages that are at least 1 second old (helps with ordering)
  maximum_batching_window_in_seconds = 1
}

# Lambda permission for SQS to invoke the function
resource "aws_lambda_permission" "allow_sqs_raw_news" {
  statement_id  = "AllowExecutionFromSQSRawNews"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.deduplication.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = aws_sqs_queue.raw_news.arn
}
