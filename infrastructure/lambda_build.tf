# Build ingestion lambda
resource "null_resource" "build_ingestion_lambda" {
  provisioner "local-exec" {
    command = "chmod +x build_lambda.sh && ./build_lambda.sh ingestion"
    working_dir = path.module
  }

# Rebuild when code changes
  triggers = {
    code_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/ingestion", "**/*") :
      filesha256("${path.module}/../lambda_functions/ingestion/${f}")
    ]))
    shared_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/shared", "**/*") :
      filesha256("${path.module}/../lambda_functions/shared/${f}")
    ]))
  }
}

# Build deduplication lambda
resource "null_resource" "build_deduplication_lambda" {
  provisioner "local-exec" {
    command = "chmod +x build_lambda.sh && ./build_lambda.sh deduplication"
    working_dir = path.module
  }

  triggers = {
    code_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/deduplication", "**/*") :
      filesha256("${path.module}/../lambda_functions/deduplication/${f}")
    ]))
    shared_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/shared", "**/*") :
      filesha256("${path.module}/../lambda_functions/shared/${f}")
    ]))
  }
}

# Build LLM scoring lambda
resource "null_resource" "build_llm_scoring_lambda" {
  provisioner "local-exec" {
    command = "chmod +x build_lambda.sh && ./build_lambda.sh llm_scoring"
    working_dir = path.module
  }

  triggers = {
    code_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/llm_scoring", "**/*") :
      filesha256("${path.module}/../lambda_functions/llm_scoring/${f}")
    ]))
    shared_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/shared", "**/*") :
      filesha256("${path.module}/../lambda_functions/shared/${f}")
    ]))
  }
}

# Build storage lambda
resource "null_resource" "build_storage_lambda" {
  provisioner "local-exec" {
    command = "chmod +x build_lambda.sh && ./build_lambda.sh storage"
    working_dir = path.module
  }

  triggers = {
    code_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/storage", "**/*") :
      filesha256("${path.module}/../lambda_functions/storage/${f}")
    ]))
    shared_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/shared", "**/*") :
      filesha256("${path.module}/../lambda_functions/shared/${f}")
    ]))
  }
}

# Build dashboard update lambda
resource "null_resource" "build_dashboard_update_lambda" {
  provisioner "local-exec" {
    command = "chmod +x build_lambda.sh && ./build_lambda.sh dashboard_update"
    working_dir = path.module
  }

  triggers = {
    code_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/dashboard_update", "**/*") :
      filesha256("${path.module}/../lambda_functions/dashboard_update/${f}")
    ]))
    shared_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/shared", "**/*") :
      filesha256("${path.module}/../lambda_functions/shared/${f}")
    ]))
  }
}

# Build mock API lambda
resource "null_resource" "build_mock_api_lambda" {
  provisioner "local-exec" {
    command = "chmod +x build_lambda.sh && ./build_lambda.sh mock_api"
    working_dir = path.module
  }

  triggers = {
    code_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/mock_api", "**/*") :
      filesha256("${path.module}/../lambda_functions/mock_api/${f}")
    ]))
    shared_hash = sha256(join("", [
      for f in fileset("${path.module}/../lambda_functions/shared", "**/*") :
      filesha256("${path.module}/../lambda_functions/shared/${f}")
    ]))
  }
}
