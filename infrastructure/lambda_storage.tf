# CloudWatch Log Group for Storage Lambda
resource "aws_cloudwatch_log_group" "storage_lambda_logs" {
  name              = "/aws/lambda/newsfeed-storage"
  retention_in_days = 7
}

# IAM Role for Storage Lambda
resource "aws_iam_role" "storage_lambda_role" {
  name = "newsfeed-storage-lambda-role"

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

# IAM Policy for Storage Lambda
resource "aws_iam_role_policy" "storage_lambda_policy" {
  name = "newsfeed-storage-lambda-policy"
  role = aws_iam_role.storage_lambda_role.id

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
        Resource = aws_sqs_queue.filtered_news.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem"
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
resource "aws_lambda_function" "storage" {
  filename         = "${path.module}/builds/storage_lambda.zip"
  function_name    = "newsfeed-storage"
  role            = aws_iam_role.storage_lambda_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.12"
  timeout         = 60   # 1 minute should be enough for batch DynamoDB writes
  memory_size     = 256  # Minimal memory for simple storage operations

  source_code_hash = fileexists("${path.module}/builds/storage_lambda.zip") ? filebase64sha256("${path.module}/builds/storage_lambda.zip") : null

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.news_items.name
    }
  }

  depends_on = [
    null_resource.build_storage_lambda,
    aws_cloudwatch_log_group.storage_lambda_logs,
    aws_iam_role_policy.storage_lambda_policy
  ]
}

# SQS Event Source Mapping - triggers Lambda from filtered_news queue
resource "aws_lambda_event_source_mapping" "filtered_news_trigger" {
  event_source_arn = aws_sqs_queue.filtered_news.arn
  function_name    = aws_lambda_function.storage.arn
  batch_size       = 10

  # Quick processing for storage operations
  maximum_batching_window_in_seconds = 1
}

# Lambda permission for SQS to invoke the function
resource "aws_lambda_permission" "allow_sqs_filtered_news" {
  statement_id  = "AllowExecutionFromSQSFilteredNews"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.storage.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = aws_sqs_queue.filtered_news.arn
}
