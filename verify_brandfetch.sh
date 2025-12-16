#!/bin/bash

# Script to verify Brandfetch API service is working correctly
# Usage: ./verify_brandfetch.sh [BRANDFETCH_URL] [AUTH_TOKEN]

BRANDFETCH_URL=${1:-"http://localhost:8095"}
AUTH_TOKEN=${2:-""}

echo "🔍 Verifying Brandfetch API Service..."
echo "📍 URL: $BRANDFETCH_URL"
echo ""

# Check if service is running (health endpoint)
echo "1. Checking health endpoint..."
HEALTH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BRANDFETCH_URL/health" 2>/dev/null)
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | sed '/HTTP_CODE/d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Health check passed: $HEALTH_BODY"
else
    echo "❌ Health check failed (HTTP $HTTP_CODE)"
    echo "   Response: $HEALTH_BODY"
    echo ""
    echo "   Make sure the Brandfetch service is running:"
    echo "   cd services/workflow-service/BrandfetchAPI"
    echo "   uvicorn app.main:app --reload --port 8095"
    exit 1
fi

echo ""

# Test fetching a brand (requires auth token)
if [ -z "$AUTH_TOKEN" ]; then
    echo "⚠️  No auth token provided. Skipping authenticated endpoint test."
    echo "   To test the /brands/fetch endpoint, run:"
    echo "   ./verify_brandfetch.sh $BRANDFETCH_URL YOUR_AUTH_TOKEN"
    exit 0
fi

echo "2. Testing /brands/fetch endpoint with teems.ai..."
FETCH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST "$BRANDFETCH_URL/brands/fetch" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"url": "teems.ai", "force_refresh": false}' \
    2>/dev/null)

HTTP_CODE=$(echo "$FETCH_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
FETCH_BODY=$(echo "$FETCH_RESPONSE" | sed '/HTTP_CODE/d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Brand fetch successful!"
    echo "   Response preview: $(echo "$FETCH_BODY" | head -c 200)..."
else
    echo "❌ Brand fetch failed (HTTP $HTTP_CODE)"
    echo "   Response: $FETCH_BODY"
    echo ""
    echo "   Possible issues:"
    echo "   - Invalid auth token"
    echo "   - Brandfetch API key not configured"
    echo "   - Database connection issue"
    exit 1
fi

echo ""
echo "✅ All checks passed! Brandfetch API service is working correctly."

