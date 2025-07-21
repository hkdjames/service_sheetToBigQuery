#!/usr/bin/env python3
"""
Job Helper for Sheet to BigQuery Jobs

This script provides utility functions for managing and triggering
individual Sheet to BigQuery jobs manually.
"""

import os
import json
import logging
import subprocess
import tempfile
import argparse
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JobHelper:
    def __init__(self, job_name: str = "sheettobigquery-job", region: str = "us-central1"):
        """Initialize job helper with job configuration"""
        self.job_name = job_name
        self.region = region
    
    def create_env_vars_file(self, config: Dict) -> str:
        """Create environment variables file from configuration dictionary"""
        required_vars = {
            'CONFIG_NAME': 'name',
            'GOOGLE_SHEET_URL': 'google_sheet_url',
            'GOOGLE_CLOUD_PROJECT_ID': 'google_cloud_project_id',
            'BIGQUERY_DATASET_ID': 'bigquery_dataset_id',
            'BIGQUERY_TABLE_ID': 'bigquery_table_id'
        }
        
        # Validate required variables
        missing_vars = []
        for env_var, config_key in required_vars.items():
            if not config.get(config_key):
                missing_vars.append(config_key)
        
        if missing_vars:
            raise ValueError(f"Missing required configuration keys: {missing_vars}")
        
        # Build environment variables
        env_vars = {}
        
        # Required variables
        for env_var, config_key in required_vars.items():
            env_vars[env_var] = config[config_key]
        
        # Optional variables
        if config.get('config_id'):
            env_vars['CONFIG_ID'] = str(config['config_id'])
        
        if config.get('google_sheet_tab_name'):
            env_vars['GOOGLE_SHEET_TAB_NAME'] = config['google_sheet_tab_name']
        
        env_vars['SCHEMA_HANDLING'] = config.get('schema_handling', 'auto_detect')
        
        if config.get('custom_schema'):
            if isinstance(config['custom_schema'], dict):
                env_vars['CUSTOM_SCHEMA'] = json.dumps(config['custom_schema'])
            else:
                env_vars['CUSTOM_SCHEMA'] = config['custom_schema']
        
        # Create temporary file in YAML format
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        
        for key, value in env_vars.items():
            # Escape single quotes in values
            escaped_value = str(value).replace("'", "''")
            temp_file.write(f"{key}: '{escaped_value}'\n")
        
        temp_file.close()
        
        logger.info(f"Created environment file: {temp_file.name}")
        logger.info("Environment variables:")
        for key, value in env_vars.items():
            if 'SCHEMA' in key and len(str(value)) > 100:
                logger.info(f"  {key}: {str(value)[:100]}... (truncated)")
            else:
                logger.info(f"  {key}: {value}")
        
        return temp_file.name
    
    def execute_job(self, config: Dict, wait: bool = True, timeout: int = 2400) -> bool:
        """Execute a Cloud Run Job with the given configuration"""
        env_file = None
        try:
            logger.info(f"Executing job for: {config.get('name', 'Unknown')}")
            
            # Create environment variables file
            env_file = self.create_env_vars_file(config)
            
            # Build gcloud command
            cmd = [
                'gcloud', 'run', 'jobs', 'execute', self.job_name,
                '--region', self.region,
                '--env-vars-file', env_file
            ]
            
            if wait:
                cmd.append('--wait')
            
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            # Execute the job
            if wait:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode == 0:
                    logger.info("Job completed successfully")
                    logger.info(f"Output: {result.stdout}")
                    return True
                else:
                    logger.error("Job failed")
                    logger.error(f"Error output: {result.stderr}")
                    return False
            else:
                # Fire and forget
                subprocess.Popen(cmd)
                logger.info("Job submitted (not waiting for completion)")
                return True
                
        except subprocess.TimeoutExpired:
            logger.error(f"Job timed out after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error executing job: {e}")
            return False
        finally:
            # Clean up temporary file
            if env_file and os.path.exists(env_file):
                os.unlink(env_file)
                logger.info(f"Cleaned up environment file: {env_file}")
    
    def get_job_status(self) -> Dict:
        """Get the status of the Cloud Run Job"""
        try:
            cmd = [
                'gcloud', 'run', 'jobs', 'describe', self.job_name,
                '--region', self.region,
                '--format', 'json'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"Error getting job status: {result.stderr}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {}
    
    def list_job_executions(self, limit: int = 10) -> list:
        """List recent job executions"""
        try:
            cmd = [
                'gcloud', 'run', 'jobs', 'executions', 'list',
                '--job', self.job_name,
                '--region', self.region,
                '--limit', str(limit),
                '--format', 'json'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"Error listing executions: {result.stderr}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing executions: {e}")
            return []

def main():
    parser = argparse.ArgumentParser(description='Sheet to BigQuery Job Helper')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Execute command
    execute_parser = subparsers.add_parser('execute', help='Execute a job')
    execute_parser.add_argument('--config-file', required=True, help='JSON config file')
    execute_parser.add_argument('--no-wait', action='store_true', help='Don\'t wait for job completion')
    execute_parser.add_argument('--timeout', type=int, default=2400, help='Job timeout in seconds')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get job status')
    
    # List executions command
    list_parser = subparsers.add_parser('list', help='List recent executions')
    list_parser.add_argument('--limit', type=int, default=10, help='Number of executions to show')
    
    # Example config command
    example_parser = subparsers.add_parser('example', help='Show example configuration')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    job_helper = JobHelper()
    
    if args.command == 'execute':
        # Load configuration from file
        try:
            with open(args.config_file, 'r') as f:
                config = json.load(f)
            
            success = job_helper.execute_job(
                config,
                wait=not args.no_wait,
                timeout=args.timeout
            )
            
            if success:
                logger.info("Job execution completed successfully")
            else:
                logger.error("Job execution failed")
                exit(1)
                
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            exit(1)
    
    elif args.command == 'status':
        status = job_helper.get_job_status()
        if status:
            print(json.dumps(status, indent=2))
        else:
            logger.error("Could not get job status")
            exit(1)
    
    elif args.command == 'list':
        executions = job_helper.list_job_executions(args.limit)
        if executions:
            print(json.dumps(executions, indent=2))
        else:
            logger.info("No executions found or error listing executions")
    
    elif args.command == 'example':
        example_config = {
            "name": "example_sheet_transfer",
            "google_sheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit",
            "google_sheet_tab_name": "Sheet1",
            "google_cloud_project_id": "hkd-reporting",
            "bigquery_dataset_id": "your_dataset",
            "bigquery_table_id": "your_table",
            "schema_handling": "auto_detect",
            "custom_schema": [
                {"name": "column1", "type": "STRING", "mode": "NULLABLE"},
                {"name": "column2", "type": "INTEGER", "mode": "REQUIRED"}
            ]
        }
        
        print("Example configuration file:")
        print(json.dumps(example_config, indent=2))
        print("\nSave this to a JSON file and use with:")
        print("python job_helper.py execute --config-file your_config.json")

if __name__ == "__main__":
    main() 