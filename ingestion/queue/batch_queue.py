"""
Batch queue for managing batch processing tasks.
"""
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable
import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from .task_queue import Task, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)


class BatchStatus(Enum):
    """Batch status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


@dataclass
class BatchTask:
    """Batch task data class."""
    id: str
    name: str
    tasks: List[Task]
    batch_size: int
    max_concurrent: int
    status: BatchStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    completed_tasks: int = 0
    failed_tasks: int = 0
    timeout: int = 1800  # 30 minutes default


class BatchQueue:
    """Batch queue for managing batch processing tasks."""
    
    def __init__(self, max_concurrent_batches: int = 5, max_batch_size: int = 100):
        """Initialize batch queue."""
        self.max_concurrent_batches = max_concurrent_batches
        self.max_batch_size = max_batch_size
        
        self.batches = {}
        self.pending_batches = []
        self.running_batches = {}
        self.completed_batches = {}
        self.failed_batches = {}
        
        self.executor = None
        self.running = False
        
        logger.info(f"Batch queue initialized: max_concurrent={max_concurrent_batches}, max_batch_size={max_batch_size}")
    
    def create_batch(self, 
                    name: str,
                    tasks: List[Task],
                    batch_size: int = None,
                    max_concurrent: int = None,
                    timeout: int = 1800) -> str:
        """Create a batch of tasks."""
        
        if len(tasks) == 0:
            logger.warning("Cannot create batch with no tasks")
            return ""
        
        if batch_size is None:
            batch_size = min(len(tasks), self.max_batch_size)
        
        if max_concurrent is None:
            max_concurrent = min(5, len(tasks))
        
        batch_id = str(uuid.uuid4())
        
        batch = BatchTask(
            id=batch_id,
            name=name,
            tasks=tasks,
            batch_size=batch_size,
            max_concurrent=max_concurrent,
            status=BatchStatus.PENDING,
            created_at=datetime.now(),
            timeout=timeout
        )
        
        self.batches[batch_id] = batch
        self.pending_batches.append(batch_id)
        
        logger.info(f"Created batch {batch_id} with {len(tasks)} tasks")
        return batch_id
    
    def create_batch_from_parameters(self,
                                   name: str,
                                   task_type: str,
                                   parameters_list: List[Dict[str, Any]],
                                   priority: TaskPriority = TaskPriority.NORMAL,
                                   batch_size: int = None,
                                   max_concurrent: int = None) -> str:
        """Create a batch from list of parameters."""
        
        tasks = []
        
        for i, params in enumerate(parameters_list):
            task_id = f"{name}_task_{i}"
            
            task = Task(
                id=task_id,
                task_type=task_type,
                parameters=params,
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=datetime.now()
            )
            
            tasks.append(task)
        
        return self.create_batch(
            name=name,
            tasks=tasks,
            batch_size=batch_size,
            max_concurrent=max_concurrent
        )
    
    def start_processing(self, task_handler: Callable):
        """Start batch processing with task handler."""
        
        if self.running:
            logger.warning("Batch processing is already running")
            return
        
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_batches)
        
        # Process batches asynchronously
        asyncio.create_task(self._process_batches(task_handler))
        
        logger.info("Started batch processing")
    
    async def _process_batches(self, task_handler: Callable):
        """Process batches asynchronously."""
        
        while self.running:
            try:
                # Get next batch to process
                batch_id = self._get_next_batch()
                
                if batch_id:
                    batch = self.batches[batch_id]
                    
                    # Move to running
                    self.pending_batches.remove(batch_id)
                    self.running_batches[batch_id] = batch
                    batch.status = BatchStatus.RUNNING
                    batch.started_at = datetime.now()
                    
                    # Process batch in background
                    self.executor.submit(self._process_single_batch, batch_id, task_handler)
                else:
                    # No batches to process, wait a bit
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in batch processing loop: {e}")
                await asyncio.sleep(5)
    
    def _get_next_batch(self) -> Optional[str]:
        """Get next batch to process."""
        
        if not self.pending_batches:
            return None
        
        if len(self.running_batches) >= self.max_concurrent_batches:
            return None
        
        # Get highest priority batch
        return self.pending_batches[0]
    
    def _process_single_batch(self, batch_id: str, task_handler: Callable):
        """Process a single batch."""
        
        batch = self.batches[batch_id]
        
        try:
            logger.info(f"Processing batch {batch_id}: {batch.name}")
            
            # Process tasks in batches
            for i in range(0, len(batch.tasks), batch.batch_size):
                if not self.running:
                    break
                
                task_batch = batch.tasks[i:i + batch.batch_size]
                
                # Process tasks concurrently
                futures = []
                
                for task in task_batch:
                    if task.status == TaskStatus.PENDING:
                        future = self.executor.submit(self._process_task, task, task_handler)
                        futures.append((task.id, future))
                
                # Wait for completion
                for task_id, future in futures:
                    try:
                        result = future.result(timeout=task.timeout)
                        
                        if result['success']:
                            batch.results.append(result['data'])
                            batch.completed_tasks += 1
                        else:
                            batch.errors.append(f"Task {task_id}: {result['error']}")
                            batch.failed_tasks += 1
                            
                    except Exception as e:
                        batch.errors.append(f"Task {task_id}: {str(e)}")
                        batch.failed_tasks += 1
                
                # Check if batch should be cancelled
                if batch.status == BatchStatus.CANCELLED:
                    break
            
            # Update batch status
            batch.completed_at = datetime.now()
            
            if batch.status == BatchStatus.CANCELLED:
                batch.status = BatchStatus.CANCELLED
                self.failed_batches[batch_id] = batch
            elif batch.failed_tasks == 0:
                batch.status = BatchStatus.COMPLETED
                self.completed_batches[batch_id] = batch
            elif batch.completed_tasks > 0:
                batch.status = BatchStatus.PARTIALLY_COMPLETED
                self.completed_batches[batch_id] = batch
            else:
                batch.status = BatchStatus.FAILED
                self.failed_batches[batch_id] = batch
            
            # Remove from running
            if batch_id in self.running_batches:
                del self.running_batches[batch_id]
            
            logger.info(f"Completed batch {batch_id}: {batch.completed_tasks} completed, {batch.failed_tasks} failed")
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {e}")
            
            batch.status = BatchStatus.FAILED
            batch.completed_at = datetime.now()
            batch.errors.append(str(e))
            
            if batch_id in self.running_batches:
                del self.running_batches[batch_id]
            
            self.failed_batches[batch_id] = batch
    
    def _process_task(self, task: Task, task_handler: Callable) -> Dict[str, Any]:
        """Process a single task."""
        
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            # Call task handler
            result = task_handler(task)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            return {
                'success': True,
                'data': result,
                'task_id': task.id
            }
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            
            return {
                'success': False,
                'error': str(e),
                'task_id': task.id
            }
    
    def stop_processing(self):
        """Stop batch processing."""
        
        self.running = False
        
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
        
        logger.info("Stopped batch processing")
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch."""
        
        if batch_id not in self.batches:
            return False
        
        batch = self.batches[batch_id]
        
        if batch.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]:
            return False
        
        batch.status = BatchStatus.CANCELLED
        batch.completed_at = datetime.now()
        
        # Remove from pending
        if batch_id in self.pending_batches:
            self.pending_batches.remove(batch_id)
        
        # Cancel individual tasks
        for task in batch.tasks:
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
        
        logger.info(f"Cancelled batch {batch_id}")
        return True
    
    def get_batch(self, batch_id: str) -> Optional[BatchTask]:
        """Get batch by ID."""
        
        return self.batches.get(batch_id)
    
    def get_batches_by_status(self, status: BatchStatus) -> List[BatchTask]:
        """Get batches by status."""
        
        if status == BatchStatus.PENDING:
            return [self.batches[bid] for bid in self.pending_batches]
        elif status == BatchStatus.RUNNING:
            return list(self.running_batches.values())
        elif status == BatchStatus.COMPLETED:
            return list(self.completed_batches.values())
        elif status == BatchStatus.FAILED:
            return list(self.failed_batches.values())
        else:
            return []
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch statistics."""
        
        stats = {
            'total_batches': len(self.batches),
            'pending_batches': len(self.pending_batches),
            'running_batches': len(self.running_batches),
            'completed_batches': len(self.completed_batches),
            'failed_batches': len(self.failed_batches),
            'total_tasks': sum(len(batch.tasks) for batch in self.batches.values()),
            'completed_tasks': sum(batch.completed_tasks for batch in self.batches.values()),
            'failed_tasks': sum(batch.failed_tasks for batch in self.batches.values()),
            'success_rate': 0.0,
            'is_running': self.running
        }
        
        # Calculate success rate
        total_processed = stats['completed_tasks'] + stats['failed_tasks']
        if total_processed > 0:
            stats['success_rate'] = (stats['completed_tasks'] / total_processed) * 100
        
        return stats
    
    def cleanup_old_batches(self, days: int = 7) -> int:
        """Clean up old completed and failed batches."""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        cleaned_count = 0
        
        # Clean completed batches
        completed_to_delete = []
        for batch_id, batch in self.completed_batches.items():
            if batch.completed_at and batch.completed_at < cutoff_date:
                completed_to_delete.append(batch_id)
        
        for batch_id in completed_to_delete:
            del self.completed_batches[batch_id]
            del self.batches[batch_id]
            cleaned_count += 1
        
        # Clean failed batches
        failed_to_delete = []
        for batch_id, batch in self.failed_batches.items():
            if batch.completed_at and batch.completed_at < cutoff_date:
                failed_to_delete.append(batch_id)
        
        for batch_id in failed_to_delete:
            del self.failed_batches[batch_id]
            del self.batches[batch_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old batches")
        
        return cleaned_count
    
    def get_batch_summary(self, batch_id: str) -> Dict[str, Any]:
        """Get detailed summary of a batch."""
        
        batch = self.get_batch(batch_id)
        
        if not batch:
            return {}
        
        summary = {
            'id': batch.id,
            'name': batch.name,
            'status': batch.status.name,
            'created_at': batch.created_at.isoformat(),
            'started_at': batch.started_at.isoformat() if batch.started_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
            'total_tasks': len(batch.tasks),
            'completed_tasks': batch.completed_tasks,
            'failed_tasks': batch.failed_tasks,
            'batch_size': batch.batch_size,
            'max_concurrent': batch.max_concurrent,
            'success_rate': 0.0,
            'duration': None,
            'task_types': {},
            'errors': batch.errors[:10]  # First 10 errors
        }
        
        # Calculate success rate
        total_processed = batch.completed_tasks + batch.failed_tasks
        if total_processed > 0:
            summary['success_rate'] = (batch.completed_tasks / total_processed) * 100
        
        # Calculate duration
        if batch.started_at and batch.completed_at:
            duration = batch.completed_at - batch.started_at
            summary['duration'] = duration.total_seconds()
        
        # Task type distribution
        for task in batch.tasks:
            task_type = task.task_type
            summary['task_types'][task_type] = summary['task_types'].get(task_type, 0) + 1
        
        return summary
    
    def create_scraping_batch(self, 
                             scraper_name: str,
                             search_params_list: List[Dict[str, Any]],
                             priority: TaskPriority = TaskPriority.NORMAL,
                             batch_size: int = 10) -> str:
        """Create a scraping batch."""
        
        return self.create_batch_from_parameters(
            name=f"scraping_{scraper_name}",
            task_type="scraping",
            parameters_list=[
                {'scraper_name': scraper_name, 'search_params': params}
                for params in search_params_list
            ],
            priority=priority,
            batch_size=batch_size
        )
    
    def create_processing_batch(self,
                               processing_type: str,
                               data_list: List[Dict[str, Any]],
                               priority: TaskPriority = TaskPriority.NORMAL,
                               batch_size: int = 50) -> str:
        """Create a processing batch."""
        
        return self.create_batch_from_parameters(
            name=f"processing_{processing_type}",
            task_type="processing",
            parameters_list=[
                {'processing_type': processing_type, 'data': data}
                for data in data_list
            ],
            priority=priority,
            batch_size=batch_size
        )
    
    def create_storage_batch(self,
                           storage_type: str,
                           data_list: List[Dict[str, Any]],
                           priority: TaskPriority = TaskPriority.NORMAL,
                           batch_size: int = 100) -> str:
        """Create a storage batch."""
        
        return self.create_batch_from_parameters(
            name=f"storage_{storage_type}",
            task_type="storage",
            parameters_list=[
                {'storage_type': storage_type, 'data': data}
                for data in data_list
            ],
            priority=priority,
            batch_size=batch_size
        )
    
    def get_queue_health(self) -> Dict[str, Any]:
        """Get queue health metrics."""
        
        health = {
            'status': 'healthy',
            'issues': [],
            'metrics': self.get_batch_stats()
        }
        
        # Check for issues
        if not self.running:
            health['issues'].append('Batch processing is not running')
        
        if len(self.pending_batches) > 50:
            health['issues'].append('High number of pending batches')
            health['status'] = 'warning'
        
        # Check for failed batches
        failed_batches = len(self.failed_batches)
        total_batches = len(self.batches)
        
        if total_batches > 0 and (failed_batches / total_batches) > 0.2:
            health['issues'].append('High failure rate (>20%)')
            health['status'] = 'warning'
        
        # Check for long-running batches
        for batch in self.running_batches.values():
            if batch.started_at:
                duration = datetime.now() - batch.started_at
                if duration.total_seconds() > 3600:  # 1 hour
                    health['issues'].append(f'Long-running batch: {batch.id}')
                    health['status'] = 'warning'
                    break
        
        return health
    
    def export_batches(self, filepath: str) -> bool:
        """Export batches to JSON file."""
        
        try:
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'stats': self.get_batch_stats(),
                'batches': {}
            }
            
            # Export all batches
            for batch_id, batch in self.batches.items():
                batch_data = {
                    'id': batch.id,
                    'name': batch.name,
                    'status': batch.status.name,
                    'created_at': batch.created_at.isoformat(),
                    'started_at': batch.started_at.isoformat() if batch.started_at else None,
                    'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
                    'batch_size': batch.batch_size,
                    'max_concurrent': batch.max_concurrent,
                    'completed_tasks': batch.completed_tasks,
                    'failed_tasks': batch.failed_tasks,
                    'timeout': batch.timeout,
                    'errors': batch.errors
                }
                
                # Export task summaries
                batch_data['task_summaries'] = []
                for task in batch.tasks:
                    task_summary = {
                        'id': task.id,
                        'type': task.task_type,
                        'status': task.status.name,
                        'created_at': task.created_at.isoformat(),
                        'priority': task.priority.name
                    }
                    
                    if task.started_at:
                        task_summary['started_at'] = task.started_at.isoformat()
                    
                    if task.completed_at:
                        task_summary['completed_at'] = task.completed_at.isoformat()
                    
                    if task.error:
                        task_summary['error'] = task.error
                    
                    batch_data['task_summaries'].append(task_summary)
                
                export_data['batches'][batch_id] = batch_data
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported {len(self.batches)} batches to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting batches: {e}")
            return False
