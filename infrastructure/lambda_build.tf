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
