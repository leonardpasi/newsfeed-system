terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.2"
    }
  }

  required_version = ">= 1.2"
}

provider "aws" {
  region = var.aws_region
}
