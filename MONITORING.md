# Monitoring Setup for be_thue_bot

This document describes the monitoring setup for the be_thue_bot Telegram bot after implementing the fixes for memory leaks and silent failures.

## Health Endpoints

The following endpoints are available for monitoring:

### 1. Basic Health Check
```
GET http://localhost:3000/health
```
Returns overall health status with Redis connectivity check.

### 2. Liveness Probe
```
GET http://localhost:3000/health/live
```
Simple check if the server is running.

### 3. Detailed Metrics
```
GET http://localhost:3000/health/metrics
```
Returns detailed metrics including:
- Memory usage (RSS, heap, external)
- CPU usage
- Uptime
- Active handles/requests
- Memory monitor status

### 4. Memory Monitor Status
```
GET http://localhost:3000/health/memory
```
Returns memory monitor status including:
- Running state
- Thresholds
- Consecutive exceeded counts
- Last memory stats

## Alerting Configuration

### Critical Alerts (Immediate Action Required)

#### 1. Bot Not Responding
- **Condition**: HTTP 200 status from `/health/live` endpoint fails for 2 consecutive minutes
- **Action**: Restart service, check logs
- **Check frequency**: 30 seconds

#### 2. Memory Critical
- **Condition**: Memory usage > 450MB for 5 consecutive minutes
- **Action**: Investigate memory leak, restart if necessary
- **Check frequency**: 1 minute

#### 3. Circuit Breaker Open
- **Condition**: Circuit breaker in OPEN state for > 2 minutes
- **Action**: Check Tax Engine gRPC service, restart if needed
- **Check frequency**: 30 seconds

### Warning Alerts (Investigation Required)

#### 1. Memory Warning
- **Condition**: Memory usage > 350MB for 10 consecutive minutes
- **Action**: Monitor memory growth trend
- **Check frequency**: 5 minutes

#### 2. High Error Rate
- **Condition**: > 10 errors in logs within 5 minutes
- **Action**: Check error patterns, fix root cause
- **Check frequency**: 5 minutes

#### 3. Response Time Degradation
- **Condition**: Average response time > 5 seconds for 10 consecutive requests
- **Action**: Check system load, optimize queries
- **Check frequency**: 1 minute

## Monitoring Tools Setup

### 1. UptimeRobot (Free Tier)
```
Monitor Type: HTTP(s)
URL: https://your-domain.com/health/live
Check Interval: 1 minute
Alert Contacts: Email, Telegram
```

### 2. Prometheus + Grafana (Self-hosted)
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'be_thue_bot'
    static_configs:
      - targets: ['localhost:3000']
    metrics_path: '/health/metrics'
    scrape_interval: 30s
```

Grafana Dashboard Metrics:
- Memory usage over time
- Request rate
- Error rate
- Circuit breaker state
- Response time percentiles

### 3. Docker Container Monitoring
```bash
# Monitor container stats
docker stats be_thue_bot_gateway

# Monitor logs
docker-compose logs -f gateway --tail=100

# Check health status
docker inspect --format='{{.State.Health.Status}}' be_thue_bot_gateway
```

## Log Analysis

### Key Log Patterns to Monitor

#### 1. Successful Operations
```
✅ Processing message
✅ /start command processed successfully
✅ gRPC ProcessMessage OK
✅ Circuit breaker reset to CLOSED state
```

#### 2. Warning Patterns
```
⚠️  Memory thresholds exceeded
⚠️  Circuit breaker moving to HALF_OPEN state
⚠️  Customer profile resolution failed
⚠️  Tax Engine not available at startup
```

#### 3. Error Patterns
```
❌ Error processing /start command
❌ Error processing Telegram message
❌ gRPC ProcessMessage error
❌ Circuit breaker tripped to OPEN state
❌ Memory thresholds consistently exceeded
```

### Log Retention
- Keep 7 days of logs (rotate daily)
- Store error logs separately for 30 days
- Alert on error rate spikes

## Performance Baselines

### Normal Operation
- Memory usage: 100-250MB
- Response time: < 2 seconds
- Error rate: < 1%
- Uptime: > 99.9%

### Warning Thresholds
- Memory usage: > 300MB
- Response time: > 3 seconds
- Error rate: > 5%
- Circuit breaker: HALF_OPEN state

### Critical Thresholds
- Memory usage: > 400MB
- Response time: > 10 seconds
- Error rate: > 10%
- Circuit breaker: OPEN state for > 2 minutes

## Recovery Procedures

### 1. Bot Not Responding
```bash
# 1. Check if container is running
docker-compose ps gateway

# 2. Check logs for errors
docker-compose logs gateway --tail=50

# 3. Restart if necessary
docker-compose restart gateway

# 4. Verify recovery
curl -f http://localhost:3000/health/live
```

### 2. Memory Leak Detected
```bash
# 1. Check current memory usage
curl -s http://localhost:3000/health/memory | jq .

# 2. Check memory growth pattern
docker stats --no-stream be_thue_bot_gateway

# 3. Force garbage collection (if enabled)
# Already handled by memory monitor

# 4. Restart if memory > 450MB
docker-compose restart gateway
```

### 3. Circuit Breaker Open
```bash
# 1. Check Tax Engine service
docker-compose ps tax-engine

# 2. Check gRPC connectivity
docker-compose logs tax-engine --tail=20

# 3. Restart Tax Engine if needed
docker-compose restart tax-engine

# 4. Monitor circuit breaker recovery
# It will automatically reset after 30 seconds of no errors
```

### 4. Silent Message Failures
```bash
# 1. Check message processing logs
docker-compose logs gateway --tail=100 | grep -i "processing message"

# 2. Test with different message types
# Send: /start, regular message, command

# 3. Check error handling
docker-compose logs gateway --tail=100 | grep -i "error.*message"

# 4. Verify all messages are logged
# Look for "Received Telegram message" and "Processing message" pairs
```

## Testing Procedures

### Daily Health Check
```bash
./test-fixes.sh
```

### Weekly Load Test
```bash
# Simulate message load
for i in {1..100}; do
  echo "Test message $i" | send-to-telegram-bot
  sleep 0.5
done

# Monitor memory growth
watch -n 1 'curl -s http://localhost:3000/health/memory | jq .lastStats'
```

### Monthly Recovery Test
```bash
# 1. Simulate Tax Engine failure
docker-compose stop tax-engine

# 2. Verify circuit breaker opens
# Wait 2 minutes, check logs

# 3. Restart Tax Engine
docker-compose start tax-engine

# 4. Verify circuit breaker closes
# Wait for recovery, check logs
```

## Deployment Verification

After deploying fixes, verify:

1. ✅ All health endpoints respond correctly
2. ✅ Memory monitor is running
3. ✅ Circuit breaker is implemented
4. ✅ Error handling works for /start command
5. ✅ All messages are logged
6. ✅ Docker resource limits are set
7. ✅ Auto-restart policy is configured
8. ✅ Monitoring alerts are set up

## Success Metrics

The fixes are successful if:

1. **Uptime**: > 99.9% over 30 days
2. **Response Rate**: 100% of messages get responses (no silent failures)
3. **Stability**: No crashes after 10+ hours of operation
4. **Memory**: Stable memory usage under 400MB
5. **Recovery**: Automatic recovery from transient failures
6. **Monitoring**: All alerts trigger correctly
7. **Logging**: Complete audit trail for debugging

## Contact Information

- **Primary On-call**: [Your Name]
- **Backup**: [Backup Person]
- **Escalation**: [Manager]

## Emergency Procedures

1. **Immediate Service Outage**: Restart all containers
2. **Data Corruption**: Restore from backup
3. **Security Breach**: Isolate service, investigate
4. **Performance Degradation**: Scale resources, optimize

---

*Last updated: $(date)*
*Version: 1.0 - Memory leak and silent failure fixes*