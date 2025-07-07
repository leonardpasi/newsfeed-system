# DynamoDB table for news items with simplified schema
resource "aws_dynamodb_table" "news_items" {
  name           = "news-items"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "published_at"
    type = "S"
  }

  # GSI for dashboard queries - get articles by timestamp
  global_secondary_index {
    name     = "published_at-index"
    hash_key = "published_at"

    projection_type = "ALL"
  }

  # Enable streams for dashboard updates (future step)
  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"

}

# Output table name for Lambda environment variables
output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.news_items.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.news_items.arn
}

output "dynamodb_stream_arn" {
  description = "ARN of the DynamoDB stream"
  value       = aws_dynamodb_table.news_items.stream_arn
}
