variable "aws_region" {
    description = "region for aws resources"
    type = string
    default = "eu-central-2"
}

variable "reddit_app_id" {
    description = "needed for ingestion from subreddit"
    sensitive = true
    type = string
}

variable "reddit_app_secret" {
    description = "needed for ingestion from subreddit"
    sensitive = true
    type = string

}

variable "openai_api_key" {
    description = "needed for API calls to OpenAI for LLM-based relevance scoring"
    sensitive = true
    type = string
}

variable "relevance_score_threshold" {
    description = "news items with a relevance score heigher than threshold are stored to dynamodb, others are discarded"
    type = number
    default = 2.0
}

variable "dashboard_lookback_days" {
  description = "Number of days to look back for dashboard articles"
  type        = number
  default     = 20
}

variable "dashboard_min_relevance_score" {
  description = "Minimum relevance score for articles to appear in dashboard"
  type        = number
  default     = 3.0
}
