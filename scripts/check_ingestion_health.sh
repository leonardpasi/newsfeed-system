#!/bin/bash
# scripts/check_ingestion_health.sh
# Monitor script to check the health of news ingestion cron jobs

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # Auto-detect project directory
LOG_DIR="$PROJECT_DIR/logs"

echo "📊 News Ingestion Health Check"
echo "=============================="
echo "Timestamp: $(date)"
echo ""

# Check if logs directory exists
if [ ! -d "$LOG_DIR" ]; then
    echo "❌ Log directory does not exist: $LOG_DIR"
    exit 1
fi

# Function to check source health
check_source() {
    local source=$1
    local log_file="$LOG_DIR/${source}.log"
    local status_file="$LOG_DIR/${source}.status"

    echo "🔍 Checking $source:"

    # Check if log file exists
    if [ ! -f "$log_file" ]; then
        echo "  ❌ No log file found"
        return
    fi

    # Check last run status
    if [ -f "$status_file" ]; then
        local last_status=$(cat "$status_file")
        if [ "$last_status" = "SUCCESS" ]; then
            echo "  ✅ Last run: SUCCESS"
        else
            echo "  ❌ Last run: FAILED"
        fi
    else
        echo "  ⚠️  No status file found"
    fi

    # Check last log entry time
    local last_log_time=$(tail -1 "$log_file" | grep -o '\[.*\]' | tr -d '[]' || echo "Unknown")
    echo "  📅 Last activity: $last_log_time"

    # Check log file size (to detect if it's growing too large)
    local log_size=$(du -h "$log_file" | cut -f1)
    echo "  📁 Log size: $log_size"

    # Show last few log entries
    echo "  📝 Recent logs:"
    tail -3 "$log_file" | sed 's/^/     /'

    echo ""
}

# Check each source
for source in tomshardware arstechnica r-infosecnews; do
    check_source "$source"
done

# Check if API server is running
echo "🚀 API Server Status:"
if pgrep -f "simple_api.py" > /dev/null; then
    echo "  ✅ API server is running"

    # Test health endpoint
    if curl -s http://localhost:5000/api/v1/health > /dev/null; then
        echo "  ✅ API health check passed"
    else
        echo "  ❌ API health check failed"
    fi
else
    echo "  ❌ API server is not running"
fi

echo ""

# Check disk space
echo "💾 Disk Usage:"
df -h / | grep -E '(Filesystem|/dev/)' | sed 's/^/  /'

echo ""

# Check recent DynamoDB activity (optional)
echo "🗄️  Database Status:"
echo "  📊 Checking recent ingestion activity..."

# Count recent items (last 24 hours) - requires AWS CLI
recent_count=$(python -c "
import boto3
from datetime import datetime, timedelta
import sys
try:
    dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
    table = dynamodb.Table('news-items')

    # Scan for recent items (simplified check)
    response = table.scan(
        FilterExpression='created_at > :yesterday',
        ExpressionAttributeValues={
            ':yesterday': (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z'
        },
        Select='COUNT'
    )
    print(response['Count'])
except Exception as e:
    print('ERROR')
" 2>/dev/null)

if [ "$recent_count" = "ERROR" ]; then
    echo "  ⚠️  Could not check database activity"
else
    echo "  📈 Items added in last 24h: $recent_count"
fi

echo ""
echo "✅ Health check complete!"
