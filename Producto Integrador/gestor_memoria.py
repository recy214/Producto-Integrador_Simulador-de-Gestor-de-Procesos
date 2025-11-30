"""Gestor completo de procesos - CPU con FCFS, Memoria, Sincronizacion"""

import configparser
import logging
import os
from clases import *
from planificador_fcfs import FCFSScheduler

class ProcessManager:
    """Gestor completo de procesos con CPU, memoria y sincronizacion"""
    
    def __init__(self, config_file='config.ini'):
        # Cargar configuracion
        config = configparser.ConfigParser()
        config.read(config_file)
        
        # Memoria
        self.ram_kb = config.getint('MEMORY', 'ram_size')
        self.swap_kb = config.getint('MEMORY', 'swap_size')
        self.page_kb = config.getint('MEMORY', 'page_size')
        self.total_frames = self.ram_kb // self.page_kb
        
        self.ram = [None] * self.total_frames
        self.frame_map = [None] * self.total_frames
        self.swap = SwapManager(self.swap_kb, self.page_kb)
        
        # CPU con planificador FCFS
        self.cpu = CPU()
        self.scheduler = FCFSScheduler()
        
        # Procesos
        self.all_processes = []
        self.active_processes = []
        self.blocked_processes = []
        self.waiting_queue = []
        self.page_tables = {}
        
        # Sincronizacion
        self.semaphores = {}
        self.shared_memory = {}
        
        # Control
        self.current_time = 0
        self.stats = Statistics()
        
        # Logger
        self.logger = None
        if config.getboolean('LOGS', 'enable_logs'):
            self._setup_logger(config.get('LOGS', 'log_file'))
    
    def _setup_logger(self, log_file):
        """Configura el sistema de logs"""
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        self.logger = logging.getLogger('ProcessSim')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_file, mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
        self.logger.addHandler(handler)
        self.logger.info("="*70)
        self.logger.info("SIMULADOR INICIADO - Planificador FCFS")
        self.logger.info("="*70)
    
    def log(self, msg):
        """Log helper"""
        if self.logger:
            self.logger.info(msg)
    
    # ==================== GESTION DE PROCESOS ====================
    
    def create_process(self, size_kb, lifetime, priority=5, cpu_burst=None):
        """Crea un nuevo proceso"""
        process = Process(size_kb, lifetime, priority, cpu_burst)
        process.arrival_time = self.current_time
        self.all_processes.append(process)
        self.stats.total_processes += 1
        return process
    
    def allocate_process(self, process):
        """Intenta asignar un proceso a memoria"""
        process.num_pages = (process.size_kb + self.page_kb - 1) // self.page_kb
        
        if process.size_kb > (self.ram_kb + self.swap_kb):
            self.log(f"RECHAZADO: P{process.pid} ({process.size_kb}KB) excede capacidad")
            self.stats.rejected_processes += 1
            process.state = ProcessState.TERMINATED
            process.termination_cause = TerminationCause.ERROR
            return False
        
        self.page_tables[process.pid] = PageTable(process.pid, process.num_pages)
        
        free_frames = sum(1 for f in self.ram if f is None)
        
        if free_frames >= process.num_pages:
            self._assign_to_ram(process)
            process.state = ProcessState.READY
            self.active_processes.append(process)
            self.scheduler.add_process(process)
            self.log(f"ASIGNADO: P{process.pid} ({process.size_kb}KB, {process.num_pages} pags)")
            return True
        else:
            return self._allocate_with_swap(process)
    
    def suspend_process(self, process):
        """Suspende un proceso (bloquearlo manualmente)"""
        if process.state == ProcessState.RUNNING:
            self.cpu.release()
        
        process.state = ProcessState.BLOCKED
        process.blocked_on = "Suspendido manualmente"
        
        if process in self.active_processes:
            self.active_processes.remove(process)
        self.blocked_processes.append(process)
        
        self.scheduler.remove_process(process)
        
        self.log(f"SUSPENDIDO: P{process.pid}")
        print(f"P{process.pid} suspendido")
    
    def resume_process(self, process):
        """Reanuda un proceso suspendido"""
        if process.state == ProcessState.BLOCKED:
            process.state = ProcessState.READY
            process.blocked_on = None
            
            if process in self.blocked_processes:
                self.blocked_processes.remove(process)
            self.active_processes.append(process)
            
            self.scheduler.add_process(process)
            
            self.log(f"REANUDADO: P{process.pid}")
            print(f"P{process.pid} reanudado")
    
    def force_terminate_process(self, process, cause=TerminationCause.FORCED):
        """Termina un proceso forzadamente"""
        if process.state == ProcessState.RUNNING:
            self.cpu.release()
        
        process.state = ProcessState.TERMINATED
        process.termination_cause = cause
        process.finish_time = self.current_time
        
        if process.start_time:
            process.turnaround_time = process.finish_time - process.arrival_time
            process.waiting_time = process.turnaround_time - (process.cpu_burst - process.remaining_cpu)
        
        self._free_process_memory(process)
        
        if process in self.active_processes:
            self.active_processes.remove(process)
        if process in self.blocked_processes:
            self.blocked_processes.remove(process)
        self.scheduler.remove_process(process)
        
        self.stats.forced_terminations += 1
        self.log(f"TERMINADO FORZADAMENTE: P{process.pid} - {cause.value}")
        print(f"P{process.pid} terminado: {cause.value}")
    
    def terminate_process(self, process):
        """Termina un proceso normalmente"""
        if process.remaining_cpu <= 0:
            cause = TerminationCause.COMPLETED
        elif process.remaining_lifetime <= 0:
            cause = TerminationCause.TIMEOUT
        else:
            cause = TerminationCause.ERROR
        
        self.force_terminate_process(process, cause)
        self.stats.completed_processes += 1
    
    # ==================== GESTION DE CPU ====================
    
    def schedule_cpu(self):
        """Ejecuta ciclo de planificacion de CPU con FCFS"""
        # Si CPU libre, asignar nuevo proceso
        if self.cpu.is_free() and self.scheduler.has_processes():
            next_process = self.scheduler.get_next_process()
            if next_process:
                self.cpu.assign(next_process)
                if next_process.start_time is None:
                    next_process.start_time = self.current_time
                self.log(f"CPU ASIGNADA: P{next_process.pid}")
        
        # Ejecutar ciclo de CPU
        if self.cpu.execute_cycle():
            current = self.cpu.current_process
            
            # Verificar si el proceso termino su burst
            if current.remaining_cpu <= 0:
                self.log(f"CPU COMPLETADO: P{current.pid}")
                self.cpu.release()
                self.terminate_process(current)
    
    # ==================== GESTION DE MEMORIA ====================
    
    def _assign_to_ram(self, process):
        """Asigna todas las paginas de un proceso a RAM"""
        page_table = self.page_tables[process.pid]
        
        for page_num in range(process.num_pages):
            frame = self._get_free_frame()
            if frame is not None:
                self.ram[frame] = process.pid
                self.frame_map[frame] = (process.pid, page_num)
                
                entry = page_table.get(page_num)
                entry.frame = frame
                entry.in_ram = True
                entry.last_access = self.current_time
                
                process.pages_in_ram.add(page_num)
                process.last_access_time[page_num] = self.current_time
    
    def _allocate_with_swap(self, process):
        """Asigna proceso usando swapping"""
        free_frames = sum(1 for f in self.ram if f is None)
        pages_needed = process.num_pages - free_frames
        
        if self.swap.used + pages_needed > self.swap.total_frames:
            self.waiting_queue.append(process)
            process.state = ProcessState.WAITING
            self.log(f"EN COLA: P{process.pid}")
            return False
        
        # Swapping LRU
        for _ in range(pages_needed):
            victim_proc, victim_page = self._lru_select_victim()
            if victim_proc:
                self._swap_out(victim_proc, victim_page)
        
        self._assign_to_ram(process)
        process.state = ProcessState.READY
        self.active_processes.append(process)
        self.scheduler.add_process(process)
        
        self.log(f"ASIGNADO CON SWAP: P{process.pid}")
        return True
    
    def _lru_select_victim(self):
        """Selecciona victima usando LRU"""
        oldest_time = self.current_time + 1
        victim_proc = None
        victim_page = None
        
        for proc in self.active_processes:
            for page in proc.pages_in_ram:
                access_time = proc.last_access_time.get(page, 0)
                if access_time < oldest_time:
                    oldest_time = access_time
                    victim_proc = proc
                    victim_page = page
        
        return victim_proc, victim_page
    
    def _swap_out(self, process, page_num):
        """Mueve pagina de RAM a Swap"""
        page_table = self.page_tables[process.pid]
        entry = page_table.get(page_num)
        
        if entry and entry.in_ram:
            frame = entry.frame
            swap_loc = self.swap.allocate(process.pid, page_num)
            
            if swap_loc is not None:
                entry.frame = None
                entry.swap_loc = swap_loc
                entry.in_ram = False
                
                self.ram[frame] = None
                self.frame_map[frame] = None
                
                process.pages_in_ram.discard(page_num)
                process.pages_in_swap.add(page_num)
                
                self.stats.total_swaps += 1
    
    def _swap_in(self, process, page_num):
        """Recupera pagina de Swap a RAM"""
        page_table = self.page_tables[process.pid]
        entry = page_table.get(page_num)
        
        if entry and entry.swap_loc is not None:
            frame = self._get_free_frame()
            if frame is None:
                victim_proc, victim_page = self._lru_select_victim()
                if victim_proc:
                    self._swap_out(victim_proc, victim_page)
                    frame = self._get_free_frame()
            
            if frame is not None:
                swap_loc = entry.swap_loc
                
                self.ram[frame] = process.pid
                self.frame_map[frame] = (process.pid, page_num)
                
                entry.frame = frame
                entry.swap_loc = None
                entry.in_ram = True
                entry.last_access = self.current_time
                
                self.swap.free(swap_loc)
                
                process.pages_in_swap.discard(page_num)
                process.pages_in_ram.add(page_num)
                process.last_access_time[page_num] = self.current_time
                
                return True
        return False
    
    def access_page(self, process, page_num):
        """Simula acceso a una pagina"""
        page_table = self.page_tables.get(process.pid)
        if not page_table:
            return
        
        frame, fault = page_table.translate(page_num)
        
        if fault:
            process.page_faults += 1
            self.stats.total_page_faults += 1
            
            if page_num in process.pages_in_swap:
                self._swap_in(process, page_num)
        
        self.stats.memory_accesses += 1
        
        if page_num in process.last_access_time:
            process.last_access_time[page_num] = self.current_time
    
    def _free_process_memory(self, process):
        """Libera memoria de un proceso"""
        for page in list(process.pages_in_ram):
            entry = self.page_tables[process.pid].get(page)
            if entry and entry.in_ram:
                frame = entry.frame
                self.ram[frame] = None
                self.frame_map[frame] = None
        
        self.swap.free_process(process.pid)
        
        if process.pid in self.page_tables:
            del self.page_tables[process.pid]
    
    def _get_free_frame(self):
        """Busca frame libre en RAM"""
        for i in range(self.total_frames):
            if self.ram[i] is None:
                return i
        return None
    
    # ==================== SINCRONIZACION ====================
    
    def create_semaphore(self, name, initial_value=1):
        """Crea un semaforo"""
        self.semaphores[name] = Semaphore(name, initial_value)
        self.log(f"SEMAFORO CREADO: {name} (valor={initial_value})")
        return self.semaphores[name]
    
    def semaphore_wait(self, process, sem_name):
        """Operacion Wait en semaforo"""
        if sem_name not in self.semaphores:
            return False
        
        sem = self.semaphores[sem_name]
        if not sem.wait(process):
            if process in self.active_processes:
                self.active_processes.remove(process)
            self.blocked_processes.append(process)
            
            if process.state == ProcessState.RUNNING:
                self.cpu.release()
            
            self.stats.total_blocks += 1
            self.log(f"BLOQUEADO: P{process.pid} en {sem_name}")
            return False
        
        return True
    
    def semaphore_signal(self, process, sem_name):
        """Operacion Signal en semaforo"""
        if sem_name not in self.semaphores:
            return
        
        sem = self.semaphores[sem_name]
        unblocked = sem.signal(process)
        
        if unblocked:
            if unblocked in self.blocked_processes:
                self.blocked_processes.remove(unblocked)
            self.active_processes.append(unblocked)
            self.scheduler.add_process(unblocked)
            self.log(f"DESBLOQUEADO: P{unblocked.pid} de {sem_name}")
    
    def create_shared_memory(self, name, size=10):
        """Crea area de memoria compartida"""
        self.shared_memory[name] = SharedMemory(name, size)
        self.log(f"MEMORIA COMPARTIDA: {name} creada (tamano={size})")
        return self.shared_memory[name]
    
    def detect_deadlock(self):
        """Detecta interbloqueos simples"""
        if not self.blocked_processes:
            return []
        
        if len(self.blocked_processes) >= len(self.active_processes) and len(self.active_processes) > 0:
            if not self.scheduler.has_processes() and self.cpu.is_free():
                self.stats.deadlocks_detected += 1
                self.log("DEADLOCK DETECTADO")
                return self.blocked_processes
        
        return []
    
    # ==================== UTILIDADES ====================
    
    def get_ram_utilization(self):
        used = sum(1 for f in self.ram if f is not None)
        return (used / self.total_frames * 100) if self.total_frames > 0 else 0
    
    def increment_time(self):
        """Incrementa reloj del sistema"""
        self.current_time += 1
        
        for proc in self.active_processes:
            if proc.state == ProcessState.READY:
                proc.waiting_time += 1
    
    # ==================== VISUALIZACION ====================
    
    def display_status(self):
        """Muestra estado general del sistema"""
        print(f"\n{'='*70}")
        print(f"ESTADO DEL SISTEMA - Ciclo {self.current_time}")
        print(f"{'='*70}")
        print(f"\n[CPU]  Utilizacion: {self.cpu.get_utilization():.1f}% | "
              f"Proceso: {f'P{self.cpu.current_process.pid}' if self.cpu.current_process else 'IDLE'}")
        print(f"[RAM]  {self.get_ram_utilization():.1f}% | "
              f"Swap: {self.swap.get_utilization():.1f}%")
        print(f"[PROC] Activos:{len(self.active_processes)} | "
              f"Bloqueados:{len(self.blocked_processes)} | "
              f"Cola:{len(self.scheduler.ready_queue)}")
        print(f"[STATS] PF:{self.stats.total_page_faults} | "
              f"Tasa: {self.stats.page_fault_rate():.1f}% | "
              f"Swaps:{self.stats.total_swaps}")
    
    def display_processes(self):
        """Muestra lista de procesos"""
        print(f"\n{'='*70}")
        print("PROCESOS ACTIVOS")
        print(f"{'='*70}")
        print(f"{'PID':<6} {'Estado':<12} {'CPU':<8} {'Prio':<6} {'RAM':<6} {'Swap':<6}")
        print("-"*70)
        
        for proc in self.active_processes[:15]:
            print(f"P{proc.pid:<5} {proc.state.value:<12} "
                  f"{proc.remaining_cpu:<8} {proc.priority:<6} "
                  f"{len(proc.pages_in_ram):<6} {len(proc.pages_in_swap):<6}")
    
    def display_stats(self):
        """Muestra estadisticas finales"""
        self.stats.calculate_cpu_metrics(self.all_processes)
        
        print(f"\n{'='*70}")
        print("ESTADISTICAS FINALES")
        print(f"{'='*70}")
        print(f"\n[Procesos]")
        print(f"  Total creados:     {self.stats.total_processes}")
        print(f"  Completados:       {self.stats.completed_processes}")
        print(f"  Rechazados:        {self.stats.rejected_processes}")
        print(f"  Term. forzadas:    {self.stats.forced_terminations}")
        
        print(f"\n[CPU] Planificador: FCFS")
        print(f"  Utilizacion:       {self.cpu.get_utilization():.2f}%")
        print(f"  Context switches:  {self.cpu.context_switches}")
        print(f"  Avg. Waiting:      {self.stats.avg_waiting_time:.2f} ciclos")
        print(f"  Avg. Turnaround:   {self.stats.avg_turnaround_time:.2f} ciclos")
        
        print(f"\n[Memoria]")
        print(f"  Page Faults:       {self.stats.total_page_faults}")
        print(f"  Tasa de fallos:    {self.stats.page_fault_rate():.2f}%")
        print(f"  Total Swaps:       {self.stats.total_swaps}")
        
        print(f"\n[Sincronizacion]")
        print(f"  Bloqueos totales:  {self.stats.total_blocks}")
        print(f"  Deadlocks:         {self.stats.deadlocks_detected}")
        print(f"{'='*70}\n")
