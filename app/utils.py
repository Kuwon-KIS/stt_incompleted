"""
Utility functions for STT processing system.
"""

import logging
import os
import re
from typing import Optional, Dict, Any


def get_credentials_from_env(credential_name: str, default_username: Optional[str] = None,
                              default_password: Optional[str] = None,
                              default_key: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Load SFTP credentials from environment variables.
    
    Environment variable naming convention:
    SFTP_CRED_{credential_name}_USERNAME
    SFTP_CRED_{credential_name}_PASSWORD
    SFTP_CRED_{credential_name}_KEY
    
    Args:
        credential_name: Name of the credential set
        default_username: Default value if env var not found
        default_password: Default value if env var not found
        default_key: Default value if env var not found
        
    Returns:
        Dictionary with username, password, key
    """
    cred_prefix = f"SFTP_CRED_{credential_name.upper()}"
    
    return {
        "username": os.getenv(f"{cred_prefix}_USERNAME") or default_username,
        "password": os.getenv(f"{cred_prefix}_PASSWORD") or default_password,
        "key": os.getenv(f"{cred_prefix}_KEY") or default_key,
    }


def resolve_sftp_credentials(credential_name: Optional[str],
                            username: Optional[str],
                            password: Optional[str],
                            key: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Resolve SFTP credentials with priority: env -> request -> default.
    
    Args:
        credential_name: Name to load from environment
        username: Username from request
        password: Password from request
        key: Key from request
        
    Returns:
        Dictionary with resolved username, password, key
    """
    if credential_name:
        env_creds = get_credentials_from_env(credential_name, username, password, key)
        return {
            "username": env_creds["username"] or username,
            "password": env_creds["password"] or password,
            "key": env_creds["key"] or key,
        }
    
    return {"username": username, "password": password, "key": key}


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger
    """
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        level=getattr(logging, log_level.upper(), logging.INFO)
    )
    return logging.getLogger(__name__)


def format_date_range(start_date: str, end_date: str) -> str:
    """
    Format date range for display.
    
    Args:
        start_date: Start date (YYYYMMDD format)
        end_date: End date (YYYYMMDD format)
        
    Returns:
        Formatted date range string
    """
    return f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]} to {end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"


def validate_date_format(date_str: str) -> bool:
    """
    Validate date string in YYYYMMDD format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        True if valid YYYYMMDD format, False otherwise
    """
    if not date_str or not isinstance(date_str, str):
        return False
    
    pattern = r'^\d{8}$'
    return bool(re.match(pattern, date_str))


def is_retriable_error(status_code: int) -> bool:
    """
    Check if an HTTP error is retriable.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        True if error is retriable (5xx or 429), False otherwise
    """
    return 500 <= status_code < 600 or status_code == 429


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing/replacing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Replace invalid characters with underscore
    invalid_chars = r'[<>:"/\\|?*]'
    return re.sub(invalid_chars, '_', filename)


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate string to max length with optional suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_error_message(error: Exception) -> str:
    """
    Extract human-readable error message from exception.
    
    Args:
        error: Exception object
        
    Returns:
        Error message string
    """
    if hasattr(error, 'detail'):
        return str(error.detail)
    elif hasattr(error, 'message'):
        return str(error.message)
    else:
        return str(error)
