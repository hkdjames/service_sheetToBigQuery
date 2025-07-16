# Sheet to BigQuery Service - Project Setup

## Project Architecture

This service operates across two Google Cloud projects:

### 1. Deployment Project: `decoded-jigsaw-341521`
- **Purpose**: Cloud Run deployment, API billing
- **Contains**: 
  - Cloud Run service hosting this application
  - API quotas and billing for Google Sheets API calls
- **Credentials**: Uses service account from `hkd-reporting` project

### 2. Data Project: `hkd-reporting` 
- **Purpose**: Data storage and processing
- **Contains**:
  - BigQuery datasets and tables
  - Service account with appropriate permissions
- **Service Account**: `hkd-reporting@hkd-reporting.iam.gserviceaccount.com`

## Configuration Requirements

When configuring the service, ensure:

### Google Cloud Project ID Parameter
```json
{
  "google_cloud_project_id": "hkd-reporting"
}
```
**Important**: This should be `hkd-reporting`, not `decoded-jigsaw-341521`

### Service Account Permissions
The service account must have:
- BigQuery Data Editor role in `hkd-reporting` project
- Access to Google Sheets (shared with service account email)

### Environment Variables
```bash
google_cloud_hkdreporting='{service_account_json}'
slack_accessToken='{slack_token}'
```

## Error Resolution

### "with_project" AttributeError
- **Cause**: Attempting to override service account project
- **Solution**: Fixed in latest code - uses proper quota project setup

### Permission Denied Errors
- **Cause**: Wrong project in `google_cloud_project_id` parameter
- **Solution**: Use `hkd-reporting` as the target project

### BigQuery Dataset Not Found
- **Cause**: Looking in wrong project (`decoded-jigsaw-341521` vs `hkd-reporting`)
- **Solution**: Verify `google_cloud_project_id` is set to `hkd-reporting`

## Deployment Process

1. Deploy service to `decoded-jigsaw-341521` project
2. Configure environment variable with `hkd-reporting` service account
3. Set `google_cloud_project_id` parameter to `hkd-reporting` in all configurations
4. Ensure BigQuery datasets exist in `hkd-reporting` project 