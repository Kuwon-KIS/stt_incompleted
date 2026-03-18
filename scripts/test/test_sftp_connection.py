#!/usr/bin/env python3
"""Test SFTP connection and directory structure.

Usage:
    python scripts/test/test_sftp_connection.py
    python scripts/test/test_sftp_connection.py --host 54.180.95.79   # Use public IP
    
This script:
    1. Tests SFTP connection to the dev server
    2. Lists available date directories
    3. Lists files in each date directory
    4. Compares with API response
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
import argparse
from app.config import config
from app.sftp_client import create_sftp_client, SFTPClient

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_sftp(host=None):
    """Test SFTP connection and list files."""
    # Allow override host via argument
    sftp_host = host if host else config.SFTP_HOST
    
    logger.info("=" * 80)
    logger.info("SFTP Connection Test")
    logger.info("=" * 80)
    logger.info(f"APP_ENV: {config.APP_ENV}")
    logger.info(f"SFTP_HOST: {sftp_host}")
    logger.info(f"SFTP_PORT: {config.SFTP_PORT}")
    logger.info(f"SFTP_USERNAME: {config.SFTP_USERNAME}")
    logger.info(f"SFTP_ROOT_PATH: {config.SFTP_ROOT_PATH}")
    logger.info(f"SFTP_KEY: {'<set>' if config.SFTP_KEY else '<not set>'}")
    logger.info("")
    
    try:
        logger.info("Connecting to SFTP...")
        # For public IP, create SFTPClient directly (not via factory)
        client = SFTPClient(
            host=sftp_host,
            port=config.SFTP_PORT,
            username=config.SFTP_USERNAME,
            password=config.SFTP_PASSWORD,
            pkey=config.SFTP_KEY
        )
        logger.info("Connected successfully")
        logger.info("")
        
        # Get available dates
        logger.info(f"Getting available dates from {config.SFTP_ROOT_PATH}...")
        available_dates = client.get_available_dates(root_path=config.SFTP_ROOT_PATH)
        logger.info(f"Found {len(available_dates)} dates: {available_dates}")
        logger.info("")
        
        # List files in each date
        root_path = config.SFTP_ROOT_PATH.rstrip('/')
        for date_str in available_dates[:3]:  # Only first 3 for testing
            date_path = f"{root_path}/{date_str}"
            logger.info(f"Listing files in {date_path}...")
            try:
                # First, try to list directory contents
                logger.info(f"  listdir({date_path})...")
                entries = client.listdir(date_path)
                logger.info(f"  Raw entries: {entries}")
                
                # Then, try list_files
                logger.info(f"  list_files({date_path}, suffix='.txt')...")
                files = client.list_files(path=date_path, suffix=".txt")
                logger.info(f"  Files found: {len(files)} - {files}")
            except Exception as e:
                logger.error(f"  Error: {e}", exc_info=True)
            logger.info("")
        
        client.close()
        logger.info("SFTP connection closed")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"SFTP connection failed: {e}", exc_info=True)
        logger.info("=" * 80)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test SFTP connection')
    parser.add_argument('--host', help='Override SFTP host (e.g., 54.180.95.79 for public IP)')
    args = parser.parse_args()
    
    test_sftp(host=args.host)
