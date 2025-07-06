# Generic null resource for building Lambda functions
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
