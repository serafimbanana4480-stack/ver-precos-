"""
Task queue for managing scraping tasks.
"""
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Callable
import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority enumeration."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Task:
    """Task data class."""
    id: str
    task_type: str
    parameters: Dict[str, Any]
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300  # 5 minutes default


class TaskQueue:
    """Task queue for managing scraping tasks."""
    
    def __init__(self, queue_file: str = "task_queue.pkl", max_size: int = 1000):
        """Initialize task queue."""
        self.queue_file = Path(queue_file)
        self.max_size = max_size
        self.tasks = {}
        self.task_queue = []
        self.running_tasks = {}
        self.completed_tasks = {}
        self.failed_tasks = {}
        
        self._load_queue()
        
        logger.info(f"Task queue initialized: {len(self.tasks)} tasks loaded")
    
    def _load_queue(self):
        """Load queue from file."""
        
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'rb') as f:
                    data = pickle.load(f)
                
                self.tasks = data.get('tasks', {})
                self.task_queue = data.get('task_queue', [])
                self.running_tasks = data.get('running_tasks', {})
                self.completed_tasks = data.get('completed_tasks', {})
                self.failed_tasks = data.get('failed_tasks', {})
                
                logger.info(f"Loaded {len(self.tasks)} tasks from queue file")
                
            except Exception as e:
                logger.error(f"Error loading task queue: {e}")
                self._initialize_empty_queue()
        else:
            self._initialize_empty_queue()
    
    def _initialize_empty_queue(self):
        """Initialize empty queue."""
        
        self.tasks = {}
        self.task_queue = []
        self.running_tasks = {}
        self.completed_tasks = {}
        self.failed_tasks = {}
    
    def _save_queue(self):
        """Save queue to file."""
        
        try:
            data = {
                'tasks': self.tasks,
                'task_queue': self.task_queue,
                'running_tasks': self.running_tasks,
                'completed_tasks': self.completed_tasks,
                'failed_tasks': self.failed_tasks
            }
            
            with open(self.queue_file, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            logger.error(f"Error saving task queue: {e}")
    
    def add_task(self, 
                 task_type: str, 
                 parameters: Dict[str, Any],
                 priority: TaskPriority = TaskPriority.NORMAL,
                 max_retries: int = 3,
                 timeout: int = 300) -> str:
        """Add a task to the queue."""
        
        if len(self.tasks) >= self.max_size:
            logger.warning("Task queue is full, cannot add new task")
            return ""
        
        task_id = str(uuid.uuid4())
        
        task = Task(
            id=task_id,
            task_type=task_type,
            parameters=parameters,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            max_retries=max_retries,
            timeout=timeout
        )
        
        self.tasks[task_id] = task
        
        # Add to priority queue
        self._add_to_priority_queue(task)
        
        self._save_queue()
        
        logger.info(f"Added task {task_id} of type {task_type} to queue")
        return task_id
    
    def _add_to_priority_queue(self, task: Task):
        """Add task to priority queue in correct position."""
        
        insert_index = 0
        
        for i, queued_task_id in enumerate(self.task_queue):
            queued_task = self.tasks[queued_task_id]
            
            if task.priority.value > queued_task.priority.value:
                insert_index = i
                break
            elif task.priority.value == queued_task.priority.value:
                if task.created_at < queued_task.created_at:
                    insert_index = i
                    break
        
        self.task_queue.insert(insert_index, task.id)
    
    def get_next_task(self) -> Optional[Task]:
        """Get next task from queue."""
        
        if not self.task_queue:
            return None
        
        task_id = self.task_queue.pop(0)
        task = self.tasks[task_id]
        
        # Move to running tasks
        self.running_tasks[task_id] = task
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        self._save_queue()
        
        logger.info(f"Retrieved task {task_id} from queue")
        return task
    
    def complete_task(self, task_id: str, result: Any = None):
        """Mark task as completed."""
        
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.result = result
        
        # Move from running to completed
        if task_id in self.running_tasks:
            del self.running_tasks[task_id]
        
        self.completed_tasks[task_id] = task
        
        self._save_queue()
        
        logger.info(f"Completed task {task_id}")
    
    def fail_task(self, task_id: str, error: str = None):
        """Mark task as failed."""
        
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task = self.tasks[task_id]
        task.error = error
        task.retry_count += 1
        
        # Check if should retry
        if task.retry_count < task.max_retries:
            # Reset to pending and requeue
            task.status = TaskStatus.PENDING
            task.started_at = None
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self._add_to_priority_queue(task)
            
            logger.info(f"Retrying task {task_id} (attempt {task.retry_count})")
        else:
            # Mark as failed
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self.failed_tasks[task_id] = task
            
            logger.error(f"Task {task_id} failed permanently: {error}")
        
        self._save_queue()
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            return False
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        
        # Remove from all queues
        if task_id in self.task_queue:
            self.task_queue.remove(task_id)
        
        if task_id in self.running_tasks:
            del self.running_tasks[task_id]
        
        self._save_queue()
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        
        return self.tasks.get(task_id)
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Get tasks by status."""
        
        status_tasks = []
        
        if status == TaskStatus.PENDING:
            status_tasks = [self.tasks[tid] for tid in self.task_queue]
        elif status == TaskStatus.RUNNING:
            status_tasks = list(self.running_tasks.values())
        elif status == TaskStatus.COMPLETED:
            status_tasks = list(self.completed_tasks.values())
        elif status == TaskStatus.FAILED:
            status_tasks = list(self.failed_tasks.values())
        
        return status_tasks
    
    def get_tasks_by_type(self, task_type: str) -> List[Task]:
        """Get tasks by type."""
        
        return [task for task in self.tasks.values() if task.task_type == task_type]
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        
        stats = {
            'total_tasks': len(self.tasks),
            'pending_tasks': len(self.task_queue),
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'failed_tasks': len(self.failed_tasks),
            'queue_size': len(self.task_queue),
            'max_size': self.max_size,
            'utilization': len(self.tasks) / self.max_size * 100,
            'task_types': {},
            'priority_distribution': {}
        }
        
        # Task type distribution
        for task in self.tasks.values():
            task_type = task.task_type
            stats['task_types'][task_type] = stats['task_types'].get(task_type, 0) + 1
        
        # Priority distribution
        for task in self.tasks.values():
            priority = task.priority.name
            stats['priority_distribution'][priority] = stats['priority_distribution'].get(priority, 0) + 1
        
        return stats
    
    def cleanup_old_tasks(self, days: int = 7) -> int:
        """Clean up old completed and failed tasks."""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        cleaned_count = 0
        
        # Clean completed tasks
        completed_to_delete = []
        for task_id, task in self.completed_tasks.items():
            if task.completed_at and task.completed_at < cutoff_date:
                completed_to_delete.append(task_id)
        
        for task_id in completed_to_delete:
            del self.completed_tasks[task_id]
            del self.tasks[task_id]
            cleaned_count += 1
        
        # Clean failed tasks
        failed_to_delete = []
        for task_id, task in self.failed_tasks.items():
            if task.completed_at and task.completed_at < cutoff_date:
                failed_to_delete.append(task_id)
        
        for task_id in failed_to_delete:
            del self.failed_tasks[task_id]
            del self.tasks[task_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            self._save_queue()
            logger.info(f"Cleaned up {cleaned_count} old tasks")
        
        return cleaned_count
    
    def clear_queue(self) -> int:
        """Clear all tasks from queue."""
        
        total_cleared = len(self.tasks)
        
        self._initialize_empty_queue()
        self._save_queue()
        
        logger.info(f"Cleared {total_cleared} tasks from queue")
        return total_cleared
    
    def export_tasks(self, filepath: str) -> bool:
        """Export tasks to JSON file."""
        
        try:
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'stats': self.get_queue_stats(),
                'tasks': {}
            }
            
            # Export all tasks
            for task_id, task in self.tasks.items():
                task_dict = asdict(task)
                # Convert datetime objects to strings
                for key, value in task_dict.items():
                    if isinstance(value, datetime):
                        task_dict[key] = value.isoformat()
                    elif isinstance(value, (TaskStatus, TaskPriority)):
                        task_dict[key] = value.value
                
                export_data['tasks'][task_id] = task_dict
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported {len(self.tasks)} tasks to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting tasks: {e}")
            return False
    
    def import_tasks(self, filepath: str) -> int:
        """Import tasks from JSON file."""
        
        try:
            with open(filepath, 'r') as f:
                import_data = json.load(f)
            
            imported_count = 0
            
            for task_id, task_dict in import_data.get('tasks', {}).items():
                # Convert back to Task object
                task_dict['status'] = TaskStatus(task_dict['status'])
                task_dict['priority'] = TaskPriority(task_dict['priority'])
                
                # Convert datetime strings back to datetime objects
                for key, value in task_dict.items():
                    if key in ['created_at', 'started_at', 'completed_at'] and value:
                        task_dict[key] = datetime.fromisoformat(value)
                
                task = Task(**task_dict)
                self.tasks[task_id] = task
                
                # Add to appropriate queue
                if task.status == TaskStatus.PENDING:
                    self._add_to_priority_queue(task)
                elif task.status == TaskStatus.RUNNING:
                    self.running_tasks[task_id] = task
                elif task.status == TaskStatus.COMPLETED:
                    self.completed_tasks[task_id] = task
                elif task.status == TaskStatus.FAILED:
                    self.failed_tasks[task_id] = task
                
                imported_count += 1
            
            if imported_count > 0:
                self._save_queue()
                logger.info(f"Imported {imported_count} tasks from {filepath}")
            
            return imported_count
            
        except Exception as e:
            logger.error(f"Error importing tasks: {e}")
            return 0
    
    def get_pending_task_count(self) -> int:
        """Get count of pending tasks."""
        
        return len(self.task_queue)
    
    def get_running_task_count(self) -> int:
        """Get count of running tasks."""
        
        return len(self.running_tasks)
    
    def is_queue_full(self) -> bool:
        """Check if queue is full."""
        
        return len(self.tasks) >= self.max_size
    
    def add_scraping_task(self, 
                         scraper_name: str,
                         search_params: Dict[str, Any],
                         priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Add a scraping task to the queue."""
        
        return self.add_task(
            task_type="scraping",
            parameters={
                'scraper_name': scraper_name,
                'search_params': search_params
            },
            priority=priority,
            max_retries=3,
            timeout=600  # 10 minutes for scraping
        )
    
    def add_processing_task(self,
                           processing_type: str,
                           data: Dict[str, Any],
                           priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Add a processing task to the queue."""
        
        return self.add_task(
            task_type="processing",
            parameters={
                'processing_type': processing_type,
                'data': data
            },
            priority=priority,
            max_retries=2,
            timeout=300  # 5 minutes for processing
        )
    
    def add_storage_task(self,
                        storage_type: str,
                        data: Dict[str, Any],
                        priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Add a storage task to the queue."""
        
        return self.add_task(
            task_type="storage",
            parameters={
                'storage_type': storage_type,
                'data': data
            },
            priority=priority,
            max_retries=3,
            timeout=120  # 2 minutes for storage
        )
    
    def get_task_summary(self) -> Dict[str, Any]:
        """Get task summary for reporting."""
        
        summary = {
            'queue_stats': self.get_queue_stats(),
            'recent_completed': [],
            'recent_failed': [],
            'long_running': []
        }
        
        # Recent completed tasks (last 10)
        recent_completed = sorted(
            self.completed_tasks.values(),
            key=lambda t: t.completed_at or datetime.min,
            reverse=True
        )[:10]
        
        summary['recent_completed'] = [
            {
                'id': task.id,
                'type': task.task_type,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'duration': (task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else None
            }
            for task in recent_completed
        ]
        
        # Recent failed tasks (last 10)
        recent_failed = sorted(
            self.failed_tasks.values(),
            key=lambda t: t.completed_at or datetime.min,
            reverse=True
        )[:10]
        
        summary['recent_failed'] = [
            {
                'id': task.id,
                'type': task.task_type,
                'failed_at': task.completed_at.isoformat() if task.completed_at else None,
                'error': task.error,
                'retry_count': task.retry_count
            }
            for task in recent_failed
        ]
        
        # Long running tasks (running for more than 10 minutes)
        now = datetime.now()
        long_running_threshold = timedelta(minutes=10)
        
        for task in self.running_tasks.values():
            if task.started_at and (now - task.started_at) > long_running_threshold:
                summary['long_running'].append({
                    'id': task.id,
                    'type': task.task_type,
                    'started_at': task.started_at.isoformat(),
                    'duration': (now - task.started_at).total_seconds()
                })
        
        return summary
