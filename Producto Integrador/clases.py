"""Clases basicas del simulador"""

from enum import Enum
from collections import OrderedDict, deque

class ProcessState(Enum):
    """Estados del proceso"""
    NEW = "Nuevo"
    READY = "Listo"
    RUNNING = "En Ejecucion"
    BLOCKED = "Bloqueado"
    WAITING = "En Espera"
    TERMINATED = "Terminado"

class TerminationCause(Enum):
    """Causas de terminacion de un proceso"""
    COMPLETED = "Finalizo su ejecucion"
    FORCED = "Terminacion forzada por usuario"
    ERROR = "Error durante ejecucion"
    DEADLOCK = "Interbloqueo detectado"
    TIMEOUT = "Timeout excedido"

class Process:
    """Representa un proceso con gestion completa"""
    _counter = 0
    
    def __init__(self, size_kb, lifetime, priority=5, cpu_burst=None):
        Process._counter += 1
        self.pid = Process._counter
        self.size_kb = size_kb
        self.num_pages = 0
        self.state = ProcessState.NEW
        self.priority = priority
        
        # Gestion de memoria
        self.pages_in_ram = set()
        self.pages_in_swap = set()
        self.page_faults = 0
        self.last_access_time = {}
        
        # Gestion de CPU
        self.cpu_burst = cpu_burst or lifetime
        self.remaining_cpu = cpu_burst or lifetime
        self.arrival_time = 0
        self.start_time = None
        self.finish_time = None
        self.waiting_time = 0
        self.turnaround_time = 0
        
        # Ciclo de vida
        self.lifetime = lifetime
        self.remaining_lifetime = lifetime
        
        # Sincronizacion
        self.blocked_on = None
        self.waiting_for = None
        
        # Terminacion
        self.termination_cause = None
        
    def __str__(self):
        return f"P{self.pid}"
    
    def is_active(self):
        """Verifica si el proceso esta activo"""
        return self.state not in [ProcessState.TERMINATED, ProcessState.NEW]

class PageTableEntry:
    """Entrada de tabla de paginas"""
    def __init__(self, page_num):
        self.page_num = page_num
        self.frame = None
        self.swap_loc = None
        self.in_ram = False
        self.last_access = 0
        self.dirty = False

class PageTable:
    """Tabla de paginas de un proceso"""
    def __init__(self, pid, num_pages):
        self.pid = pid
        self.entries = {i: PageTableEntry(i) for i in range(num_pages)}
    
    def get(self, page_num):
        return self.entries.get(page_num)
    
    def translate(self, page_num):
        """Traduce pagina a marco. Retorna (marco, page_fault)"""
        entry = self.get(page_num)
        if not entry:
            return None, True
        if entry.in_ram:
            return entry.frame, False
        return None, True

class CPU:
    """Recurso CPU"""
    def __init__(self):
        self.current_process = None
        self.idle_time = 0
        self.busy_time = 0
        self.context_switches = 0
    
    def is_free(self):
        return self.current_process is None
    
    def assign(self, process):
        """Asigna CPU a un proceso"""
        if self.current_process:
            self.context_switches += 1
        self.current_process = process
        if process:
            process.state = ProcessState.RUNNING
            if process.start_time is None:
                process.start_time = 0
    
    def release(self):
        """Libera la CPU"""
        if self.current_process:
            self.current_process.state = ProcessState.READY
        self.current_process = None
    
    def execute_cycle(self):
        """Ejecuta un ciclo de CPU"""
        if self.current_process:
            self.busy_time += 1
            self.current_process.remaining_cpu -= 1
            return True
        else:
            self.idle_time += 1
            return False
    
    def get_utilization(self):
        total = self.busy_time + self.idle_time
        return (self.busy_time / total * 100) if total > 0 else 0

class Semaphore:
    """Semaforo para sincronizacion"""
    def __init__(self, name, initial_value=1):
        self.name = name
        self.value = initial_value
        self.waiting_queue = deque()
        self.history = []
    
    def wait(self, process):
        """Operacion Wait (P)"""
        self.value -= 1
        if self.value < 0:
            process.state = ProcessState.BLOCKED
            process.blocked_on = self.name
            self.waiting_queue.append(process)
            self.history.append(f"P{process.pid} bloqueado en {self.name}")
            return False
        self.history.append(f"P{process.pid} adquirio {self.name}")
        return True
    
    def signal(self, process=None):
        """Operacion Signal (V)"""
        self.value += 1
        if self.waiting_queue:
            blocked_process = self.waiting_queue.popleft()
            blocked_process.state = ProcessState.READY
            blocked_process.blocked_on = None
            self.history.append(f"P{blocked_process.pid} desbloqueado de {self.name}")
            return blocked_process
        if process:
            self.history.append(f"P{process.pid} libero {self.name}")
        return None

class SharedMemory:
    """Memoria compartida entre procesos"""
    def __init__(self, name, size=10):
        self.name = name
        self.buffer = []
        self.max_size = size
        self.readers = 0
        self.writers = 0
    
    def write(self, process, data):
        """Escribe en memoria compartida"""
        if len(self.buffer) < self.max_size:
            self.buffer.append((process.pid, data))
            return True
        return False
    
    def read(self, process):
        """Lee de memoria compartida"""
        if self.buffer:
            return self.buffer.pop(0)
        return None
    
    def is_full(self):
        return len(self.buffer) >= self.max_size
    
    def is_empty(self):
        return len(self.buffer) == 0

class SwapManager:
    """Gestor del area de intercambio"""
    def __init__(self, total_kb, page_kb):
        self.total_frames = total_kb // page_kb
        self.frames = [None] * self.total_frames
        self.used = 0
        self.swaps_in = 0
        self.swaps_out = 0
    
    def allocate(self, pid, page_num):
        """Asigna un frame en swap"""
        for i in range(self.total_frames):
            if self.frames[i] is None:
                self.frames[i] = (pid, page_num)
                self.used += 1
                self.swaps_in += 1
                return i
        return None
    
    def free(self, swap_idx):
        """Libera un frame del swap"""
        if 0 <= swap_idx < self.total_frames and self.frames[swap_idx]:
            self.frames[swap_idx] = None
            self.used -= 1
            self.swaps_out += 1
    
    def free_process(self, pid):
        """Libera todas las paginas de un proceso"""
        for i in range(self.total_frames):
            if self.frames[i] and self.frames[i][0] == pid:
                self.frames[i] = None
                self.used -= 1
    
    def get_utilization(self):
        return (self.used / self.total_frames * 100) if self.total_frames > 0 else 0
    
    def is_full(self):
        return self.used >= self.total_frames

class Statistics:
    """Estadisticas del sistema"""
    def __init__(self):
        # Procesos
        self.total_processes = 0
        self.completed_processes = 0
        self.rejected_processes = 0
        self.forced_terminations = 0
        
        # Memoria
        self.total_page_faults = 0
        self.memory_accesses = 0
        self.total_swaps = 0
        
        # CPU
        self.avg_waiting_time = 0
        self.avg_turnaround_time = 0
        self.avg_response_time = 0
        
        # Sincronizacion
        self.deadlocks_detected = 0
        self.total_blocks = 0
    
    def page_fault_rate(self):
        if self.memory_accesses == 0:
            return 0.0
        return (self.total_page_faults / self.memory_accesses) * 100
    
    def calculate_cpu_metrics(self, processes):
        """Calcula metricas de CPU"""
        finished = [p for p in processes if p.finish_time is not None]
        if not finished:
            return
        
        self.avg_waiting_time = sum(p.waiting_time for p in finished) / len(finished)
        self.avg_turnaround_time = sum(p.turnaround_time for p in finished) / len(finished)
