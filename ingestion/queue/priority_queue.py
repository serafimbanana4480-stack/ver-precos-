"""
Priority queue for managing prioritized tasks.
"""
import heapq
import uuid
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from .task_queue import Task, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)


@dataclass(order=True)
class PriorityTask:
    """Priority task for heap queue."""
    priority: int = field(compare=False)
    created_at: datetime = field(compare=False)
    task_id: str = field(compare=False)
    task: Task = field(compare=False)


class PriorityQueue:
    """Priority queue for managing prioritized tasks."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize priority queue."""
        self.max_size = max_size
        self.heap = []
        self.tasks = {}
        self.task_index = {}  # Map task_id to heap index
        
        logger.info(f"Priority queue initialized with max size: {max_size}")
    
    def add_task(self, task: Task) -> bool:
        """Add task to priority queue."""
        
        if len(self.tasks) >= self.max_size:
            logger.warning("Priority queue is full, cannot add new task")
            return False
        
        if task.id in self.tasks:
            logger.warning(f"Task {task.id} already exists in queue")
            return False
        
        # Create priority task
        priority_task = PriorityTask(
            priority=task.priority.value,
            created_at=task.created_at,
            task_id=task.id,
            task=task
        )
        
        # Add to heap
        heapq.heappush(self.heap, priority_task)
        
        # Track task
        self.tasks[task.id] = priority_task
        
        logger.info(f"Added task {task.id} with priority {task.priority.name}")
        return True
    
    def get_next_task(self) -> Optional[Task]:
        """Get next highest priority task."""
        
        if not self.heap:
            return None
        
        priority_task = heapq.heappop(self.heap)
        task = priority_task.task
        
        # Remove from tracking
        del self.tasks[task.id]
        
        logger.info(f"Retrieved task {task.id} with priority {task.priority.name}")
        return task
    
    def peek_next_task(self) -> Optional[Task]:
        """Peek at next highest priority task without removing it."""
        
        if not self.heap:
            return None
        
        priority_task = self.heap[0]
        return priority_task.task
    
    def remove_task(self, task_id: str) -> bool:
        """Remove specific task from queue."""
        
        if task_id not in self.tasks:
            return False
        
        priority_task = self.tasks[task_id]
        
        try:
            # Remove from heap (this is O(n) operation)
            self.heap.remove(priority_task)
            heapq.heapify(self.heap)
            
            del self.tasks[task_id]
            
            logger.info(f"Removed task {task_id} from priority queue")
            return True
            
        except ValueError:
            logger.error(f"Task {task_id} not found in heap")
            return False
    
    def update_task_priority(self, task_id: str, new_priority: TaskPriority) -> bool:
        """Update task priority."""
        
        if task_id not in self.tasks:
            return False
        
        # Remove old task
        priority_task = self.tasks[task_id]
        
        try:
            self.heap.remove(priority_task)
            heapq.heapify(self.heap)
        except ValueError:
            logger.error(f"Task {task_id} not found in heap")
            return False
        
        # Update priority
        priority_task.task.priority = new_priority
        priority_task.priority = new_priority.value
        
        # Re-add to heap
        heapq.heappush(self.heap, priority_task)
        
        logger.info(f"Updated task {task_id} priority to {new_priority.name}")
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        
        priority_task = self.tasks.get(task_id)
        return priority_task.task if priority_task else None
    
    def get_tasks_by_priority(self, priority: TaskPriority) -> List[Task]:
        """Get all tasks with specific priority."""
        
        return [
            pt.task for pt in self.heap 
            if pt.task.priority == priority
        ]
    
    def get_tasks_by_type(self, task_type: str) -> List[Task]:
        """Get all tasks of specific type."""
        
        return [
            pt.task for pt in self.heap 
            if pt.task.task_type == task_type
        ]
    
    def size(self) -> int:
        """Get queue size."""
        
        return len(self.heap)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        
        return len(self.heap) == 0
    
    def is_full(self) -> bool:
        """Check if queue is full."""
        
        return len(self.heap) >= self.max_size
    
    def clear(self) -> int:
        """Clear all tasks from queue."""
        
        cleared_count = len(self.heap)
        
        self.heap.clear()
        self.tasks.clear()
        
        logger.info(f"Cleared {cleared_count} tasks from priority queue")
        return cleared_count
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        
        stats = {
            'total_tasks': len(self.heap),
            'max_size': self.max_size,
            'utilization': len(self.heap) / self.max_size * 100,
            'priority_distribution': {},
            'task_type_distribution': {},
            'oldest_task': None,
            'newest_task': None
        }
        
        if not self.heap:
            return stats
        
        # Priority distribution
        for pt in self.heap:
            priority_name = pt.task.priority.name
            stats['priority_distribution'][priority_name] = stats['priority_distribution'].get(priority_name, 0) + 1
        
        # Task type distribution
        for pt in self.heap:
            task_type = pt.task.task_type
            stats['task_type_distribution'][task_type] = stats['task_type_distribution'].get(task_type, 0) + 1
        
        # Oldest and newest tasks
        sorted_tasks = sorted(self.heap, key=lambda pt: pt.created_at)
        
        if sorted_tasks:
            stats['oldest_task'] = {
                'id': sorted_tasks[0].task_id,
                'type': sorted_tasks[0].task.task_type,
                'priority': sorted_tasks[0].task.priority.name,
                'created_at': sorted_tasks[0].created_at.isoformat()
            }
            
            stats['newest_task'] = {
                'id': sorted_tasks[-1].task_id,
                'type': sorted_tasks[-1].task.task_type,
                'priority': sorted_tasks[-1].task.priority.name,
                'created_at': sorted_tasks[-1].created_at.isoformat()
            }
        
        return stats
    
    def get_tasks_by_age(self, max_age_hours: int = 24) -> List[Task]:
        """Get tasks older than specified age."""
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        return [
            pt.task for pt in self.heap 
            if pt.created_at < cutoff_time
        ]
    
    def get_tasks_by_age_range(self, min_age_hours: int = 0, max_age_hours: int = 24) -> List[Task]:
        """Get tasks within age range."""
        
        min_time = datetime.now() - timedelta(hours=min_age_hours)
        max_time = datetime.now() - timedelta(hours=max_age_hours)
        
        return [
            pt.task for pt in self.heap 
            if max_time <= pt.created_at <= min_time
        ]
    
    def remove_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove tasks older than specified age."""
        
        old_tasks = self.get_tasks_by_age(max_age_hours)
        removed_count = 0
        
        for task in old_tasks:
            if self.remove_task(task.id):
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old tasks from priority queue")
        
        return removed_count
    
    def promote_urgent_tasks(self) -> int:
        """Promote high priority tasks to urgent."""
        
        promoted_count = 0
        
        for pt in self.heap:
            if pt.task.priority == TaskPriority.HIGH:
                if self.update_task_priority(pt.task_id, TaskPriority.URGENT):
                    promoted_count += 1
        
        if promoted_count > 0:
            logger.info(f"Promoted {promoted_count} tasks to urgent priority")
        
        return promoted_count
    
    def demote_old_tasks(self, max_age_hours: int = 12) -> int:
        """Demote old tasks to lower priority."""
        
        old_tasks = self.get_tasks_by_age(max_age_hours)
        demoted_count = 0
        
        for task in old_tasks:
            if task.priority in [TaskPriority.URGENT, TaskPriority.HIGH]:
                new_priority = TaskPriority.NORMAL if task.priority == TaskPriority.URGENT else TaskPriority.LOW
                if self.update_task_priority(task.id, new_priority):
                    demoted_count += 1
        
        if demoted_count > 0:
            logger.info(f"Demoted {demoted_count} old tasks to lower priority")
        
        return demoted_count
    
    def get_priority_summary(self) -> Dict[str, Any]:
        """Get priority summary for reporting."""
        
        summary = {
            'total_tasks': len(self.heap),
            'priority_breakdown': {},
            'age_breakdown': {
                '0-1h': 0,
                '1-6h': 0,
                '6-24h': 0,
                '24h+': 0
            },
            'top_5_tasks': []
        }
        
        if not self.heap:
            return summary
        
        # Priority breakdown
        for pt in self.heap:
            priority_name = pt.task.priority.name
            summary['priority_breakdown'][priority_name] = summary['priority_breakdown'].get(priority_name, 0) + 1
        
        # Age breakdown
        now = datetime.now()
        for pt in self.heap:
            age_hours = (now - pt.created_at).total_seconds() / 3600
            
            if age_hours <= 1:
                summary['age_breakdown']['0-1h'] += 1
            elif age_hours <= 6:
                summary['age_breakdown']['1-6h'] += 1
            elif age_hours <= 24:
                summary['age_breakdown']['6-24h'] += 1
            else:
                summary['age_breakdown']['24h+'] += 1
        
        # Top 5 tasks (highest priority)
        top_tasks = sorted(self.heap, key=lambda pt: (pt.priority, pt.created_at))[:5]
        
        for i, pt in enumerate(top_tasks):
            summary['top_5_tasks'].append({
                'rank': i + 1,
                'id': pt.task_id,
                'type': pt.task.task_type,
                'priority': pt.task.priority.name,
                'created_at': pt.created_at.isoformat(),
                'age_hours': (now - pt.created_at).total_seconds() / 3600
            })
        
        return summary
    
    def rebalance_queue(self) -> int:
        """Rebalance queue based on age and priority."""
        
        rebalanced_count = 0
        
        # Promote old high-priority tasks to urgent
        old_high_tasks = self.get_tasks_by_age_range(6, 24)
        
        for task in old_high_tasks:
            if task.priority == TaskPriority.HIGH:
                if self.update_task_priority(task.id, TaskPriority.URGENT):
                    rebalanced_count += 1
        
        # Demote very old normal tasks to low priority
        very_old_tasks = self.get_tasks_by_age(48)
        
        for task in very_old_tasks:
            if task.priority == TaskPriority.NORMAL:
                if self.update_task_priority(task.id, TaskPriority.LOW):
                    rebalanced_count += 1
        
        if rebalanced_count > 0:
            logger.info(f"Rebalanced {rebalanced_count} tasks in priority queue")
        
        return rebalanced_count
    
    def export_queue_state(self) -> Dict[str, Any]:
        """Export current queue state for backup/analysis."""
        
        state = {
            'export_timestamp': datetime.now().isoformat(),
            'max_size': self.max_size,
            'stats': self.get_queue_stats(),
            'tasks': []
        }
        
        # Export all tasks
        for pt in self.heap:
            task_data = {
                'id': pt.task_id,
                'type': pt.task.task_type,
                'priority': pt.task.priority.name,
                'status': pt.task.status.name,
                'created_at': pt.created_at.isoformat(),
                'parameters': pt.task.parameters,
                'retry_count': pt.task.retry_count,
                'max_retries': pt.task.max_retries,
                'timeout': pt.task.timeout
            }
            
            if pt.task.started_at:
                task_data['started_at'] = pt.task.started_at.isoformat()
            
            if pt.task.completed_at:
                task_data['completed_at'] = pt.task.completed_at.isoformat()
            
            if pt.task.error:
                task_data['error'] = pt.task.error
            
            state['tasks'].append(task_data)
        
        return state
    
    def import_queue_state(self, state: Dict[str, Any]) -> int:
        """Import queue state from backup."""
        
        imported_count = 0
        
        try:
            # Clear current queue
            self.clear()
            
            # Import tasks
            for task_data in state.get('tasks', []):
                # Reconstruct task
                task = Task(
                    id=task_data['id'],
                    task_type=task_data['type'],
                    parameters=task_data['parameters'],
                    priority=TaskPriority[task_data['priority']],
                    status=TaskStatus[task_data['status']],
                    created_at=datetime.fromisoformat(task_data['created_at']),
                    retry_count=task_data.get('retry_count', 0),
                    max_retries=task_data.get('max_retries', 3),
                    timeout=task_data.get('timeout', 300)
                )
                
                if 'started_at' in task_data:
                    task.started_at = datetime.fromisoformat(task_data['started_at'])
                
                if 'completed_at' in task_data:
                    task.completed_at = datetime.fromisoformat(task_data['completed_at'])
                
                if 'error' in task_data:
                    task.error = task_data['error']
                
                # Add to queue (only pending tasks)
                if task.status == TaskStatus.PENDING:
                    self.add_task(task)
                    imported_count += 1
            
            logger.info(f"Imported {imported_count} tasks to priority queue")
            return imported_count
            
        except Exception as e:
            logger.error(f"Error importing queue state: {e}")
            return 0
    
    def get_queue_health(self) -> Dict[str, Any]:
        """Get queue health metrics."""
        
        health = {
            'status': 'healthy',
            'issues': [],
            'metrics': self.get_queue_stats()
        }
        
        # Check for issues
        if len(self.heap) == 0:
            health['issues'].append('Queue is empty')
        
        if len(self.heap) >= self.max_size * 0.9:
            health['issues'].append('Queue is nearly full')
            health['status'] = 'warning'
        
        # Check for very old tasks
        old_tasks = self.get_tasks_by_age(48)
        if len(old_tasks) > len(self.heap) * 0.3:
            health['issues'].append('High number of old tasks (>48 hours)')
            health['status'] = 'warning'
        
        # Check for too many urgent tasks
        urgent_tasks = self.get_tasks_by_priority(TaskPriority.URGENT)
        if len(urgent_tasks) > len(self.heap) * 0.5:
            health['issues'].append('High number of urgent tasks')
            health['status'] = 'warning'
        
        return health
