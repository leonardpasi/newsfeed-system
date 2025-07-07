# CloudWatch Log Group for LLM Scoring Lambda
resource "aws_cloudwatch_log_group" "llm_scoring_lambda_logs" {
  name              = "/aws/lambda/newsfeed-llm-scoring"
  retention_in_days = 7
}

# IAM Role for LLM Scoring Lambda
resource "aws_iam_role" "llm_scoring_lambda_role" {
  name = "newsfeed-llm-scoring-lambda-role"

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

# IAM Policy for LLM Scoring Lambda
resource "aws_iam_role_policy" "llm_scoring_lambda_policy" {
  name = "newsfeed-llm-scoring-lambda-policy"
  role = aws_iam_role.llm_scoring_lambda_role.id

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
        Resource = aws_sqs_queue.new_news.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.filtered_news.arn
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
resource "aws_lambda_function" "llm_scoring" {
  filename         = "${path.module}/builds/llm_scoring_lambda.zip"
  function_name    = "newsfeed-llm-scoring"
  role            = aws_iam_role.llm_scoring_lambda_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.12"
  timeout         = 300  # 5 minutes for OpenAI API calls
  memory_size     = 512  # More memory for AI processing

  source_code_hash =  fileexists("${path.module}/builds/llm_scoring_lambda.zip") ? filebase64sha256("${path.module}/builds/llm_scoring_lambda.zip") : null

  environment {
    variables = {
      FILTERED_NEWS_QUEUE_URL = aws_sqs_queue.filtered_news.url
      RELEVANCE_THRESHOLD     = tostring(var.relevance_score_threshold)
      OPENAI_API_KEY         = var.openai_api_key
    }
  }

  depends_on = [
    null_resource.build_llm_scoring_lambda,
    aws_cloudwatch_log_group.llm_scoring_lambda_logs,
    aws_iam_role_policy.llm_scoring_lambda_policy
  ]
}

# SQS Event Source Mapping - triggers Lambda from new_news queue
resource "aws_lambda_event_source_mapping" "new_news_trigger" {
  event_source_arn = aws_sqs_queue.new_news.arn
  function_name    = aws_lambda_function.llm_scoring.arn
  batch_size       = 10

  # Allow more time for batch processing due to OpenAI API calls
  maximum_batching_window_in_seconds = 5
}

# Lambda permission for SQS to invoke the function
resource "aws_lambda_permission" "allow_sqs_new_news" {
  statement_id  = "AllowExecutionFromSQSNewNews"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.llm_scoring.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = aws_sqs_queue.new_news.arn
}
