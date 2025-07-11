from flask import Flask, request, jsonify
from main import main as sheet_to_bigquery_main
import os
import logging
import json
import base64
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

app = Flask(__name__)

@app.route('/sheet-to-bigquery', methods=['POST'])
def process_request():
    trace_header = request.headers.get("X-Cloud-Trace-Context", "")
    trace_id = None

    if trace_header:
        parts = trace_header.split('/')
        if len(parts) > 0:
            trace_id = parts[0]

    try:
        # 1. Decode Pub/Sub message
        envelope = request.get_json(silent=True)
        if not envelope or "message" not in envelope:
            return jsonify({"status": "error", "message": "No Pub/Sub message received"}), 400

        pubsub_message = envelope["message"]

        if "data" not in pubsub_message:
            return jsonify({"status": "error", "message": "No data field in Pub/Sub message"}), 400

        # 2. Base64 decode and JSON parse
        try:
            payload_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
            input_params = json.loads(payload_str)
        except Exception as e:
            logger.error(f"Error decoding message data: {e}")
            return jsonify({"status": "error", "message": f"Failed to parse Pub/Sub message: {str(e)}"}), 400

        # 3. Extract fields for Sheet to BigQuery transfer
        logger.info(f"Input parameters: {input_params}")
        params = {
            "config_id": input_params.get("id"),
            "name": input_params.get("name"),
            "google_sheet_url": input_params.get("google_sheet_url"),
            "google_sheet_tab_name": input_params.get("google_sheet_tab_name"),
            "google_cloud_project_id": input_params.get("google_cloud_project_id"),
            "bigquery_dataset_id": input_params.get("bigquery_dataset_id"),
            "bigquery_table_id": input_params.get("bigquery_table_id"),
            "schema_handling": input_params.get("schema_handling"),
            "custom_schema": input_params.get("custom_schema")
        }

        # Check for required parameters
        required_params = ['name', 'google_sheet_url', 'google_cloud_project_id', 'bigquery_dataset_id', 'bigquery_table_id']
        for param in required_params:
            if not params.get(param):
                error_msg = f"{param} is required"
                logger.error(error_msg)
                return jsonify({"status": "error", "message": error_msg}), 400

        response_data = {}
        try:
            logger.info(f"Processing Sheet to BigQuery request for config: {params.get('name')}")
            result = sheet_to_bigquery_main(**params)
            
            if result is not None:
                response_data['status'] = "success"
                response_data['message'] = f"Successfully transferred data from Google Sheet to BigQuery table: {params['bigquery_dataset_id']}.{params['bigquery_table_id']}"
                logger.info(f"Successfully processed config: {params.get('name')}")
                return jsonify(response_data), 200
            else:
                response_data['status'] = "error"
                response_data['message'] = "Failed to process Sheet to BigQuery transfer"
                logger.error(f"Failed to process config: {params.get('name')}")
                return jsonify(response_data), 500

        except Exception as e:
            logger.error(f"{trace_id} - Error processing Sheet to BigQuery transfer: {e}")
            
            # Check if it's a critical error that should send Slack notification
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['permission', 'access', 'not found', 'invalid', 'forbidden']):
                send_slack_notification(
                    f"🔴 Sheet to BigQuery Service: Critical error processing '{params.get('name')}' - {e}"
                )
            
            response_data['status'] = "error"
            response_data['message'] = str(e)
            return jsonify(response_data), 500

    except Exception as e:
        logger.error(f"{trace_id} - Error retrieving parameters from initial request: {e}")
        return jsonify({"status": "error", "message": f"Failed to retrieve parameters: {e}"}), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 