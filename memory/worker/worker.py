
"""
Memory Worker for Sentinel
Handles memory management tasks asynchronously
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import threading
import time
import json
import os


@dataclass
class Task:
    """A memory management task"""
    task_id: str
    task_type: str  # "cleanup", "summarize", "index", "compact"
    priority: int = 1
    status: str = "pending"
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None


class MemoryWorker:
    """
    Background worker for memory management tasks
    Handles cleanup, summarization, indexing, and compaction
    """
    
    def __init__(self):
        self.tasks: List[Task] = []
        self.task_counter = 0
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.cleanup_interval = 3600  # 1 hour
        self.log_file: Optional[str] = None
    
    def start(self, interval: int = 3600, log_path: Optional[str] = None):
        """Start the worker thread"""
        self.cleanup_interval = interval
        self.log_file = log_path
        
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the worker"""
        self.running = False
    
    def _worker_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                self._process_pending_tasks()
                time.sleep(self.cleanup_interval)
            except Exception as e:
                self._log(f"Worker error: {str(e)}")
    
    def _process_pending_tasks(self):
        """Process pending tasks"""
        pending = [t for t in self.tasks if t.status == "pending"]
        
        for task in pending:
            if task.task_type == "cleanup":
                self._run_cleanup_task(task)
            elif task.task_type == "summarize":
                self._run_summarize_task(task)
            elif task.task_type == "index":
                self._run_index_task(task)
            elif task.task_type == "compact":
                self._run_compact_task(task)
        
        # Clean up completed tasks
        self.tasks = [t for t in self.tasks if t.status != "completed"]
    
    def _run_cleanup_task(self, task: Task):
        """Run a cleanup task"""
        task.status = "running"
        
        try:
            # Cleanup logic would go here
            # Remove old session memories older than threshold
            # Clear temporary files
            
            result = "Cleanup completed"
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now()
            self._log(f"Task {task.task_id} completed: {result}")
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self._log(f"Task {task.task_id} failed: {str(e)}")
    
    def _run_summarize_task(self, task: Task):
        """Run a summarization task"""
        task.status = "running"
        
        try:
            # Summarize recent conversation into an episode
            # This would call the episode store
            
            result = "Summarization completed"
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now()
            self._log(f"Task {task.task_id} completed: {result}")
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self._log(f"Task {task.task_id} failed: {str(e)}")
    
    def _run_index_task(self, task: Task):
        """Run an indexing task"""
        task.status = "running"
        
        try:
            # Build indexes for faster retrieval
            # This would update index files
            
            result = "Indexing completed"
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now()
            self._log(f"Task {task.task_id} completed: {result}")
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self._log(f"Task {task.task_id} failed: {str(e)}")
    
    def _run_compact_task(self, task: Task):
        """Run a compaction task"""
        task.status = "running"
        
        try:
            # Compact memory layers
            # Move infrequently accessed data to slower storage
            
            result = "Compaction completed"
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now()
            self._log(f"Task {task.task_id} completed: {result}")
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self._log(f"Task {task.task_id} failed: {str(e)}")
    
    def add_task(self, task_type: str, priority: int = 1) -> Task:
        """Add a new task"""
        self.task_counter += 1
        task = Task(
            task_id=f"task_{self.task_counter:04d}",
            task_type=task_type,
            priority=priority,
            created_at=datetime.now()
        )
        self.tasks.append(task)
        return task
    
    def submit_cleanup(self):
        """Submit a cleanup task"""
        return self.add_task("cleanup")
    
    def submit_summarize(self):
        """Submit a summarization task"""
        return self.add_task("summarize")
    
    def submit_index(self):
        """Submit an indexing task"""
        return self.add_task("index")
    
    def submit_compact(self):
        """Submit a compaction task"""
        return self.add_task("compact")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def list_tasks(self) -> List[Dict]:
        """List all tasks"""
        return [
            {
                "id": t.task_id,
                "type": t.task_type,
                "priority": t.priority,
                "status": t.status,
                "created": t.created_at.isoformat() if t.created_at else None,
                "completed": t.completed_at.isoformat() if t.completed_at else None,
                "result": t.result,
                "error": t.error
            }
            for t in self.tasks
        ]
    
    def _log(self, message: str):
        """Log a message"""
        if self.log_file:
            timestamp = datetime.now().isoformat()
            with open(self.log_file, 'a') as f:
                f.write(f"[{timestamp}] {message}\n")
        else:
            print(f"[MemoryWorker] {message}")
    
    def log_task(self, task: Task, message: str):
        """Log a task operation"""
        self._log(f"Task {task.task_id}: {message}")


# Global worker instance
_worker: Optional[MemoryWorker] = None


def get_worker() -> MemoryWorker:
    """Get or create the memory worker"""
    global _worker
    if _worker is None:
        _worker = MemoryWorker()
    return _worker


def start_worker(interval: int = 3600, log_path: Optional[str] = None):
    """Start the memory worker"""
    worker = get_worker()
    worker.start(interval, log_path)
    return worker


def submit_cleanup_task() -> Task:
    """Submit a cleanup task"""
    return get_worker().submit_cleanup()


def submit_summarize_task() -> Task:
    """Submit a summarization task"""
    return get_worker().submit_summarize()
