# Sheet to BigQuery Service

## Migration to Single-Project Architecture

This service has been updated to run entirely within the `hkd-reporting` Google Cloud project, eliminating cross-project complexity.

## Quick Setup

1. **Enable APIs**: 
   ```bash
   ./enable_apis.sh    # Linux/Mac
   ./enable_apis.ps1   # Windows
   ```

2. **Setup Infrastructure**:
   ```bash
   ./setup_infrastructure.sh
   ```

3. **Deploy Service**:
   ```bash
   gcloud builds submit --config cloudbuild.yaml --project=hkd-reporting
   ```

## Important Files

- **`GOOGLE_CLOUD_CONSOLE_CHANGES.md`** - Complete list of required Google Cloud Console settings
- **`main.py`** - Simplified service code (no cross-project complexity)
- **`cloudbuild.yaml`** - Updated to deploy to `hkd-reporting`
- **`enable_apis.sh/.ps1`** - Enable all required APIs
- **`setup_infrastructure.sh`** - Automated infrastructure setup

## Critical Configuration Change

**Any system calling this service must update:**
```json
{
  "google_cloud_project_id": "hkd-reporting"
}
```

## Benefits of Single-Project Setup
- ✅ Simplified architecture
- ✅ No quota project management needed
- ✅ All resources in one place
- ✅ Easier debugging and maintenance
- ✅ Eliminates cross-project permission issues

## Service Functionality
Transfers data from Google Sheets to BigQuery tables with:
- Auto-detect or custom schema support
- Error handling with Slack notifications
- Support for specific sheet tabs
- Automatic dataset creation 