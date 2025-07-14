import json
import os
import platform
import logging
import pandas as pd
from google.oauth2 import service_account
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configure Slack Client
slack_access_token = os.getenv("slack_accessToken")
if slack_access_token:
    slack_channel = "dev_alerts"
    slack_client = WebClient(token=slack_access_token)
else:
    logger.error("Could not generate slack client - slack_accessToken not found")
    slack_client = None

def send_slack_notification(message):
    """Send notification to Slack dev_alerts channel"""
    if slack_client:
        try:
            slack_client.chat_postMessage(channel=slack_channel, text=message)
            logger.info(f"Sent Slack notification: {message}")
        except SlackApiError as e:
            logger.error(f"Error sending Slack message: {e}")
    else:
        logger.warning("Slack client not configured, skipping notification")

def get_credentials():
    """Get Google Cloud credentials based on platform."""
    # Define the required scopes for Google Sheets and BigQuery access
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',  # Google Sheets read access
        'https://www.googleapis.com/auth/cloud-platform',        # BigQuery and other GCP services
        'https://www.googleapis.com/auth/drive.readonly'         # Google Drive read access (for accessing sheets)
    ]
    
    try:
        if platform.system() == 'Windows':
            # Windows - use service account file (for local development)
            service_account_path = r'G:\Shared drives\HKD - Admin\GitHub\process_agenda\hkd-reporting-5b9e2c294edc.json'
            if os.path.exists(service_account_path):
                logger.info(f"Using Windows service account file: {service_account_path}")
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_path, scopes=SCOPES
                )
                return credentials
            else:
                logger.error(f"Service account file not found: {service_account_path}")
                raise FileNotFoundError(f"Service account file not found: {service_account_path}")
        else:
            # Linux/Production - use environment variable
            logger.info("Running on Linux, using google_cloud_hkdreporting for authentication...")
            
            credentials_json = os.environ.get('google_cloud_hkdreporting')
            if not credentials_json:
                logger.error("google_cloud_hkdreporting environment variable not found")
                raise ValueError("google_cloud_hkdreporting environment variable not found")
            
            logger.info(f"Found google_cloud_hkdreporting environment variable, length: {len(credentials_json)}")
            
            try:
                credentials_dict = json.loads(credentials_json)
                logger.info("Successfully parsed credentials JSON")
                logger.info(f"Service account project ID: {credentials_dict.get('project_id', 'Unknown')}")
                logger.info(f"Service account email: {credentials_dict.get('client_email', 'Unknown')}")
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict, scopes=SCOPES
                )
                return credentials
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse credentials JSON: {e}")
                raise ValueError(f"Invalid JSON in google_cloud_hkdreporting: {e}")
            
    except Exception as e:
        logger.error(f"Error getting credentials: {e}")
        raise

def extract_sheet_id_from_url(url):
    """Extract Google Sheet ID from URL"""
    try:
        if '/spreadsheets/d/' in url:
            start = url.find('/spreadsheets/d/') + len('/spreadsheets/d/')
            end = url.find('/', start)
            if end == -1:
                end = url.find('#', start)
            if end == -1:
                end = len(url)
            return url[start:end]
        else:
            logger.error(f"Invalid Google Sheet URL format: {url}")
            raise ValueError(f"Invalid Google Sheet URL format: {url}")
    except Exception as e:
        logger.error(f"Error extracting sheet ID from URL: {e}")
        raise

def get_sheet_data(sheet_url, tab_name=None):
    """Get data from Google Sheet"""
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        
        # Extract sheet ID from URL
        sheet_id = extract_sheet_id_from_url(sheet_url)
        logger.info(f"Extracted sheet ID: {sheet_id}")
        
        # Get sheet metadata to find available tabs
        sheet_metadata = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = sheet_metadata.get('sheets', [])
        
        if not sheets:
            error_msg = f"No sheets found in the Google Sheet: {sheet_url}"
            logger.error(error_msg)
            send_slack_notification(f"🔴 Sheet to BigQuery Service: {error_msg}")
            raise ValueError(error_msg)
        
        # Determine which tab to use
        if tab_name:
            # Check if specified tab exists
            tab_found = False
            for sheet in sheets:
                if sheet['properties']['title'] == tab_name:
                    tab_found = True
                    break
            
            if not tab_found:
                error_msg = f"Tab '{tab_name}' not found in Google Sheet. Available tabs: {[sheet['properties']['title'] for sheet in sheets]}"
                logger.error(error_msg)
                send_slack_notification(f"🔴 Sheet to BigQuery Service: {error_msg}")
                raise ValueError(error_msg)
            
            range_name = f"'{tab_name}'"
        else:
            # Use first tab
            range_name = f"'{sheets[0]['properties']['title']}'"
            logger.info(f"Using first available tab: {range_name}")
        
        # Get the data
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        if not values:
            error_msg = f"No data found in the specified sheet/tab: {range_name}"
            logger.error(error_msg)
            send_slack_notification(f"🔴 Sheet to BigQuery Service: {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"Retrieved {len(values)} rows from Google Sheet")
        return values
        
    except HttpError as e:
        error_code = e.resp.status
        error_reason = e.error_details[0].get('reason', 'Unknown') if e.error_details else 'Unknown'
        
        if error_code == 403:
            if 'SERVICE_DISABLED' in str(e):
                error_msg = f"Google Sheets API is disabled for the project. Enable it at: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview"
            elif 'does not have permission' in str(e):
                error_msg = f"Service account does not have permission to access this Google Sheet. Please share the sheet with the service account email or check IAM permissions."
            else:
                error_msg = f"Permission denied accessing Google Sheet: {e}"
        elif error_code == 404:
            error_msg = f"Google Sheet not found. Please check the URL: {sheet_url}"
        else:
            error_msg = f"Google Sheets API error (HTTP {error_code}): {e}"
        
        logger.error(error_msg)
        send_slack_notification(f"🔴 Sheet to BigQuery Service: {error_msg}")
        raise
    except Exception as e:
        logger.error(f"Error getting sheet data: {e}")
        raise

def create_bigquery_dataset_if_not_exists(client, project_id, dataset_id):
    """Create BigQuery dataset if it doesn't exist"""
    try:
        dataset_ref = client.dataset(dataset_id, project=project_id)
        client.get_dataset(dataset_ref)
        logger.info(f"Dataset {project_id}.{dataset_id} already exists")
    except NotFound:
        logger.info(f"Creating dataset {project_id}.{dataset_id}")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        logger.info(f"Created dataset {project_id}.{dataset_id}")

def create_custom_schema(custom_schema_json):
    """Create BigQuery schema from custom schema JSON"""
    try:
        schema_fields = []
        schema_data = json.loads(custom_schema_json) if isinstance(custom_schema_json, str) else custom_schema_json
        
        for field in schema_data:
            field_name = field.get('name')
            field_type = field.get('type', 'STRING')
            field_mode = field.get('mode', 'NULLABLE')
            
            schema_fields.append(bigquery.SchemaField(field_name, field_type, mode=field_mode))
        
        return schema_fields
    except Exception as e:
        logger.error(f"Error creating custom schema: {e}")
        raise ValueError(f"Invalid custom schema format: {e}")

def main(config_id=None, name=None, google_sheet_url=None, google_sheet_tab_name=None, 
         google_cloud_project_id=None, bigquery_dataset_id=None, bigquery_table_id=None,
         schema_handling=None, custom_schema=None):
    """Main function to transfer data from Google Sheet to BigQuery"""
    
    try:
        logger.info(f"Starting Sheet to BigQuery transfer for config: {name}")
        
        # Get data from Google Sheet
        sheet_data = get_sheet_data(google_sheet_url, google_sheet_tab_name)
        
        if not sheet_data:
            error_msg = f"No data retrieved from Google Sheet: {google_sheet_url}"
            logger.error(error_msg)
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])  # First row as headers
        logger.info(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
        
        # Get BigQuery client
        creds = get_credentials()
        client = bigquery.Client(credentials=creds, project=google_cloud_project_id)
        
        # Create dataset if it doesn't exist
        create_bigquery_dataset_if_not_exists(client, google_cloud_project_id, bigquery_dataset_id)
        
        # Prepare table reference
        table_ref = client.dataset(bigquery_dataset_id).table(bigquery_table_id)
        
        # Configure job config
        job_config = bigquery.LoadJobConfig()
        job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE  # Replace table
        job_config.source_format = bigquery.SourceFormat.PARQUET
        
        # Handle schema
        if schema_handling == 'custom' and custom_schema:
            logger.info("Using custom schema")
            job_config.schema = create_custom_schema(custom_schema)
            job_config.autodetect = False
        else:
            logger.info("Using auto-detect schema")
            job_config.autodetect = True
        
        # Load data to BigQuery
        logger.info(f"Loading data to BigQuery table: {google_cloud_project_id}.{bigquery_dataset_id}.{bigquery_table_id}")
        
        # Use load_table_from_dataframe for better performance
        job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        
        # Wait for job to complete
        job.result()
        
        # Get final table info
        table = client.get_table(table_ref)
        logger.info(f"Successfully loaded {table.num_rows} rows to BigQuery table")
        
        return {
            'status': 'success',
            'rows_loaded': table.num_rows,
            'table_id': f"{google_cloud_project_id}.{bigquery_dataset_id}.{bigquery_table_id}"
        }
        
    except Exception as e:
        logger.error(f"Error in Sheet to BigQuery transfer: {e}")
        raise

if __name__ == "__main__":
    # Test locally
    main(
        name="test_config",
        google_sheet_url="https://docs.google.com/spreadsheets/d/1example",
        google_cloud_project_id="decoded-jigsaw-341521",
        bigquery_dataset_id="test_dataset",
        bigquery_table_id="test_table",
        schema_handling="auto_detect"
    ) 