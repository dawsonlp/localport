"""
Service Log Manager for LocalPort v0.3.4

Manages service-specific log files with rotation, retention, and metadata headers.
Provides the foundation for dual-stream logging architecture.
"""

import hashlib
import os
import platform
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import threading
import fcntl
import errno

import structlog

from localport.config.settings import get_settings

logger = structlog.get_logger(__name__)


class ServiceLogManager:
    """
    Manages service-specific log files with intelligent rotation and retention.
    
    Features:
    - Unique service IDs for each service instance
    - Metadata headers with diagnostic information
    - Size-based log rotation (configurable, default 10MB)
    - Time-based retention (configurable, default 3 days)
    - Thread-safe file operations with locking
    - Cross-platform compatibility
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._log_dir = self._get_log_directory()
        self._service_dir = self._log_dir / "services"
        self._active_logs: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        
        # Configuration from settings
        self.max_log_size = self.settings.get_service_log_rotation_size_bytes()
        self.retention_days = self.settings.service_log_retention_days
        self.buffer_size = self.settings.service_log_buffer_size
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _get_log_directory(self) -> Path:
        """Get the base log directory, creating if necessary."""
        return self.settings.get_daemon_log_directory()
    
    def _ensure_directories(self) -> None:
        """Ensure log directories exist with proper permissions."""
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._service_dir.mkdir(parents=True, exist_ok=True)
            
            # Set appropriate permissions (readable/writable by owner only)
            if platform.system() != "Windows":
                os.chmod(self._log_dir, 0o700)
                os.chmod(self._service_dir, 0o700)
                
        except OSError as e:
            logger.error("failed_to_create_log_directories", 
                        error=str(e), 
                        log_dir=str(self._log_dir))
            raise
    
    def generate_service_id(self, service_name: str) -> str:
        """
        Generate a unique service ID for this service instance.
        
        Format: {service_name}_{hash}
        Where hash is based on service name + current timestamp
        """
        timestamp = str(int(time.time() * 1000))  # millisecond precision
        hash_input = f"{service_name}_{timestamp}".encode('utf-8')
        hash_suffix = hashlib.sha256(hash_input).hexdigest()[:8]
        
        return f"{service_name}_{hash_suffix}"
    
    def create_service_log(self, service_name: str, service_config: Dict) -> Tuple[str, Path]:
        """
        Create a new service log file with metadata header.
        
        Args:
            service_name: Name of the service
            service_config: Service configuration dictionary
            
        Returns:
            Tuple of (service_id, log_file_path)
        """
        service_id = self.generate_service_id(service_name)
        log_file = self._service_dir / f"{service_id}.log"
        
        with self._lock:
            try:
                # Create log file with metadata header
                with open(log_file, 'w', encoding='utf-8') as f:
                    # Use file locking for thread safety
                    if platform.system() != "Windows":
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    
                    self._write_metadata_header(f, service_name, service_id, service_config)
                
                # Track active log
                self._active_logs[service_id] = {
                    'service_name': service_name,
                    'log_file': log_file,
                    'created_at': datetime.now(),
                    'size': log_file.stat().st_size if log_file.exists() else 0
                }
                
                logger.info("service_log_created", 
                           service_id=service_id,
                           service_name=service_name,
                           log_file=str(log_file))
                
                return service_id, log_file
                
            except OSError as e:
                logger.error("failed_to_create_service_log",
                            service_name=service_name,
                            service_id=service_id,
                            error=str(e))
                raise
    
    def _write_metadata_header(self, file_handle, service_name: str, service_id: str, service_config: Dict) -> None:
        """Write metadata header to service log file."""
        timestamp = datetime.now().isoformat() + 'Z'
        
        # Extract relevant config information
        local_port = service_config.get('local_port', 'unknown')
        target_info = f"{service_config.get('host', 'unknown')}:{service_config.get('port', 'unknown')}"
        connection_type = service_config.get('type', 'unknown')
        namespace = service_config.get('namespace', 'default')
        resource = service_config.get('resource', 'unknown')
        
        header = f"""=== SERVICE START: {service_name} ===
Timestamp: {timestamp}
Service ID: {service_id}
Process ID: {os.getpid()}
Local Port: :{local_port}
Target: {target_info}
Connection Type: {connection_type}
Namespace: {namespace}
Resource: {resource}
Platform: {platform.system()} {platform.release()}
LocalPort Version: 0.3.4
=== SUBPROCESS OUTPUT BEGINS ===
"""
        file_handle.write(header)
        file_handle.flush()
    
    def get_log_file_path(self, service_id: str) -> Optional[Path]:
        """Get the log file path for a service ID."""
        with self._lock:
            if service_id in self._active_logs:
                return self._active_logs[service_id]['log_file']
        return None
    
    def should_rotate_log(self, service_id: str) -> bool:
        """Check if a service log should be rotated based on size."""
        log_file = self.get_log_file_path(service_id)
        if not log_file or not log_file.exists():
            return False
        
        try:
            current_size = log_file.stat().st_size
            return current_size >= self.max_log_size
        except OSError:
            return False
    
    def rotate_log(self, service_id: str) -> Optional[Path]:
        """
        Rotate a service log file.
        
        Renames current log to .1, .2, etc. and creates new log file.
        Returns path to new log file.
        """
        with self._lock:
            log_file = self.get_log_file_path(service_id)
            if not log_file or not log_file.exists():
                return None
            
            try:
                # Find next rotation number
                rotation_num = 1
                while True:
                    rotated_path = log_file.with_suffix(f'.log.{rotation_num}')
                    if not rotated_path.exists():
                        break
                    rotation_num += 1
                
                # Rotate the file
                log_file.rename(rotated_path)
                
                # Create new log file (will be opened by caller)
                logger.info("service_log_rotated",
                           service_id=service_id,
                           old_file=str(rotated_path),
                           new_file=str(log_file))
                
                return log_file
                
            except OSError as e:
                logger.error("failed_to_rotate_service_log",
                            service_id=service_id,
                            error=str(e))
                return None
    
    def cleanup_old_logs(self) -> None:
        """Clean up service logs older than retention period."""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        
        try:
            for log_file in self._service_dir.glob("*.log*"):
                try:
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        log_file.unlink()
                        logger.info("service_log_cleaned_up",
                                   log_file=str(log_file),
                                   age_days=(datetime.now() - file_mtime).days)
                except OSError as e:
                    logger.warning("failed_to_cleanup_log_file",
                                  log_file=str(log_file),
                                  error=str(e))
        except OSError as e:
            logger.error("failed_to_cleanup_old_logs", error=str(e))
    
    def list_service_logs(self) -> List[Dict]:
        """
        List all available service logs with metadata.
        
        Returns:
            List of dictionaries with log information
        """
        logs = []
        
        try:
            for log_file in self._service_dir.glob("*.log"):
                try:
                    stat = log_file.stat()
                    
                    # Parse service name from filename
                    service_id = log_file.stem
                    service_name = service_id.rsplit('_', 1)[0] if '_' in service_id else service_id
                    
                    # Check if service is currently active
                    is_active = service_id in self._active_logs
                    
                    # Count rotated files
                    rotated_count = len(list(self._service_dir.glob(f"{service_id}.log.*")))
                    
                    logs.append({
                        'service_id': service_id,
                        'service_name': service_name,
                        'log_file': log_file,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'is_active': is_active,
                        'rotated_files': rotated_count
                    })
                    
                except OSError:
                    continue
                    
        except OSError as e:
            logger.error("failed_to_list_service_logs", error=str(e))
        
        return sorted(logs, key=lambda x: x['modified'], reverse=True)
    
    def remove_service_log(self, service_id: str) -> None:
        """Remove service log when service stops."""
        with self._lock:
            if service_id in self._active_logs:
                del self._active_logs[service_id]
                
                logger.info("service_log_removed",
                           service_id=service_id)
    
    def get_log_directory(self) -> Path:
        """Get the service logs directory path."""
        return self._service_dir


# Global instance
_service_log_manager = None


def get_service_log_manager() -> ServiceLogManager:
    """Get the global ServiceLogManager instance."""
    global _service_log_manager
    if _service_log_manager is None:
        _service_log_manager = ServiceLogManager()
    return _service_log_manager
