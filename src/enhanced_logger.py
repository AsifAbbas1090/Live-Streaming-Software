#!/usr/bin/env python3
"""
Enhanced Logging System for GB28181 Restreamer
Provides detailed logging with real-time catalog exchange monitoring and thread safety.
"""

import logging
import logging.handlers
import threading
import time
import os
import json
from datetime import datetime
from pathlib import Path

class GB28181Logger:
    """Enhanced logger with SIP message tracking and catalog exchange monitoring"""
    
    def __init__(self, config=None, log_dir="logs"):
        self.config = config or {}
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Thread-safe logging
        self._log_lock = threading.Lock()
        
        # Catalog exchange tracking
        self.catalog_exchanges = []
        self.catalog_lock = threading.Lock()
        
        # Setup loggers
        self._setup_main_logger()
        self._setup_sip_logger()
        self._setup_catalog_logger()
        self._setup_timing_logger()
        
        # Start background logger maintenance
        self._start_maintenance_thread()
    
    def _setup_main_logger(self):
        """Setup main application logger"""
        self.main_logger = logging.getLogger('gb28181.main')
        self.main_logger.setLevel(logging.DEBUG)
        
        # Console handler with color support
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        # File handler with detailed format
        main_log_file = self.log_dir / 'gb28181_main.log'
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(threadName)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        self.main_logger.addHandler(console_handler)
        self.main_logger.addHandler(file_handler)
    
    def _setup_sip_logger(self):
        """Setup SIP-specific logger"""
        self.sip_logger = logging.getLogger('gb28181.sip')
        self.sip_logger.setLevel(logging.DEBUG)
        
        # SIP-specific file handler
        sip_log_file = self.log_dir / 'gb28181_sip.log'
        sip_handler = logging.handlers.RotatingFileHandler(
            sip_log_file, maxBytes=50*1024*1024, backupCount=10
        )
        sip_handler.setLevel(logging.DEBUG)
        sip_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [SIP] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )
        sip_handler.setFormatter(sip_formatter)
        self.sip_logger.addHandler(sip_handler)
        
        # Also log SIP messages to main logger
        self.sip_logger.parent = self.main_logger
    
    def _setup_catalog_logger(self):
        """Setup catalog exchange logger"""
        self.catalog_logger = logging.getLogger('gb28181.catalog')
        self.catalog_logger.setLevel(logging.DEBUG)
        
        # Catalog-specific file handler
        catalog_log_file = self.log_dir / 'gb28181_catalog.log'
        catalog_handler = logging.handlers.RotatingFileHandler(
            catalog_log_file, maxBytes=20*1024*1024, backupCount=5
        )
        catalog_handler.setLevel(logging.DEBUG)
        catalog_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [CATALOG] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )
        catalog_handler.setFormatter(catalog_formatter)
        self.catalog_logger.addHandler(catalog_handler)
    
    def _setup_timing_logger(self):
        """Setup timing analysis logger"""
        self.timing_logger = logging.getLogger('gb28181.timing')
        self.timing_logger.setLevel(logging.DEBUG)
        
        # Timing-specific file handler
        timing_log_file = self.log_dir / 'gb28181_timing.log'
        timing_handler = logging.handlers.RotatingFileHandler(
            timing_log_file, maxBytes=10*1024*1024, backupCount=3
        )
        timing_handler.setLevel(logging.DEBUG)
        timing_formatter = logging.Formatter(
            '[%(asctime)s] [TIMING] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )
        timing_handler.setFormatter(timing_formatter)
        self.timing_logger.addHandler(timing_handler)
    
    def _start_maintenance_thread(self):
        """Start background maintenance thread"""
        maintenance_thread = threading.Thread(
            target=self._maintenance_worker,
            daemon=True,
            name="LoggerMaintenance"
        )
        maintenance_thread.start()
    
    def _maintenance_worker(self):
        """Background worker for log maintenance"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                self._cleanup_old_logs()
                self._generate_periodic_reports()
            except Exception as e:
                self.main_logger.error(f"Error in logger maintenance: {e}")
    
    def _cleanup_old_logs(self):
        """Clean up old log files"""
        try:
            # Remove logs older than 7 days
            cutoff_time = time.time() - (7 * 24 * 3600)
            
            for log_file in self.log_dir.glob("*.log.*"):
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    self.main_logger.debug(f"Cleaned up old log file: {log_file}")
                    
        except Exception as e:
            self.main_logger.error(f"Error cleaning up logs: {e}")
    
    def _generate_periodic_reports(self):
        """Generate periodic status reports"""
        try:
            with self.catalog_lock:
                if self.catalog_exchanges:
                    recent_exchanges = [
                        ex for ex in self.catalog_exchanges
                        if time.time() - ex.get('timestamp', 0) < 3600  # Last hour
                    ]
                    
                    if recent_exchanges:
                        success_count = sum(1 for ex in recent_exchanges if ex.get('success', False))
                        success_rate = (success_count / len(recent_exchanges)) * 100
                        
                        self.catalog_logger.info(
                            f"Hourly Report: {len(recent_exchanges)} catalog exchanges, "
                            f"{success_rate:.1f}% success rate"
                        )
                        
        except Exception as e:
            self.main_logger.error(f"Error generating periodic report: {e}")
    
    def log_catalog_query_received(self, sn, device_id, source_ip=None):
        """Log incoming catalog query"""
        timestamp = time.time()
        
        with self.catalog_lock:
            exchange = {
                'type': 'query',
                'sn': sn,
                'device_id': device_id,
                'source_ip': source_ip,
                'timestamp': timestamp,
                'query_time': timestamp
            }
            self.catalog_exchanges.append(exchange)
        
        self.catalog_logger.info(
            f"📥 QUERY RECEIVED: SN={sn}, DeviceID={device_id}, Source={source_ip}"
        )
        self.timing_logger.info(f"QUERY_START,{sn},{timestamp}")
    
    def log_catalog_response_sent(self, sn, device_count, response_size, success=True):
        """Log outgoing catalog response"""
        timestamp = time.time()
        
        with self.catalog_lock:
            # Find matching query
            for exchange in reversed(self.catalog_exchanges):
                if exchange.get('sn') == sn and exchange.get('type') == 'query':
                    exchange.update({
                        'response_time': timestamp,
                        'device_count': device_count,
                        'response_size': response_size,
                        'success': success,
                        'duration': timestamp - exchange['query_time']
                    })
                    break
        
        status = "✅ SUCCESS" if success else "❌ FAILED"
        self.catalog_logger.info(
            f"📤 RESPONSE SENT: {status}, SN={sn}, Devices={device_count}, "
            f"Size={response_size}B"
        )
        self.timing_logger.info(f"RESPONSE_SENT,{sn},{timestamp},{success}")
    
    def log_catalog_timing(self, sn, phase, duration):
        """Log detailed timing for catalog operations"""
        self.timing_logger.info(f"TIMING,{sn},{phase},{duration:.6f}")
        
        if duration > 5.0:  # Log slow operations
            self.catalog_logger.warning(
                f"⚠️ SLOW OPERATION: SN={sn}, Phase={phase}, Duration={duration:.3f}s"
            )
    
    def log_sip_message(self, direction, message_type, content_preview=None, size=None):
        """Log SIP message exchange"""
        timestamp = time.time()
        
        self.sip_logger.info(
            f"{direction} {message_type}" + 
            (f" ({size}B)" if size else "") +
            (f" - {content_preview}" if content_preview else "")
        )
    
    def log_thread_safety_event(self, event_type, thread_name, details=None):
        """Log thread safety events"""
        self.main_logger.debug(
            f"🔒 THREAD_SAFETY: {event_type} in {thread_name}" +
            (f" - {details}" if details else "")
        )
    
    def get_catalog_statistics(self, hours=24):
        """Get catalog exchange statistics"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.catalog_lock:
            recent_exchanges = [
                ex for ex in self.catalog_exchanges
                if ex.get('timestamp', 0) > cutoff_time
            ]
            
            if not recent_exchanges:
                return {}
            
            successful = [ex for ex in recent_exchanges if ex.get('success', False)]
            durations = [ex['duration'] for ex in successful if 'duration' in ex]
            
            stats = {
                'total_queries': len(recent_exchanges),
                'successful_responses': len(successful),
                'success_rate': (len(successful) / len(recent_exchanges)) * 100,
                'avg_response_time': sum(durations) / len(durations) if durations else 0,
                'max_response_time': max(durations) if durations else 0,
                'min_response_time': min(durations) if durations else 0
            }
            
            return stats
    
    def save_catalog_report(self):
        """Save detailed catalog exchange report"""
        try:
            stats = self.get_catalog_statistics()
            report_file = self.log_dir / f"catalog_report_{int(time.time())}.json"
            
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'statistics': stats,
                'recent_exchanges': self.catalog_exchanges[-100:]  # Last 100 exchanges
            }
            
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            self.main_logger.info(f"📊 Catalog report saved: {report_file}")
            return str(report_file)
            
        except Exception as e:
            self.main_logger.error(f"Error saving catalog report: {e}")
            return None


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m'  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


# Global logger instance
_logger_instance = None

def get_logger(config=None):
    """Get or create the global logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = GB28181Logger(config)
    return _logger_instance

def log_catalog_query(sn, device_id, source_ip=None):
    """Convenience function for logging catalog queries"""
    logger = get_logger()
    logger.log_catalog_query_received(sn, device_id, source_ip)

def log_catalog_response(sn, device_count, response_size, success=True):
    """Convenience function for logging catalog responses"""
    logger = get_logger()
    logger.log_catalog_response_sent(sn, device_count, response_size, success)

def log_timing(sn, phase, duration):
    """Convenience function for logging timing"""
    logger = get_logger()
    logger.log_catalog_timing(sn, phase, duration)

def log_sip_message(direction, message_type, content_preview=None, size=None):
    """Convenience function for logging SIP messages"""
    logger = get_logger()
    logger.log_sip_message(direction, message_type, content_preview, size)


if __name__ == "__main__":
    # Test the enhanced logging system
    import time
    
    logger = get_logger()
    
    # Test catalog exchange logging
    logger.log_catalog_query_received("123456", "81000000465001000001", "192.168.1.100")
    time.sleep(0.1)
    logger.log_catalog_response_sent("123456", 42, 15000, True)
    
    # Test timing logging
    logger.log_catalog_timing("123456", "video_scan", 2.5)
    logger.log_catalog_timing("123456", "xml_generation", 0.1)
    
    # Test SIP message logging
    logger.log_sip_message("INCOMING", "MESSAGE", "Catalog query", 500)
    logger.log_sip_message("OUTGOING", "MESSAGE", "Catalog response", 15000)
    
    # Generate report
    report_file = logger.save_catalog_report()
    print(f"Test report saved: {report_file}")
    
    # Show statistics
    stats = logger.get_catalog_statistics()
    print(f"Statistics: {stats}") 