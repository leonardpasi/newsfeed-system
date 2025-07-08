# S3 bucket for dashboard hosting
resource "aws_s3_bucket" "dashboard_bucket" {
  bucket = "newsfeed-dashboard-${random_id.bucket_suffix.hex}"
}

# Random suffix for bucket name to ensure uniqueness
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# S3 bucket website configuration
resource "aws_s3_bucket_website_configuration" "dashboard_website" {
  bucket = aws_s3_bucket.dashboard_bucket.id

  index_document {
    suffix = "dashboard.html"
  }

  error_document {
    key = "error.html"
  }
}

# S3 bucket public access configuration
resource "aws_s3_bucket_public_access_block" "dashboard_bucket_pab" {
  bucket = aws_s3_bucket.dashboard_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# S3 bucket policy for public read access
resource "aws_s3_bucket_policy" "dashboard_bucket_policy" {
  bucket = aws_s3_bucket.dashboard_bucket.id

  depends_on = [aws_s3_bucket_public_access_block.dashboard_bucket_pab]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.dashboard_bucket.arn}/*"
      }
    ]
  })
}

# Upload the dashboard HTML file
resource "aws_s3_object" "dashboard_html" {
  bucket       = aws_s3_bucket.dashboard_bucket.bucket
  key          = "dashboard.html"
  source       = "${path.module}/../web-interface/dashboard.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/../web-interface/dashboard.html")
  cache_control = "public, max-age=300"
}

# Outputs
output "dashboard_url" {
  description = "URL of the news dashboard"
  value       = aws_s3_bucket_website_configuration.dashboard_website.website_endpoint
}

output "dashboard_bucket_name" {
  description = "Name of the S3 bucket hosting the dashboard"
  value       = aws_s3_bucket.dashboard_bucket.bucket
}
