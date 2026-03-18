import logging
import paramiko
import stat
from typing import List, Optional
import io
import base64
from datetime import datetime, timedelta
from .config import config

logger = logging.getLogger(__name__)

class MockSFTPClient:
    """Mock SFTP client for local development and testing.
    
    Returns dummy directory and file listings without connecting to a real server.
    Simulates the structure of a production SFTP server.
    """
    def __init__(self, host: str, port: int = 22, username: Optional[str] = None, 
                 password: Optional[str] = None, pkey: Optional[str] = None, timeout: int = 10):
        logger.info("Using MockSFTPClient (APP_ENV=local) - no real SFTP connection")
        self.host = host
        self.port = port
        self.username = username
        # Generate dummy date directories: last 7 days (for testing different scenarios)
        today = datetime.now()
        self.mock_dates = [
            (today - timedelta(days=i)).strftime("%Y%m%d")
            for i in range(7, 0, -1)  # 7 days ago to yesterday
        ]
        # Only mark first 3 as completed in DB (for testing partial/no overlap cases)
        self.mock_completed_dates = self.mock_dates[:3]
        # Sample files for each date (file names are timestamps with .txt extension)
        self.mock_files = {
            date: [
                f"{date}_001.txt",
                f"{date}_002.txt",
                f"{date}_003.txt",
            ]
            for date in self.mock_dates
        }
    
    def listdir(self, path: str = ".") -> List[str]:
        """Mock listdir - returns date directories and files."""
        logger.debug("MockSFTPClient.listdir path=%s", path)
        # Root returns date directories
        if path == "/" or path == ".":
            return self.mock_dates
        # Subdirectory returns files
        for date in self.mock_dates:
            if path == f"/{date}" or path == date:
                return self.mock_files[date]
        return []
    
    def list_files(self, path: str, suffix: Optional[str] = None) -> List[str]:
        """Mock list_files - returns files in directory with optional suffix filter."""
        logger.debug("MockSFTPClient.list_files path=%s suffix=%s", path, suffix)
        files = self.listdir(path)
        if suffix:
            files = [f for f in files if f.endswith(suffix)]
        return files
    
    def list_directories(self, path: str) -> List[str]:
        """Mock list_directories - returns subdirectories."""
        logger.debug("MockSFTPClient.list_directories path=%s", path)
        # Root contains date directories
        if path == "/" or path == ".":
            return self.mock_dates
        return []
    
    def get_available_dates(self, root_path: str = "/") -> List[str]:
        """Get list of available dates (YYYYMMDD format) from mock data.
        
        Args:
            root_path: Root path to search (ignored for mock, always uses mock_dates)
            
        Returns:
            Sorted list of dates in YYYYMMDD format
        """
        logger.info(f"MockSFTPClient.get_available_dates: returning {len(self.mock_dates)} mock dates")
        return sorted(self.mock_dates)
    
    def read_file(self, path: str) -> str:
        """Mock read_file - returns dummy content for testing."""
        logger.debug("MockSFTPClient.read_file path=%s", path)
        # Return sample text content that can be processed
        sample_content = """고객과의 통화 기록
시간: 2026-03-16 10:00:00
상담사: 홍길동
고객명: 김철수

상담내용:
- 상품 설명: 우리 신상품 XX는 매우 좋은 제품입니다.
- 가격: 299,000원입니다.
- 특징: 최고의 품질과 가성비를 자랑합니다.
- 구매 권유: 지금 구매하시면 특별 할인이 있습니다.

결과: 고객이 구매에 동의했습니다.
"""
        return sample_content
    
    def close(self):
        """Mock close - no-op."""
        logger.debug("MockSFTPClient.close")

class SFTPClient:
    """Lightweight wrapper around Paramiko SFTP.

    Usage:
        client = SFTPClient(host, username=..., password=...)
        client.listdir("/")
        client.close()
    """
    def __init__(self, host: str, port: int = 22, username: Optional[str] = None, password: Optional[str] = None, pkey: Optional[str] = None, timeout: int = 10):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.sftp = None
        try:
            logger.info("Connecting to SFTP host=%s port=%s user=%s", host, port, username)
            if pkey:
                # Try to load as file path first
                try:
                    key = paramiko.RSAKey.from_private_key_file(pkey)
                    logger.info("Loaded SSH key from file: %s", pkey)
                except (FileNotFoundError, IOError):
                    # If file doesn't exist, treat as base64-encoded key content
                    try:
                        key_bytes = base64.b64decode(pkey)
                        key_file = io.StringIO(key_bytes.decode('utf-8'))
                        key = paramiko.RSAKey.from_private_key(key_file)
                        logger.info("Loaded SSH key from base64-encoded content")
                    except Exception as e:
                        logger.error("Failed to parse SSH key as file or base64: %s", e)
                        raise ValueError(f"Invalid SSH key format: {e}")
                
                self.client.connect(hostname=host, port=port, username=username, pkey=key, timeout=timeout)
            else:
                self.client.connect(hostname=host, port=port, username=username, password=password, timeout=timeout)
            self.sftp = self.client.open_sftp()
            logger.info("SFTP connection established to %s", host)
        except Exception:
            logger.exception("Failed to connect to SFTP %s", host)
            # cleanup on failure
            self.close()
            raise

    def listdir(self, path: str = ".") -> List[str]:
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")

        logger.debug("Listing sftp path=%s", path)
        return self.sftp.listdir(path)

    def upload(self, local_path: str, remote_path: str):
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")
        return self.sftp.put(local_path, remote_path)

    def download(self, remote_path: str, local_path: str):
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")
        return self.sftp.get(remote_path, local_path)

    def read_file(self, remote_path: str, encoding: str = "utf-8") -> str:
        """Read a remote text file and return its contents as a string."""
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")
        logger.debug("Reading remote file %s", remote_path)
        with self.sftp.open(remote_path, "rb") as f:
            data = f.read()
        if isinstance(data, bytes):
            return data.decode(encoding, errors='replace')
        return str(data)

    def list_files(self, path: str, suffix: str = None) -> List[str]:
        """List all files in a directory, optionally filtered by suffix.
        
        Args:
            path: Remote directory path
            suffix: Optional file suffix filter (e.g., ".txt")
            
        Returns:
            List of filenames
        """
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")
        
        logger.debug("Listing files in sftp path=%s with suffix=%s", path, suffix)
        try:
            entries = self.sftp.listdir(path)
            files = []
            for entry in entries:
                full_path = f"{path}/{entry}".replace("//", "/")
                try:
                    # Check if it's a file (not a directory)
                    file_stat = self.sftp.stat(full_path)
                    # S_ISREG checks if it's a regular file
                    if stat.S_ISREG(file_stat.st_mode):
                        if suffix is None or entry.endswith(suffix):
                            files.append(entry)
                except IOError:
                    # Skip if we can't stat (permission denied, etc.)
                    pass
            return files
        except FileNotFoundError:
            logger.warning("Directory not found: %s", path)
            return []

    def list_directories(self, path: str) -> List[str]:
        """List all subdirectories in a directory.
        
        Args:
            path: Remote directory path
            
        Returns:
            List of directory names
        """
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")
        
        logger.debug("Listing directories in sftp path=%s", path)
        try:
            entries = self.sftp.listdir(path)
            directories = []
            for entry in entries:
                full_path = f"{path}/{entry}".replace("//", "/")
                try:
                    file_stat = self.sftp.stat(full_path)
                    # S_ISDIR checks if it's a directory
                    if stat.S_ISDIR(file_stat.st_mode):
                        directories.append(entry)
                except IOError:
                    pass
            return directories
        except FileNotFoundError:
            logger.warning("Directory not found: %s", path)
            return []

    def get_available_dates(self, root_path: str = "/") -> List[str]:
        """Get list of available dates (YYYYMMDD format) from SFTP root directory.
        
        Scans the root directory and returns only entries that match YYYYMMDD format.
        
        Args:
            root_path: Root path to search (default: "/")
            
        Returns:
            Sorted list of dates in YYYYMMDD format
            
        Raises:
            RuntimeError: If SFTP connection not established
            Exception: If directory listing fails
        """
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")
        
        logger.info(f"Scanning SFTP {root_path} for available dates")
        try:
            entries = self.list_directories(root_path)
            dates = []
            
            for entry in entries:
                if self._is_valid_date_format(entry):
                    dates.append(entry)
            
            dates = sorted(dates)
            logger.info(f"Found {len(dates)} available dates in SFTP: {dates}")
            return dates
        
        except Exception as e:
            logger.error(f"Failed to get available dates from SFTP {root_path}: {e}")
            raise
    
    @staticmethod
    def _is_valid_date_format(value: str) -> bool:
        """Check if value is valid YYYYMMDD format date.
        
        Args:
            value: String to validate
            
        Returns:
            True if value matches YYYYMMDD format and represents valid date
        """
        try:
            datetime.strptime(value, "%Y%m%d")
            return True
        except (ValueError, TypeError):
            return False

    def close(self):
        try:
            if self.sftp:
                self.sftp.close()
        except Exception:
            pass
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass

def create_sftp_client(host: str, port: int = 22, username: Optional[str] = None, 
                       password: Optional[str] = None, pkey: Optional[str] = None, 
                       timeout: int = 10):
    """Factory function to create appropriate SFTP client based on environment.
    
    Args:
        host: SFTP server hostname
        port: SFTP server port (default: 22)
        username: Username for authentication
        password: Password for authentication
        pkey: SSH private key (file path or base64-encoded content)
        timeout: Connection timeout in seconds
        
    Returns:
        MockSFTPClient if APP_ENV=local, otherwise real SFTPClient
    """
    if config.APP_ENV == "local":
        return MockSFTPClient(host, port, username, password, pkey, timeout)
    else:
        return SFTPClient(host, port, username, password, pkey, timeout)