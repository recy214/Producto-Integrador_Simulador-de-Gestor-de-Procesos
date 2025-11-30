"""Implementacion de planificador FCFS - First Come, First Served"""

from collections import deque
from clases import ProcessState

class FCFSScheduler:
    """First Come, First Served (FCFS)"""
    
    def __init__(self):
        self.name = "FCFS"
        self.ready_queue = deque()
    
    def add_process(self, process):
        """Agrega proceso a la cola de listos"""
        if process.state == ProcessState.READY or process.state == ProcessState.NEW:
            process.state = ProcessState.READY
            self.ready_queue.append(process)
    
    def get_next_process(self):
        """Retorna el primer proceso en llegar (FIFO)"""
        if self.ready_queue:
            return self.ready_queue.popleft()
        return None
    
    def has_processes(self):
        """Verifica si hay procesos en la cola"""
        return len(self.ready_queue) > 0
    
    def should_preempt(self, current_process):
        """FCFS"""
        return False
    
    def remove_process(self, process):
        """Elimina un proceso de la cola"""
        if process in self.ready_queue:
            self.ready_queue.remove(process)
