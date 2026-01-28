import logging
import paramiko
from typing import List, Optional
import io
import base64

logger = logging.getLogger(__name__)

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
                    stat = self.sftp.stat(full_path)
                    # S_ISREG checks if it's a regular file
                    if paramiko.stat.S_ISREG(stat.st_mode):
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
                    stat = self.sftp.stat(full_path)
                    # S_ISDIR checks if it's a directory
                    if paramiko.stat.S_ISDIR(stat.st_mode):
                        directories.append(entry)
                except IOError:
                    pass
            return directories
        except FileNotFoundError:
            logger.warning("Directory not found: %s", path)
            return []

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
