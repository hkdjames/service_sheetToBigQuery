# Google Cloud Console Settings Required

## Migration Summary
Moving from cross-project deployment (`decoded-jigsaw-341521` + `hkd-reporting`) to single-project deployment (`hkd-reporting` only).

## Required Changes in Google Cloud Console

### 1. APIs & Services
**Location**: [APIs & Services > Library](https://console.cloud.google.com/apis/library?project=hkd-reporting)
**Project**: `hkd-reporting`

**Enable these APIs:**
- ✅ Google Sheets API
- ✅ BigQuery API  
- ✅ Google Drive API
- ✅ Cloud Run API
- ✅ Cloud Build API
- ✅ Artifact Registry API
- ✅ Secret Manager API

**Quick Command**: Run `./enable_apis.sh` or `./enable_apis.ps1`

### 2. Artifact Registry
**Location**: [Artifact Registry](https://console.cloud.google.com/artifacts?project=hkd-reporting)
**Project**: `hkd-reporting`

**Create New Repository:**
- **Name**: `github-service-sheettobigquery`
- **Format**: Docker
- **Mode**: Standard
- **Location Type**: Region
- **Region**: `us-central1`

**Command**: 
```bash
gcloud artifacts repositories create github-service-sheettobigquery \
    --repository-format=docker \
    --location=us-central1 \
    --project=hkd-reporting
```

### 3. Cloud Build
**Location**: [Cloud Build](https://console.cloud.google.com/cloud-build?project=hkd-reporting)
**Project**: `hkd-reporting`

**Settings Required:**
- **Default Service Account**: `[PROJECT-NUMBER]@cloudbuild.gserviceaccount.com`
- **Required Triggers**: Connect to your source repository

**Run Build Command**:
```bash
gcloud builds submit --config cloudbuild.yaml --project=hkd-reporting
```

### 4. IAM & Admin
**Location**: [IAM & Admin > IAM](https://console.cloud.google.com/iam-admin/iam?project=hkd-reporting)
**Project**: `hkd-reporting`

**Grant Cloud Build Service Account These Roles:**
Find: `[PROJECT-NUMBER]@cloudbuild.gserviceaccount.com`
Add:
- ✅ Cloud Run Developer
- ✅ Artifact Registry Writer  
- ✅ Secret Manager Secret Accessor

**Service Account Permissions** (`hkd-reporting@hkd-reporting.iam.gserviceaccount.com`):
- ✅ BigQuery Data Editor
- ✅ BigQuery Job User
- ✅ (Existing permissions should be fine)

### 5. Secret Manager
**Location**: [Security > Secret Manager](https://console.cloud.google.com/security/secret-manager?project=hkd-reporting)
**Project**: `hkd-reporting`

**Required Secrets:**
- ✅ `google_cloud_hkdreporting` - Service account JSON key
- ✅ `slack_accessToken` - Slack bot token

**Verify these secrets exist and are accessible by the Cloud Run service.**

### 6. Cloud Run
**Location**: [Cloud Run](https://console.cloud.google.com/run?project=hkd-reporting)
**Project**: `hkd-reporting`

**Service Configuration** (will be created by Cloud Build):
- **Service Name**: `service-sheettobigquery`
- **Region**: `us-central1`
- **Platform**: Managed
- **Authentication**: Allow unauthenticated invocations
- **Environment Variables**: Linked to Secret Manager

### 7. BigQuery
**Location**: [BigQuery](https://console.cloud.google.com/bigquery?project=hkd-reporting)
**Project**: `hkd-reporting`

**Verify Existing:**
- ✅ Datasets (e.g., `hkd_plutotvcanada`)
- ✅ Service account has proper access

## Configuration Updates Required

### Update Calling Service Configuration
**CRITICAL**: Any service/system calling this Sheet to BigQuery service must update their configuration:

**Change FROM:**
```json
{
  "google_cloud_project_id": "decoded-jigsaw-341521"
}
```

**Change TO:**
```json
{
  "google_cloud_project_id": "hkd-reporting"
}
```

### New Service URL
After deployment, update any hardcoded URLs to:
```
https://service-sheettobigquery-[hash].us-central1.run.app
```

## Quick Setup Commands

1. **Enable APIs**: `./enable_apis.sh`
2. **Setup Infrastructure**: `./setup_infrastructure.sh`  
3. **Deploy Service**: `gcloud builds submit --config cloudbuild.yaml --project=hkd-reporting`

## Cleanup (Optional)
After successful migration, you can remove the old service from `decoded-jigsaw-341521`:
- Delete Cloud Run service
- Delete Artifact Registry images
- Remove any unused IAM bindings

## Verification Checklist
- [ ] All APIs enabled in `hkd-reporting`
- [ ] Artifact Registry repository created
- [ ] Cloud Build service account has required roles
- [ ] Secrets exist in Secret Manager
- [ ] Service deploys successfully
- [ ] Configuration updated to use `hkd-reporting`
- [ ] Service responds to test requests
- [ ] BigQuery operations work correctly 