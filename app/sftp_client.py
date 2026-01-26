import logging
import paramiko
from typing import List, Optional

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
                key = paramiko.RSAKey.from_private_key_file(pkey)
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
        with self.sftp.open(remote_path, "r") as f:
            data = f.read()
            if isinstance(data, bytes):
                return data.decode(encoding)
            return str(data)

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
