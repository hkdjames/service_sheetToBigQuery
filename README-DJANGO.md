# Using Sheet to BigQuery Jobs with Django

## Overview

This guide explains how to use the Sheet to BigQuery job system with your existing Django application that manages configurations.

## Architecture

```
Django App (Portal) → PostgreSQL Database → Standalone Job Orchestrator → Cloud Run Jobs
```

- **Django App**: Manages configurations through admin interface
- **PostgreSQL Database**: Stores `SheetToBigQueryConfig` records
- **Job Orchestrator**: Standalone script that reads configs and triggers jobs
- **Cloud Run Jobs**: Individual job executions for each configuration

## Setup

### 1. Django Model Updates ✅

Your Django model has been updated with job orchestration fields:

```python
class SheetToBigQueryConfig(models.Model):
    # ... existing fields ...
    
    # New job orchestration fields
    last_run = models.DateTimeField(null=True, blank=True)
    run_frequency_hours = models.PositiveIntegerField(default=24)
    
    @property
    def should_run(self):
        """Check if this configuration should run based on frequency and last run"""
        # Logic implemented
```

### 2. Database Migration ✅

The migration has been applied:
- `0003_sheettobigqueryconfig_last_run_and_more.py`

### 3. Admin Interface ✅

The Django admin has been updated to show:
- Run frequency settings
- Last run timestamps
- Job status indicators

## Usage

### Managing Configurations (Django Admin)

1. **Access Django Admin**: `/admin/sheet_to_bigquery/sheettobigqueryconfig/`

2. **Create/Edit Configurations**:
   - Set `run_frequency_hours`:
     - `0` = Manual execution only
     - `1` = Every hour
     - `24` = Daily (default)
     - `168` = Weekly

3. **Monitor Status**:
   - **Status Column**: Shows if config is "Due", "Not due", "Manual", or "Inactive"
   - **Last Run**: Shows when job was last executed
   - **Frequency**: Shows how often job runs

### Running Jobs (Standalone Orchestrator)

#### Option 1: Direct Database Connection

```bash
# Run orchestrator connecting directly to Django database
python job_orchestrator_django.py \
  --postgres-host=your-django-db-host \
  --postgres-db=your-django-db-name \
  --postgres-user=your-django-db-user \
  --postgres-password=your-django-db-password \
  --dry-run  # Remove for actual execution
```

#### Option 2: Manual Single Job

```bash
# Create config from Django data
cat > config.json << EOF
{
  "name": "sales_data_sync",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/...",
  "google_cloud_project_id": "hkd-reporting",
  "bigquery_dataset_id": "sales",
  "bigquery_table_id": "q4_data",
  "schema_handling": "auto_detect"
}
EOF

# Execute single job
python job_helper.py execute --config-file config.json
```

## Configuration Examples

### High-Frequency Data (Every Hour)
```python
# In Django admin or shell
config = SheetToBigQueryConfig.objects.create(
    name="real_time_metrics",
    google_sheet_url="https://docs.google.com/spreadsheets/d/...",
    google_cloud_project_id="hkd-reporting",
    bigquery_dataset_id="metrics",
    bigquery_table_id="hourly_data",
    run_frequency_hours=1,  # Every hour
    schema_handling="auto_detect"
)
```

### Daily Batch Processing
```python
config = SheetToBigQueryConfig.objects.create(
    name="daily_sales_report",
    google_sheet_url="https://docs.google.com/spreadsheets/d/...",
    google_cloud_project_id="hkd-reporting",
    bigquery_dataset_id="sales",
    bigquery_table_id="daily_summary",
    run_frequency_hours=24,  # Daily
    schema_handling="custom",
    custom_schema='[{"name": "date", "type": "DATE"}, {"name": "sales", "type": "FLOAT"}]'
)
```

### Manual Execution Only
```python
config = SheetToBigQueryConfig.objects.create(
    name="manual_data_import",
    google_sheet_url="https://docs.google.com/spreadsheets/d/...",
    google_cloud_project_id="hkd-reporting",
    bigquery_dataset_id="imports",
    bigquery_table_id="manual_data",
    run_frequency_hours=0,  # Manual only
    schema_handling="auto_detect"
)
```

## Deployment Options

### Option 1: Cloud Scheduler + Cloud Run Service
```bash
# Deploy orchestrator as Cloud Run Service
gcloud run deploy sheettobigquery-orchestrator \
  --source . \
  --region us-central1 \
  --set-env-vars="POSTGRES_HOST=your-host,POSTGRES_DB=your-db" \
  --set-secrets="POSTGRES_PASSWORD=db-password:latest"

# Create Cloud Scheduler job
gcloud scheduler jobs create http orchestrator-schedule \
  --schedule="0 */6 * * *" \
  --uri="https://your-orchestrator-url/run" \
  --http-method=POST
```

### Option 2: Compute Engine with Cron
```bash
# On VM with cron
# Add to crontab: 
# 0 */6 * * * /path/to/job_orchestrator_django.py --postgres-host=... --postgres-db=...
```

### Option 3: Manual Execution
```bash
# Run manually when needed
python job_orchestrator_django.py \
  --postgres-host=your-host \
  --postgres-db=your-db \
  --postgres-user=your-user \
  --postgres-password=your-password
```

## Monitoring

### Django Admin Monitoring
- View job execution status in admin interface
- Filter by frequency, status, and last run
- See which configs are due to run

### Cloud Console Monitoring
```bash
# View job executions
gcloud run jobs executions list --job=sheettobigquery-job --region=us-central1

# View job logs
gcloud run jobs executions logs JOB_EXECUTION_NAME --region=us-central1
```

### Database Monitoring
```sql
-- Check job execution status
SELECT 
    name,
    run_frequency_hours,
    last_run,
    is_active,
    CASE 
        WHEN run_frequency_hours = 0 THEN 'Manual'
        WHEN last_run IS NULL THEN 'Never run'
        WHEN NOW() - last_run > INTERVAL run_frequency_hours HOUR THEN 'Due'
        ELSE 'Not due'
    END as status
FROM sheet_to_bigquery_sheettobigqueryconfig
WHERE is_active = true
ORDER BY last_run DESC;
```

## Troubleshooting

### Common Issues

1. **No configs found**
   ```bash
   # Check database connection
   python -c "import psycopg2; conn = psycopg2.connect(host='HOST', database='DB', user='USER', password='PASS'); print('Connected')"
   ```

2. **Configs not running**
   ```bash
   # Check config status with dry run
   python job_orchestrator_django.py --dry-run --postgres-host=... --postgres-db=...
   ```

3. **Job execution failures**
   ```bash
   # Check Cloud Run Job logs
   gcloud run jobs executions logs EXECUTION_NAME --region=us-central1
   ```

### Debug Mode

```bash
# Run orchestrator with verbose logging
python job_orchestrator_django.py \
  --postgres-host=your-host \
  --postgres-db=your-db \
  --postgres-user=your-user \
  --postgres-password=your-password \
  --dry-run \
  --config-names "specific_config_name"  # Test specific config
```

## Security

### Database Access
- Use dedicated database user with read/write access to job table only
- Store database credentials in Cloud Secret Manager
- Use connection pooling for production deployments

### Google Cloud Permissions
- Job requires same permissions as original service:
  - BigQuery Data Editor
  - Sheets API access
  - Secret Manager Secret Accessor

## Benefits of This Approach

✅ **Separation of Concerns**: Django manages configs, jobs handle execution
✅ **Scalability**: Jobs run independently without affecting Django app
✅ **Flexibility**: Can run orchestrator from anywhere with database access
✅ **Monitoring**: Full visibility through Django admin + Cloud Console
✅ **Reliability**: Individual job failures don't affect Django or other jobs 