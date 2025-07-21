# Migration Guide: Service to Job Architecture

## Overview

This guide provides step-by-step instructions for migrating your Sheet to BigQuery implementation from a service-based architecture to a job-based architecture.

## Pre-Migration Checklist

- [ ] Current service is working and processing configurations
- [ ] Database access credentials are available
- [ ] Google Cloud permissions are set up correctly
- [ ] Backup current service configuration
- [ ] Test environment is available for validation

## Migration Steps

### Phase 1: Preparation and Testing

#### Step 1: Analyze Current Usage
```bash
# Review current service logs to understand usage patterns
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=service-sheettobigquery" \
  --limit=1000 --format="table(timestamp, severity, textPayload)"

# Identify peak usage times and frequency
# Document current configurations and their schedules
```

#### Step 2: Prepare Database Schema
```sql
-- Add new columns for job management to existing configuration table
ALTER TABLE sheet_to_bigquery_configs 
ADD COLUMN IF NOT EXISTS last_run TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS run_frequency_hours INTEGER DEFAULT 24,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_configs_active_last_run 
ON sheet_to_bigquery_configs(is_active, last_run);

-- Update existing records with reasonable defaults
UPDATE sheet_to_bigquery_configs 
SET run_frequency_hours = 24, is_active = true 
WHERE run_frequency_hours IS NULL;
```

#### Step 3: Deploy Job Infrastructure
```bash
# Deploy the Cloud Run Job
gcloud builds submit --config cloudbuild-job.yaml --project=hkd-reporting

# Verify job deployment
gcloud run jobs describe sheettobigquery-job --region=us-central1
```

#### Step 4: Test Job Execution
```bash
# Create test configuration file
cat > test_config.json << EOF
{
  "name": "migration_test",
  "google_sheet_url": "YOUR_TEST_SHEET_URL",
  "google_cloud_project_id": "hkd-reporting",
  "bigquery_dataset_id": "test_dataset",
  "bigquery_table_id": "migration_test",
  "schema_handling": "auto_detect"
}
EOF

# Test manual job execution
python job_helper.py execute --config-file test_config.json

# Verify results in BigQuery
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) as row_count FROM \`hkd-reporting.test_dataset.migration_test\`"
```

### Phase 2: Parallel Deployment

#### Step 5: Deploy Job Orchestrator
```bash
# Option A: Deploy as Cloud Run Service
gcloud run deploy sheettobigquery-orchestrator \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --env-vars-file orchestrator-env.yaml \
  --set-secrets="POSTGRES_PASSWORD=postgres-password:latest"
```

Create `orchestrator-env.yaml`:
```yaml
POSTGRES_HOST: 'your-postgres-host'
POSTGRES_DB: 'your-database'
POSTGRES_USER: 'your-username'
POSTGRES_PORT: '5432'
```

#### Step 6: Test Orchestrator
```bash
# Test orchestrator with dry run
python job_orchestrator.py \
  --postgres-host=your-host \
  --postgres-db=your-db \
  --postgres-user=your-user \
  --postgres-password=your-password \
  --dry-run

# Run orchestrator for a subset of configs
python job_orchestrator.py \
  --postgres-host=your-host \
  --postgres-db=your-db \
  --postgres-user=your-user \
  --postgres-password=your-password \
  --max-parallel-jobs=2
```

#### Step 7: Set Up Monitoring
```bash
# Create log-based metrics for job success/failure
gcloud logging metrics create sheet_to_bigquery_job_success \
  --description="Successful Sheet to BigQuery job executions" \
  --log-filter='resource.type="cloud_run_job"
    AND resource.labels.job_name="sheettobigquery-job"
    AND textPayload:"Job completed successfully"'

gcloud logging metrics create sheet_to_bigquery_job_failure \
  --description="Failed Sheet to BigQuery job executions" \
  --log-filter='resource.type="cloud_run_job"
    AND resource.labels.job_name="sheettobigquery-job"
    AND (textPayload:"Job execution failed" OR severity="ERROR")'
```

### Phase 3: Gradual Migration

#### Step 8: Configure Parallel Processing
```sql
-- Mark configurations for job processing
UPDATE sheet_to_bigquery_configs 
SET migration_status = 'job_ready'
WHERE name IN ('config1', 'config2', 'config3');  -- Start with low-risk configs

-- Create view for job orchestrator
CREATE VIEW active_job_configs AS
SELECT * FROM sheet_to_bigquery_configs 
WHERE is_active = true AND migration_status = 'job_ready';
```

#### Step 9: Run Both Systems in Parallel
```bash
# Continue running original service for non-migrated configs
# Run job orchestrator for migrated configs

# Monitor both systems
watch -n 30 'echo "=== Service Status ===" && gcloud run services describe service-sheettobigquery --region=us-central1 --format="value(status.conditions[0].type,status.conditions[0].status)" && echo "=== Job Status ===" && python job_helper.py status'
```

#### Step 10: Validate Job Results
```sql
-- Compare results between service and job executions
SELECT 
  config_name,
  service_last_run,
  job_last_run,
  service_row_count,
  job_row_count,
  CASE 
    WHEN service_row_count = job_row_count THEN 'MATCH'
    ELSE 'MISMATCH'
  END as validation_status
FROM comparison_view;
```

### Phase 4: Complete Migration

#### Step 11: Migrate All Configurations
```sql
-- Update all remaining configurations
UPDATE sheet_to_bigquery_configs 
SET migration_status = 'job_ready'
WHERE migration_status IS NULL OR migration_status = 'service';

-- Verify migration readiness
SELECT 
  COUNT(*) as total_configs,
  COUNT(CASE WHEN migration_status = 'job_ready' THEN 1 END) as job_ready,
  COUNT(CASE WHEN is_active = true THEN 1 END) as active_configs
FROM sheet_to_bigquery_configs;
```

#### Step 12: Set Up Production Scheduling
```bash
# Option A: Cloud Scheduler
gcloud scheduler jobs create http orchestrator-schedule \
  --schedule="0 */4 * * *" \
  --uri="https://sheettobigquery-orchestrator-xxx-uc.a.run.app/run" \
  --http-method=POST \
  --time-zone="UTC"

# Option B: Cron job on VM/container
# Add to crontab:
# 0 */4 * * * /usr/bin/python3 /path/to/job_orchestrator.py --config-file /path/to/config.json
```

#### Step 13: Update Monitoring and Alerting
```bash
# Create alerting policies
gcloud alpha monitoring policies create --policy-from-file=- <<EOF
{
  "displayName": "Sheet to BigQuery Job Failures",
  "conditions": [
    {
      "displayName": "Job failure rate",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/sheet_to_bigquery_job_failure\"",
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0
      }
    }
  ],
  "notificationChannels": ["projects/hkd-reporting/notificationChannels/YOUR_SLACK_CHANNEL"],
  "alertStrategy": {
    "autoClose": "300s"
  }
}
EOF
```

### Phase 5: Cleanup

#### Step 14: Decommission Service
```bash
# Scale down service traffic gradually
gcloud run services update-traffic service-sheettobigquery \
  --to-revisions=LATEST=50 \
  --region=us-central1

# Wait 24-48 hours and monitor for issues

# Scale to zero
gcloud run services update-traffic service-sheettobigquery \
  --to-revisions=LATEST=0 \
  --region=us-central1

# Wait another 24-48 hours

# Delete service
gcloud run services delete service-sheettobigquery \
  --region=us-central1
```

#### Step 15: Clean Up Resources
```sql
-- Remove migration tracking columns
ALTER TABLE sheet_to_bigquery_configs 
DROP COLUMN IF EXISTS migration_status;

-- Clean up test data
DELETE FROM sheet_to_bigquery_configs 
WHERE name LIKE 'migration_test%';
```

## Rollback Procedure

If issues arise during migration:

### Immediate Rollback
```bash
# Scale service back up
gcloud run services update-traffic service-sheettobigquery \
  --to-revisions=LATEST=100 \
  --region=us-central1

# Disable job orchestrator
gcloud scheduler jobs pause orchestrator-schedule

# Update database to disable job processing
UPDATE sheet_to_bigquery_configs 
SET migration_status = 'service' 
WHERE migration_status = 'job_ready';
```

### Partial Rollback
```sql
-- Rollback specific configurations
UPDATE sheet_to_bigquery_configs 
SET migration_status = 'service'
WHERE name IN ('problematic_config1', 'problematic_config2');
```

## Post-Migration Validation

### Performance Comparison
```bash
# Compare execution times
# Service average: Look at Cloud Run service metrics
# Job average: Look at Cloud Run job execution times

# Compare resource usage
# Service: Memory and CPU utilization over time
# Job: Per-execution resource consumption

# Compare costs
# Service: Monthly Cloud Run service costs
# Job: Sum of individual job execution costs
```

### Success Metrics
- [ ] All configurations successfully migrated
- [ ] No data loss or corruption
- [ ] Improved execution reliability
- [ ] Reduced overall costs
- [ ] Better monitoring and debugging capabilities

### Monitoring Checklist
- [ ] Job success/failure alerts configured
- [ ] Performance metrics tracked
- [ ] Database connection monitoring
- [ ] Resource quota monitoring
- [ ] Cost tracking enabled

## Troubleshooting Common Issues

### Issue 1: Job Startup Failures
```bash
# Check job configuration
gcloud run jobs describe sheettobigquery-job --region=us-central1

# Verify container image
gcloud container images list --repository=us-central1-docker.pkg.dev/hkd-reporting/github-service-sheettobigquery

# Test locally
docker run --rm -it us-central1-docker.pkg.dev/hkd-reporting/github-service-sheettobigquery/sheettobigquery-job:latest
```

### Issue 2: Orchestrator Database Connection
```bash
# Test connection manually
python -c "
import psycopg2
conn = psycopg2.connect(host='HOST', database='DB', user='USER', password='PASS')
print('Connection successful')
"

# Check firewall rules
gcloud compute firewall-rules list --filter="name~postgres"
```

### Issue 3: Permission Issues
```bash
# Verify service account permissions
gcloud projects get-iam-policy hkd-reporting \
  --flatten="bindings[].members" \
  --filter="bindings.members:*sheettobigquery*"

# Test Google Sheets access
python -c "
from main import get_credentials, get_sheet_data
creds = get_credentials()
print('Credentials OK')
"
```

## Support and Documentation

- **Job Architecture Documentation**: `README-JOB.md`
- **Helper Scripts**: `job_helper.py` for manual operations
- **Orchestrator**: `job_orchestrator.py` for automated processing
- **Original Service**: `app.py` (maintained for reference)

## Success Criteria

Migration is considered successful when:
1. All configurations process successfully via jobs
2. Data accuracy is maintained (100% match with service results)
3. No increase in processing failures
4. Monitoring and alerting are functional
5. Documentation is updated and team is trained
6. Original service can be safely decommissioned

---

**Note**: This migration should be performed during a maintenance window or low-traffic period to minimize impact on data processing schedules. 