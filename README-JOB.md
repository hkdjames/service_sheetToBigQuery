# Sheet to BigQuery Job Architecture

## Overview

This document describes the converted job-based architecture for the Sheet to BigQuery service. The system has been migrated from a Flask service to individual Cloud Run Jobs for better scalability, reliability, and cost efficiency.

## Architecture Components

### 1. Cloud Run Job (`main.py`)
- **Purpose**: Execute individual sheet-to-BigQuery transfers
- **Input**: Environment variables containing configuration
- **Output**: BigQuery table with data from Google Sheets
- **Runtime**: Standalone Python process (no web server)

### 2. Job Orchestrator (`job_orchestrator.py`)
- **Purpose**: Fetch configurations from Postgres and trigger jobs
- **Features**: 
  - Frequency-based scheduling
  - Parallel job execution
  - Error handling and notifications
  - Database integration

### 3. Job Helper (`job_helper.py`)
- **Purpose**: Manual job management and testing
- **Features**:
  - Execute individual jobs
  - Monitor job status
  - Generate example configurations

## Files Structure

```
service_sheetToBigQuery/
├── main.py                     # Core ETL logic (job-compatible)
├── app.py                      # Original service (kept for backward compatibility)
├── job_orchestrator.py         # Orchestrates multiple jobs
├── job_helper.py              # Manual job management
├── Dockerfile                 # Original service container
├── Dockerfile.job            # Job-optimized container
├── cloudbuild.yaml           # Original service deployment
├── cloudbuild-job.yaml       # Job deployment
├── requirements.txt          # Service dependencies
├── requirements-job.txt      # Job dependencies (no Flask)
├── requirements-orchestrator.txt  # Orchestrator dependencies
└── README-JOB.md            # This documentation
```

## Deployment

### 1. Deploy the Cloud Run Job

```bash
# Build and deploy the job
gcloud builds submit --config cloudbuild-job.yaml --project=hkd-reporting
```

### 2. Set Up Job Orchestrator

The orchestrator can be deployed as:

**Option A: Cloud Run Service (Recommended)**
```bash
# Create orchestrator service
gcloud run deploy sheettobigquery-orchestrator \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars="POSTGRES_HOST=your-host,POSTGRES_DB=your-db,POSTGRES_USER=your-user" \
  --set-secrets="POSTGRES_PASSWORD=your-password-secret:latest"
```

**Option B: Cloud Scheduler + Cloud Functions**
```bash
# Deploy as Cloud Function triggered by Cloud Scheduler
gcloud functions deploy sheet-to-bigquery-orchestrator \
  --runtime python39 \
  --trigger-http \
  --allow-unauthenticated \
  --memory 512MB \
  --timeout 540s
```

**Option C: Manual Execution**
```bash
# Run orchestrator manually
python job_orchestrator.py \
  --postgres-host=your-host \
  --postgres-db=your-db \
  --postgres-user=your-user \
  --postgres-password=your-password \
  --dry-run  # Remove for actual execution
```

## Configuration

### Environment Variables (Job)

The job expects these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `CONFIG_ID` | No | Database configuration ID |
| `CONFIG_NAME` | Yes | Human-readable configuration name |
| `GOOGLE_SHEET_URL` | Yes | Full Google Sheets URL |
| `GOOGLE_SHEET_TAB_NAME` | No | Specific tab name (default: first tab) |
| `GOOGLE_CLOUD_PROJECT_ID` | Yes | Target BigQuery project |
| `BIGQUERY_DATASET_ID` | Yes | Target BigQuery dataset |
| `BIGQUERY_TABLE_ID` | Yes | Target BigQuery table |
| `SCHEMA_HANDLING` | No | "auto_detect" or "custom" (default: auto_detect) |
| `CUSTOM_SCHEMA` | No | JSON schema definition (if schema_handling=custom) |

### Database Schema (Postgres)

Expected table structure for job orchestrator:

```sql
CREATE TABLE sheet_to_bigquery_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    google_sheet_url TEXT NOT NULL,
    google_sheet_tab_name VARCHAR(255),
    google_cloud_project_id VARCHAR(255) NOT NULL,
    bigquery_dataset_id VARCHAR(255) NOT NULL,
    bigquery_table_id VARCHAR(255) NOT NULL,
    schema_handling VARCHAR(50) DEFAULT 'auto_detect',
    custom_schema JSONB,
    is_active BOOLEAN DEFAULT true,
    last_run TIMESTAMP WITH TIME ZONE,
    run_frequency_hours INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Usage Examples

### 1. Manual Job Execution

```bash
# Create configuration file
cat > config.json << EOF
{
  "name": "sales_data_sync",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/1abc123.../edit",
  "google_sheet_tab_name": "Q4_Sales",
  "google_cloud_project_id": "hkd-reporting",
  "bigquery_dataset_id": "sales",
  "bigquery_table_id": "q4_data",
  "schema_handling": "auto_detect"
}
EOF

# Execute job
python job_helper.py execute --config-file config.json
```

### 2. Orchestrated Execution

```bash
# Run orchestrator to process all active configs
python job_orchestrator.py \
  --postgres-host=your-postgres-host \
  --postgres-db=your-database \
  --postgres-user=your-user \
  --postgres-password=your-password \
  --max-parallel-jobs=3
```

### 3. Job Monitoring

```bash
# Check job status
python job_helper.py status

# List recent executions
python job_helper.py list --limit=20

# Get job logs
gcloud run jobs executions logs sheettobigquery-job --region=us-central1
```

## Migration from Service

### Step 1: Deploy Job Infrastructure
1. Deploy the Cloud Run Job using `cloudbuild-job.yaml`
2. Test manual job execution with `job_helper.py`

### Step 2: Update Database
1. Add job-specific columns to your configuration table
2. Populate `run_frequency_hours` for existing configs

### Step 3: Deploy Orchestrator
1. Choose deployment method (Cloud Run, Functions, or manual)
2. Set up scheduling (Cloud Scheduler if using automated approach)

### Step 4: Migrate Traffic
1. Update calling systems to use job orchestrator
2. Gradually phase out service endpoints
3. Monitor job execution and performance

### Step 5: Cleanup
1. Remove old service deployment
2. Clean up unused service-specific infrastructure

## Benefits of Job Architecture

### ✅ **Advantages**
- **Isolation**: Each config runs in its own container
- **Scalability**: No concurrency limits or scaling issues
- **Cost Efficiency**: Pay only for actual execution time
- **Reliability**: Individual job failures don't affect others
- **Resource Allocation**: Dedicated resources per job
- **Debugging**: Individual logs per execution

### ⚠️ **Considerations**
- **Cold Start**: Each job has container startup time
- **Orchestration**: Requires external coordination system
- **Complexity**: More moving parts than simple service

## Troubleshooting

### Common Issues

1. **Job Fails to Start**
   ```bash
   # Check job configuration
   gcloud run jobs describe sheettobigquery-job --region=us-central1
   
   # Verify secrets and environment variables
   python job_helper.py example  # See required config format
   ```

2. **Permission Errors**
   ```bash
   # Verify service account has required permissions
   # - BigQuery Data Editor
   # - Sheets API access
   # - Secret Manager Secret Accessor
   ```

3. **Database Connection Issues**
   ```bash
   # Test database connectivity
   python -c "import psycopg2; print('DB connection OK')"
   
   # Check orchestrator configuration
   python job_orchestrator.py --dry-run --postgres-host=...
   ```

### Performance Tuning

1. **Memory Allocation**: Adjust based on sheet size
   - Small sheets (< 1K rows): 1Gi memory
   - Medium sheets (1K-10K rows): 2Gi memory
   - Large sheets (> 10K rows): 4Gi memory

2. **Parallel Jobs**: Balance system load
   - Start with 3-5 parallel jobs
   - Monitor Cloud Run quotas
   - Adjust based on sheet processing times

3. **Execution Frequency**: Optimize based on data freshness needs
   - Real-time: Every 15-30 minutes
   - Near real-time: Every 1-2 hours  
   - Batch: Daily or weekly

## Support

For issues or questions:
1. Check job execution logs in Cloud Console
2. Use `job_helper.py` for manual testing
3. Review Slack notifications for error details
4. Monitor orchestrator logs for scheduling issues 