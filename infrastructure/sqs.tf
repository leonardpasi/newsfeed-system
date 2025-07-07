# Dead Letter Queue for failed message processing
resource "aws_sqs_queue" "raw_news_dlq" {
  name = "newsfeed-raw-news-dlq"

  # Keep failed messages for investigation
  message_retention_seconds = 1209600  # 14 days

}

# Main queue for raw news items from ingestion
resource "aws_sqs_queue" "raw_news" {
  name = "newsfeed-raw-news"

  # Lambda timeout should be less than visibility timeout
  visibility_timeout_seconds = 60

  # Keep messages for 14 days if not processed
  message_retention_seconds = 1209600  # 14 days

  # Send to DLQ after 3 failed attempts
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.raw_news_dlq.arn
    maxReceiveCount     = 3
  })

}

# Output the queue URL for Lambda environment variable
output "raw_news_queue_url" {
  description = "URL of the raw news SQS queue"
  value       = aws_sqs_queue.raw_news.url
}

output "raw_news_dlq_url" {
  description = "URL of the dead letter queue"
  value       = aws_sqs_queue.raw_news_dlq.url
}

# Queue for news items that passed deduplication
resource "aws_sqs_queue" "new_news_dlq" {
  name = "newsfeed-new-news-dlq"
  message_retention_seconds = 1209600  # 14 days
}

resource "aws_sqs_queue" "new_news" {
  name = "newsfeed-new-news"

  visibility_timeout_seconds = 60
  message_retention_seconds = 1209600  # 14 days

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.new_news_dlq.arn
    maxReceiveCount     = 3
  })
}

# Output for Lambda environment variable
output "new_news_queue_url" {
  description = "URL of the new news SQS queue"
  value       = aws_sqs_queue.new_news.url
}

# Dead Letter Queue for filtered news processing
resource "aws_sqs_queue" "filtered_news_dlq" {
  name = "newsfeed-filtered-news-dlq"
  message_retention_seconds = 1209600  # 14 days
}

# Queue for news items that passed LLM filtering
resource "aws_sqs_queue" "filtered_news" {
  name = "newsfeed-filtered-news"

  visibility_timeout_seconds = 60
  message_retention_seconds = 1209600  # 14 days

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.filtered_news_dlq.arn
    maxReceiveCount     = 3
  })
}

# Output for Lambda environment variable
output "filtered_news_queue_url" {
  description = "URL of the filtered news SQS queue"
  value       = aws_sqs_queue.filtered_news.url
}

output "filtered_news_dlq_url" {
  description = "URL of the filtered news dead letter queue"
  value       = aws_sqs_queue.filtered_news_dlq.url
}
