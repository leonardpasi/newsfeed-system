#!/bin/bash

# Usage: ./test_api.sh <mock_api_url>

URL=$1

curl -X POST  ${URL}/ingest \
  -H "Content-Type: application/json" \
  -d '[
    {
      "id": "test-high-001",
      "source": "synthetic",
      "title": "Critical Security Vulnerability Found in Enterprise Software",
      "body": "A critical security vulnerability has been discovered that could lead to system breaches and data loss.",
      "published_at": "2025-06-09T10:00:00Z"
    },
    {
      "id": "test-medium-002",
      "source": "synthetic",
      "title": "Major Network Infrastructure Update Released",
      "body": "New software update for network infrastructure includes important bug fixes and performance improvements.",
      "published_at": "2025-06-09T09:30:00Z"
    },
    {
      "id": "test-low-003",
      "source": "synthetic",
      "title": "New Gaming Laptop Announced",
      "body": "Consumer electronics company releases new gaming laptop with improved graphics card.",
      "published_at": "2025-06-09T09:00:00Z"
    }
  ]'

curl ${URL}/retrieve
