output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "postgres_endpoint" {
  value     = aws_db_instance.postgres.endpoint
  sensitive = true
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "documents_bucket" {
  value = aws_s3_bucket.documents.bucket
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.backend.name
}
