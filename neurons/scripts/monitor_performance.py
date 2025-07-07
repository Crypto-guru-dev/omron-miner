#!/usr/bin/env python3
"""
Performance monitoring script for Omron subnet miner.
Tracks key metrics to help optimize for high scores.
"""

import time
import json
import os
import psutil
import threading
from datetime import datetime
from pathlib import Path
import bittensor as bt

class PerformanceMonitor:
    def __init__(self, log_file="miner_performance.log"):
        self.log_file = log_file
        self.metrics = {
            "proof_times": [],
            "overhead_times": [],
            "total_response_times": [],
            "success_rate": 0,
            "error_count": 0,
            "start_time": time.time()
        }
        self.lock = threading.Lock()
        
    def log_proof_metrics(self, proof_time: float, overhead_time: float, total_time: float, success: bool = True):
        """Log proof generation metrics."""
        with self.lock:
            self.metrics["proof_times"].append(proof_time)
            self.metrics["overhead_times"].append(overhead_time)
            self.metrics["total_response_times"].append(total_time)
            
            if success:
                self.metrics["success_rate"] = len([t for t in self.metrics["total_response_times"] if t < 45]) / len(self.metrics["total_response_times"])
            else:
                self.metrics["error_count"] += 1
                
            # Keep only last 1000 entries to prevent memory bloat
            if len(self.metrics["proof_times"]) > 1000:
                self.metrics["proof_times"] = self.metrics["proof_times"][-1000:]
                self.metrics["overhead_times"] = self.metrics["overhead_times"][-1000:]
                self.metrics["total_response_times"] = self.metrics["total_response_times"][-1000:]
    
    def get_system_metrics(self):
        """Get current system resource usage."""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / (1024**3)
        }
    
    def get_performance_summary(self):
        """Get performance summary statistics."""
        with self.lock:
            if not self.metrics["proof_times"]:
                return "No metrics available yet"
            
            proof_times = self.metrics["proof_times"]
            overhead_times = self.metrics["overhead_times"]
            total_times = self.metrics["total_response_times"]
            
            summary = {
                "total_requests": len(total_times),
                "success_rate": self.metrics["success_rate"] * 100,
                "error_count": self.metrics["error_count"],
                "avg_proof_time": sum(proof_times) / len(proof_times),
                "avg_overhead_time": sum(overhead_times) / len(overhead_times),
                "avg_total_time": sum(total_times) / len(total_times),
                "min_proof_time": min(proof_times),
                "max_proof_time": max(proof_times),
                "timeout_count": len([t for t in total_times if t > 45]),
                "uptime_hours": (time.time() - self.metrics["start_time"]) / 3600
            }
            
            return summary
    
    def log_performance(self):
        """Log current performance metrics."""
        summary = self.get_performance_summary()
        system_metrics = self.get_system_metrics()
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "performance": summary,
            "system": system_metrics
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        # Print summary to console
        print(f"\n=== Performance Summary ===")
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Avg Proof Time: {summary['avg_proof_time']:.3f}s")
        print(f"Avg Overhead: {summary['avg_overhead_time']:.3f}s")
        print(f"Avg Total Time: {summary['avg_total_time']:.3f}s")
        print(f"Timeout Count: {summary['timeout_count']}")
        print(f"CPU Usage: {system_metrics['cpu_percent']:.1f}%")
        print(f"Memory Usage: {system_metrics['memory_percent']:.1f}%")
        print(f"Uptime: {summary['uptime_hours']:.1f} hours")
        print("=" * 30)

def monitor_miner_logs(log_file_path="/tmp/omron/miner.log"):
    """Monitor miner logs for performance metrics."""
    monitor = PerformanceMonitor()
    
    if not os.path.exists(log_file_path):
        print(f"Log file not found: {log_file_path}")
        print("Make sure your miner is running and logging to this path")
        return
    
    print(f"Monitoring miner logs: {log_file_path}")
    print("Press Ctrl+C to stop monitoring")
    
    try:
        with open(log_file_path, 'r') as f:
            # Go to end of file
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    # Parse performance metrics from log lines
                    if "Optimized response - Total:" in line:
                        try:
                            # Extract timing information
                            parts = line.split("Total: ")[1].split(",")
                            total_time = float(parts[0].replace("s", ""))
                            proof_time = float(parts[1].split(": ")[1].replace("s", ""))
                            overhead_time = float(parts[2].split(": ")[1].replace("s", ""))
                            
                            success = total_time < 45  # 45 second timeout
                            monitor.log_proof_metrics(proof_time, overhead_time, total_time, success)
                            
                        except Exception as e:
                            print(f"Error parsing log line: {e}")
                
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
    except KeyboardInterrupt:
        print("\nStopping performance monitoring...")
        monitor.log_performance()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor miner performance")
    parser.add_argument("--log-file", default="/tmp/omron/miner.log", 
                       help="Path to miner log file")
    parser.add_argument("--interval", type=int, default=60,
                       help="Performance summary interval in seconds")
    
    args = parser.parse_args()
    
    # Start monitoring
    monitor_miner_logs(args.log_file) 