#!/bin/bash

# Usage: ./build_lambda.sh <function_name>
# Example: ./build_lambda.sh ingestion

FUNCTION_NAME=$1

# Clean build
rm -rf builds/${FUNCTION_NAME}_lambda.zip builds/temp_${FUNCTION_NAME}
mkdir -p builds/temp_${FUNCTION_NAME}

# Copy shared code to root
cp -r ../lambda_functions/shared builds/temp_${FUNCTION_NAME}/

# Copy function-specific code to root
cp -r ../lambda_functions/${FUNCTION_NAME}/* builds/temp_${FUNCTION_NAME}/

# Install dependencies to root
if [ -f "builds/temp_${FUNCTION_NAME}/requirements.txt" ]; then
    cd builds/temp_${FUNCTION_NAME}
    uv pip install -r requirements.txt --target .
    cd ../..
fi

# Create ZIP from contents
cd builds/temp_${FUNCTION_NAME}
zip -r ../${FUNCTION_NAME}_lambda.zip .
cd ../..

# Cleanup
rm -rf builds/temp_${FUNCTION_NAME}
