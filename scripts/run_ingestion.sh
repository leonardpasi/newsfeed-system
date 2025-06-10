#!/bin/bash
# scripts/run_ingestion.sh
# Wrapper script for running news ingestion via cron

set -e

# Configuration - ADJUST THESE PATHS FOR YOUR SETUP
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # Auto-detect project directory
LOG_DIR="$PROJECT_DIR/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to run ingestion for a source
run_ingestion() {
    local source=$1
    local log_file="$LOG_DIR/${source}.log"

    log "Starting ingestion for $source" >> "$log_file"

    # Change to project directory
    cd "$PROJECT_DIR"

    # Run the ingestion with all options using Poetry
    if ~/.local/bin/poetry run python -m scripts.main \
        --src "$source" \
        --store \
        --filter \
        --generate-json \
        --upload-s3 \
        --max-items 50 \
        --min-score 3.0 >> "$log_file" 2>&1; then

        log "Successfully completed ingestion for $source" >> "$log_file"
        echo "SUCCESS" > "$LOG_DIR/${source}.status"
    else
        log "ERROR: Failed ingestion for $source" >> "$log_file"
        echo "FAILED" > "$LOG_DIR/${source}.status"

        # Optional: Send alert (email, Slack, etc.)
        # echo "News ingestion failed for $source at $(date)" | mail -s "Ingestion Alert" your-email@domain.com
    fi

    log "Finished processing $source" >> "$log_file"
}

# Main execution
if [ $# -eq 0 ]; then
    echo "Usage: $0 <source_name>"
    echo "Available sources: tomshardware, arstechnica"
    exit 1
fi

SOURCE=$1

# Validate source
case $SOURCE in
    tomshardware|arstechnica)
        run_ingestion "$SOURCE"
        ;;
    *)
        echo "Invalid source: $SOURCE"
        echo "Available sources: tomshardware, arstechnica"
        exit 1
        ;;
esac
