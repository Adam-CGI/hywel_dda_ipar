# Performance Optimization Guide - Hywel Dda IPAR Document Miner

## Issues Identified

### 1. Slow LLM Response
**Problem**: GPT-4o-mini responses are slow  
**Root Cause**: 
- Low App Service tier (B1 - 1 core, 1.75GB RAM)
- No response streaming
- Synchronous request processing

### 2. Slow PDF Preview/Thumbnails  
**Problem**: Thumbnails load slowly or timeout
**Root Cause**:
- SAS token regenerated on every request (1-hour expiry)
- Synchronous thumbnail generation during upload
- No CDN or caching headers

### 3. Document Management Page Not Loading
**Problem**: Document list page loads but shows no documents
**Root Cause**:
- Cosmos DB serverless cold start latency (can be 5-10 seconds)
- Inefficient query selecting all fields (`SELECT * FROM c`)
- No timeout handling in frontend HTMX
- No indexing policy on frequently queried fields

## Optimizations Applied

### Infrastructure Changes (`deploy_hdipar_delta.ps1`)

#### 1. App Service Plan Upgrade
```powershell
# Changed from default (likely B1) to S1 Standard
az appservice plan create -g $ResourceGroup -n $WebPlan -l $Location --sku S1 --is-linux

# S1 Benefits:
# - Better CPU performance for LLM processing
# - Always-on capability (no cold starts)
# - Better concurrent request handling
# - Cost: ~$70/month (vs ~$13/month for B1)
```

**For Production**: Consider upgrading to P1V3 for 2 cores, 8GB RAM (~$150/month)

#### 2. Azure OpenAI Capacity Increase
```powershell
# Changed embedding deployment from 1 TPM to 120 TPM
--sku-capacity 120  # Was: 1

# Benefits:
# - 120x faster embedding throughput
# - Supports concurrent uploads
# - Cost: ~$10-30/month additional
```

#### 3. Cosmos DB Indexing Optimization
```json
{
  "indexingMode": "consistent",
  "includedPaths": [
    {"path": "/doc_id/?"},
    {"path": "/logical_id/?"},
    {"path": "/created_at/?"},
    {"path": "/is_deleted/?"},
    {"path": "/version/?"}
  ],
  "excludedPaths": [{"path": "/*"}]
}
```

**Benefits**:
- Faster queries (only index needed fields)
- Lower RU consumption
- Faster document listing

#### 4. App Service Configuration
```powershell
# Enable performance features
az webapp config set -g $ResourceGroup -n $Web `
  --always-on true `              # Prevents cold starts
  --http20-enabled true `         # HTTP/2 for better performance
  --min-tls-version 1.2           # Security + performance

# Production optimizations
PYTHON_ENABLE_GUNICORN_MULTIWORKERS=true  # Multiple workers
```

### Application Code Changes

#### 1. Optimized Cosmos DB Queries (`cosmos_service.py`)
```python
# BEFORE: Inefficient - selects all fields
SELECT TOP 100 * FROM c ORDER BY c.created_at DESC

# AFTER: Optimized - only needed fields
SELECT TOP 100 c.id, c.doc_id, c.logical_id, c.origin_filename, 
       c.version, c.page_count, c.created_at, c.updated_at, 
       c.is_deleted, c.superseded, c.source_uri
FROM c 
WHERE (NOT IS_DEFINED(c.is_deleted) OR c.is_deleted = false)
ORDER BY c.created_at DESC
```

**Benefits**:
- Reduced data transfer (smaller response size)
- Faster query execution
- Lower RU consumption

#### 2. Enhanced Error Handling (`documents.py`)
```python
# Added timeout tracking and graceful degradation
import time
start_time = time.time()
# ... processing ...
elapsed = time.time() - start_time
logger.info(f"Retrieved {len(documents)} documents in {elapsed:.2f}s")
```

**Benefits**:
- Better observability
- Graceful error messages for users
- No total page failures

#### 3. Thumbnail Caching (`documents.py`)
```python
# BEFORE: 1-hour SAS token expiry
sas_url = storage_service.generate_sas_url('thumbs', thumb_blob, expiry_hours=1)

# AFTER: 24-hour expiry with cache headers
sas_url = storage_service.generate_sas_url('thumbs', thumb_blob, expiry_hours=24)
response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours
```

**Benefits**:
- Browser caches thumbnails for 24 hours
- Fewer SAS token generations
- Faster page loads on repeat visits

## Performance Improvements Expected

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Document List Load | 10-30s | 2-5s | **5-10x faster** |
| LLM Response (first token) | 3-5s | 1-2s | **2-3x faster** |
| Thumbnail Load | 1-2s/each | <100ms (cached) | **10-20x faster** |
| Concurrent Uploads | 1-2 max | 10-20+ | **10x improvement** |
| Embedding Throughput | 1 TPM | 120 TPM | **120x faster** |

## Additional Optimizations (Not Yet Implemented)

### Priority: High
1. **Response Streaming for Chat**
   ```python
   # Enable streaming in ChatService
   response = self.client.chat.completions.create(
       model=self.deployment,
       messages=messages,
       stream=True  # Enable streaming
   )
   ```
   **Impact**: Perceived latency reduction of 50-70%

2. **Connection Pooling** 
   ```python
   # Add to config.py
   from azure.core.pipeline.transport import RequestsTransport
   transport = RequestsTransport(
       session=session,
       pool_connections=20,
       pool_maxsize=20
   )
   ```
   **Impact**: 20-30% faster Azure service calls

### Priority: Medium
3. **Azure CDN for Thumbnails**
   ```powershell
   # Add CDN endpoint in deployment
   az cdn endpoint create -g $ResourceGroup `
     --profile-name $CDN -n "$CDN-thumbs" `
     --origin "$SA.blob.core.windows.net" `
     --origin-path "/thumbs"
   ```
   **Impact**: 2-5x faster global thumbnail delivery
   **Cost**: ~$20-50/month

4. **Redis Cache for Document Metadata**
   ```python
   # Cache frequently accessed documents
   from azure.core.caching import redis_cache
   @redis_cache(ttl=300)  # 5 minute cache
   def get_document(doc_id):
       # ...
   ```
   **Impact**: 10-50x faster repeated document access
   **Cost**: ~$16/month (Basic C0)

### Priority: Low
5. **Async Upload Processing**
   - Move thumbnail generation to Azure Function
   - Queue-based background processing
   - Immediate upload response, background processing

## Deployment Instructions

### 1. Update Existing Deployment
```powershell
# Run updated deployment script
.\deploy_hdipar_delta.ps1 -SubscriptionId "<YOUR-SUB-ID>"

# The script is idempotent and will:
# - Upgrade App Service Plan to S1
# - Update OpenAI capacity to 120 TPM
# - Apply Cosmos indexing policy
# - Configure App Service settings
```

### 2. Verify Changes
```powershell
# Check App Service Plan
az appservice plan show -g RG_300000000120926_Hywel_Dda_AI -n asp-hdipar-dev

# Check OpenAI deployment
az cognitiveservices account deployment show `
  -g RG_300000000120926_Hywel_Dda_AI -n aoai-hdipar-dev `
  --deployment-name text-embedding-3-large
```

### 3. Deploy Code Changes
```bash
# Deploy updated application code
git push azure main

# Or via Azure CLI
az webapp up -g RG_300000000120926_Hywel_Dda_AI -n app-hdipar-dev
```

## Monitoring

### Key Metrics to Track
1. **App Service Metrics** (Azure Portal)
   - Response Time (target: <2s)
   - CPU Usage (target: <70%)
   - Memory Usage (target: <80%)
   - HTTP 5xx errors (target: <1%)

2. **Cosmos DB Metrics**
   - Request Units/sec (watch for throttling)
   - Query execution time (target: <500ms)
   - Availability (target: >99.9%)

3. **Application Insights**
   - `/api/documents` endpoint latency
   - Document upload pipeline duration
   - Chat response time

### Performance Queries (Application Insights)
```kusto
// Document list performance
requests
| where name == "GET /api/documents"
| summarize avg(duration), percentiles(duration, 50, 95, 99) by bin(timestamp, 1h)

// Slow requests (>5s)
requests
| where duration > 5000
| project timestamp, name, url, duration, resultCode
| order by duration desc
```

## Cost Impact

| Service | Before | After | Increase |
|---------|--------|-------|----------|
| App Service Plan | B1: $13/mo | S1: $70/mo | +$57/mo |
| Azure OpenAI | ~$10/mo | ~$20-40/mo | +$10-30/mo |
| Cosmos DB | ~$5-10/mo | ~$5-10/mo | $0 (same) |
| **Total** | **~$28/mo** | **~$95-120/mo** | **+$67-92/mo** |

**ROI**: 5-10x performance improvement for ~3-4x cost increase

## Rollback Plan

If performance degrades or costs are too high:

```powershell
# Downgrade App Service Plan to B1
az appservice plan update -g RG_300000000120926_Hywel_Dda_AI `
  -n asp-hdipar-dev --sku B1

# Reduce OpenAI capacity
az cognitiveservices account deployment create `
  -g RG_300000000120926_Hywel_Dda_AI -n aoai-hdipar-dev `
  --deployment-name text-embedding-3-large `
  --sku-capacity 10  # Moderate capacity
```

## Next Steps

1. ✅ Deploy infrastructure changes
2. ✅ Deploy application code updates
3. ⏳ Test document listing performance
4. ⏳ Test chat response times
5. ⏳ Monitor for 24-48 hours
6. ⏳ Implement response streaming (Priority High)
7. ⏳ Add connection pooling (Priority High)
8. ⏳ Consider CDN for production (Priority Medium)

## Support

For issues or questions:
- Check Application Insights logs
- Review deployment logs in `logs/` directory
- Contact: [Your Support Contact]
