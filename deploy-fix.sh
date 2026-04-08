#!/bin/bash

# Deployment script for be_thue_bot fixes
# This script deploys the fixes for the memory leak and silent failure issues

set -e

echo "🚀 Deploying be_thue_bot fixes..."
echo "======================================"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found. Run this script from the TaxAssistant root directory."
    exit 1
fi

# 1. Build the updated gateway
echo "📦 Building updated gateway image..."
docker-compose build gateway

# 2. Stop and remove the old gateway container
echo "🛑 Stopping existing gateway container..."
docker-compose stop gateway || true
docker-compose rm -f gateway || true

# 3. Start the new gateway with updated configuration
echo "🚀 Starting updated gateway..."
docker-compose up -d gateway

# 4. Wait for gateway to be healthy
echo "⏳ Waiting for gateway to become healthy..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker-compose ps gateway | grep -q "(healthy)"; then
        echo "✅ Gateway is healthy!"
        break
    fi
    
    echo "   Waiting... ($((WAITED+1))s/$MAX_WAIT)"
    sleep 1
    WAITED=$((WAITED+1))
    
    if [ $WAITED -eq $MAX_WAIT ]; then
        echo "❌ Gateway did not become healthy within $MAX_WAIT seconds"
        echo "📋 Checking logs..."
        docker-compose logs gateway --tail=20
        exit 1
    fi
done

# 5. Run health check
echo "🏥 Running health check..."
HEALTH_CHECK_URL="http://localhost:3000/health"
if command -v curl &> /dev/null; then
    curl -s -f "$HEALTH_CHECK_URL" | jq . || curl -s "$HEALTH_CHECK_URL"
elif command -v wget &> /dev/null; then
    wget -q -O - "$HEALTH_CHECK_URL" | jq . || wget -q -O - "$HEALTH_CHECK_URL"
else
    echo "⚠️  Could not run health check (curl/wget not available)"
fi

# 6. Check memory monitor status
echo "🧠 Checking memory monitor status..."
MEMORY_CHECK_URL="http://localhost:3000/health/memory"
if command -v curl &> /dev/null; then
    curl -s "$MEMORY_CHECK_URL" | jq . || curl -s "$MEMORY_CHECK_URL"
elif command -v wget &> /dev/null; then
    wget -q -O - "$MEMORY_CHECK_URL" | jq . || wget -q -O - "$HEALTH_CHECK_URL"
fi

# 7. Show container status
echo "📊 Container status:"
docker-compose ps

# 8. Show resource usage
echo "📈 Resource usage:"
docker stats --no-stream $(docker-compose ps -q gateway) 2>/dev/null || echo "⚠️  Could not get container stats"

# 9. Create monitoring instructions
echo ""
echo "======================================"
echo "✅ Deployment complete!"
echo ""
echo "📋 Monitoring endpoints:"
echo "   • Health check: http://localhost:3000/health"
echo "   • Live check:   http://localhost:3000/health/live"
echo "   • Metrics:      http://localhost:3000/health/metrics"
echo "   • Memory:       http://localhost:3000/health/memory"
echo ""
echo "🔍 To monitor the bot:"
echo "   1. Check logs: docker-compose logs -f gateway"
echo "   2. Monitor memory: watch -n 60 'curl -s http://localhost:3000/health/memory | jq .'"
echo "   3. Test /start command: Send '/start' to the bot"
echo "   4. Test regular message: Send 'Chạy chưa?' to the bot"
echo ""
echo "🚨 Alerting setup (recommended):"
echo "   • Monitor HTTP 200 status from /health endpoint"
echo "   • Alert if memory usage > 400MB for > 5 minutes"
echo "   • Alert if circuit breaker is OPEN for > 1 minute"
echo "   • Alert if bot doesn't respond within 5 seconds"
echo ""
echo "🔄 Auto-restart configuration (in docker-compose.yml):"
echo "   • restart: unless-stopped"
echo "   • healthcheck: configured"
echo "   • resource limits: memory:512M, cpus:1.0"
echo ""
echo "🐛 Debugging tips:"
echo "   • Check error logs: docker-compose logs gateway --tail=100 | grep -i error"
echo "   • Monitor Redis connections: docker-compose exec redis redis-cli info clients"
echo "   • Check gRPC connectivity: Look for 'circuit breaker' in logs"
echo "   • Test with different message types to ensure no silent failures"
echo ""
echo "📝 Fixes applied:"
echo "   1. ✅ Fixed /start command error handling"
echo "   2. ✅ Added comprehensive logging for all messages"
echo "   3. ✅ Implemented circuit breaker for gRPC calls"
echo "   4. ✅ Added memory leak monitoring and prevention"
echo "   5. ✅ Added Docker resource limits"
echo "   6. ✅ Enhanced health check endpoints"
echo "   7. ✅ Fixed Redis connection pooling in health checks"
echo "   8. ✅ Added automatic recovery mechanisms"
echo ""
echo "🎯 Next steps:"
echo "   1. Test the bot thoroughly with various messages"
echo "   2. Monitor for 24 hours to ensure no crashes"
echo "   3. Set up external monitoring (UptimeRobot, etc.)"
echo "   4. Configure alerts for any issues"
echo ""
echo "💡 For immediate testing:"
echo "   Send '/start' and 'Chạy chưa?' to verify fixes work"
echo "======================================"