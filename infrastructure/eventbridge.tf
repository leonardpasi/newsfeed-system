# EventBridge rule for Tom's Hardware ingestion (daily at 8:00 AM UTC)
resource "aws_cloudwatch_event_rule" "tomshardware_schedule" {
  name                = "newsfeed-tomshardware-schedule"
  description         = "Trigger Tom's Hardware ingestion twice a month"
  schedule_expression = "cron(0 8 1,15 * ? *)"
}

# EventBridge rule for Ars Technica ingestion (daily at 8:30 AM UTC)
resource "aws_cloudwatch_event_rule" "arstechnica_schedule" {
  name                = "newsfeed-arstechnica-schedule"
  description         = "Trigger Ars Technica ingestion twice a month"
  schedule_expression = "cron(20 8 1,15 * ? *)"
}

# EventBridge rule for Reddit ingestion (daily at 9:00 AM UTC)
resource "aws_cloudwatch_event_rule" "reddit_schedule" {
  name                = "newsfeed-reddit-schedule"
  description         = "Trigger Reddit ingestion twice a month"
  schedule_expression = "cron(40 8 1,15 * ? *)"
}

# EventBridge target for Tom's Hardware
resource "aws_cloudwatch_event_target" "tomshardware_target" {
  rule      = aws_cloudwatch_event_rule.tomshardware_schedule.name
  target_id = "TomHardwareLambdaTarget"
  arn       = aws_lambda_function.ingestion.arn

  input = jsonencode({
    source = "tomshardware"
  })
}

# EventBridge target for Ars Technica
resource "aws_cloudwatch_event_target" "arstechnica_target" {
  rule      = aws_cloudwatch_event_rule.arstechnica_schedule.name
  target_id = "ArsTechnicaLambdaTarget"
  arn       = aws_lambda_function.ingestion.arn

  input = jsonencode({
    source = "arstechnica"
  })
}

# EventBridge target for Reddit
resource "aws_cloudwatch_event_target" "reddit_target" {
  rule      = aws_cloudwatch_event_rule.reddit_schedule.name
  target_id = "RedditLambdaTarget"
  arn       = aws_lambda_function.ingestion.arn

  input = jsonencode({
    source = "r-infosecnews"
  })
}

# Lambda permissions for EventBridge to invoke the function
resource "aws_lambda_permission" "allow_eventbridge_tomshardware" {
  statement_id  = "AllowExecutionFromEventBridgeTomHardware"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.tomshardware_schedule.arn
}

resource "aws_lambda_permission" "allow_eventbridge_arstechnica" {
  statement_id  = "AllowExecutionFromEventBridgeArsTechnica"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.arstechnica_schedule.arn
}

resource "aws_lambda_permission" "allow_eventbridge_reddit" {
  statement_id  = "AllowExecutionFromEventBridgeReddit"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reddit_schedule.arn
}
