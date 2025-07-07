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

  attribute {
  name = "item_type"
  type = "S"
}

  # GSI for dashboard queries - get articles by timestamp
  global_secondary_index {
    name      = "recent-articles-index"
    hash_key  = "item_type"
    range_key = "published_at"

    projection_type = "ALL"
  }

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
