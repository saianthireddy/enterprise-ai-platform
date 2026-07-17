variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "enterprise-ai-platform"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "backend_image" {
  description = "ECR image URI for the FastAPI backend"
  type        = string
}

variable "frontend_image" {
  description = "ECR image URI for the Next.js frontend"
  type        = string
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.medium"
}

variable "desired_backend_count" {
  type    = number
  default = 3
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the ALB HTTPS listener"
  type        = string
}
