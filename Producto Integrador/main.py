"""Simulador Completo de Gestion de Procesos - CPU (FCFS)"""

import sys
import time
import random
import os
import configparser
from gestor_memoria import ProcessManager
from clases import TerminationCause

def clear_screen():
    """Limpia la pantalla"""
    os.system('clear' if os.name == 'posix' else 'cls')

def generate_process(config, pm):
    """Genera un proceso aleatorio"""
    size = random.randint(
        config.getint('SIMULATION', 'process_size_min'),
        config.getint('SIMULATION', 'process_size_max')
    )
    lifetime = random.randint(
        config.getint('SIMULATION', 'process_lifetime_min'),
        config.getint('SIMULATION', 'process_lifetime_max')
    )
    priority = random.randint(1, 10)
    cpu_burst = random.randint(3, lifetime)
    
    return pm.create_process(size, lifetime, priority, cpu_burst)

def demo_producer_consumer(pm):
    """Demostracion del problema Productor-Consumidor"""
    clear_screen()
    print(f"\n{'='*70}")
    print("PROBLEMA PRODUCTOR-CONSUMIDOR")
    print(f"{'='*70}")
    print("\nEste ejemplo demuestra:")
    print("  - Sincronizacion con Semaforos")
    print("  - Memoria Compartida (Buffer)")
    print("  - Coordinacion entre procesos\n")
    
    input("Presione ENTER para iniciar...")
    
    # Crear recursos de sincronizacion
    buffer_size = 5
    pm.create_shared_memory('buffer', buffer_size)
    pm.create_semaphore('mutex', 1)
    pm.create_semaphore('empty', buffer_size)
    pm.create_semaphore('full', 0)
    
    print(f"\nBuffer creado (tamano={buffer_size})")
    print("Semaforos creados: mutex, empty, full\n")
    
    # Crear procesos productor y consumidor
    producer = pm.create_process(512, 30, priority=3, cpu_burst=25)
    consumer = pm.create_process(512, 30, priority=3, cpu_burst=25)
    
    producer.role = "Productor"
    consumer.role = "Consumidor"
    
    pm.allocate_process(producer)
    pm.allocate_process(consumer)
    
    print(f"{producer.role} P{producer.pid} creado")
    print(f"{consumer.role} P{consumer.pid} creado\n")
    
    time.sleep(2)
    
    # Simular interaccion
    buffer = pm.shared_memory['buffer']
    items_produced = 0
    items_consumed = 0
    
    for cycle in range(20):
        pm.increment_time()
        
        # Productor intenta producir
        if producer.is_active() and random.random() > 0.3:
            if pm.semaphore_wait(producer, 'empty'):
                if pm.semaphore_wait(producer, 'mutex'):
                    # Seccion critica: producir
                    item = f"Item-{items_produced}"
                    if buffer.write(producer, item):
                        items_produced += 1
                        print(f"[Ciclo {pm.current_time:2d}] P{producer.pid} PRODUJO: {item}")
                    
                    pm.semaphore_signal(producer, 'mutex')
                    pm.semaphore_signal(producer, 'full')
        
        # Consumidor intenta consumir
        if consumer.is_active() and random.random() > 0.4:
            if pm.semaphore_wait(consumer, 'full'):
                if pm.semaphore_wait(consumer, 'mutex'):
                    # Seccion critica: consumir
                    item = buffer.read(consumer)
                    if item:
                        items_consumed += 1
                        print(f"[Ciclo {pm.current_time:2d}] P{consumer.pid} CONSUMIO: {item[1]}")
                    
                    pm.semaphore_signal(consumer, 'mutex')
                    pm.semaphore_signal(consumer, 'empty')
        
        # Ejecutar CPU
        pm.schedule_cpu()
        
        # Accesos a memoria aleatorios
        for proc in [producer, consumer]:
            if proc.is_active() and proc.num_pages > 0:
                page = random.randint(0, proc.num_pages - 1)
                pm.access_page(proc, page)
        
        time.sleep(0.5)
    
    print(f"\n{'='*70}")
    print("RESULTADOS DEL DEMO")
    print(f"{'='*70}")
    print(f"Items producidos:  {items_produced}")
    print(f"Items consumidos:  {items_consumed}")
    print(f"En buffer:         {len(buffer.buffer)}")
    print(f"\nHistorial del semaforo 'mutex':")
    for event in pm.semaphores['mutex'].history[-10:]:
        print(f"  - {event}")
    
    # Terminar procesos
    pm.force_terminate_process(producer, TerminationCause.COMPLETED)
    pm.force_terminate_process(consumer, TerminationCause.COMPLETED)
    
    input(f"\n\n{'='*70}\nPresione ENTER para continuar...")

def run_automatic_mode(pm, config):
    """Modo automatico con generacion continua"""
    print("\nModo Automatico")
    print("Presione Ctrl+C para detener\n")
    time.sleep(2)
    
    max_procs = config.getint('SIMULATION', 'max_processes')
    next_arrival = random.randint(
        config.getint('SIMULATION', 'process_arrival_min'),
        config.getint('SIMULATION', 'process_arrival_max')
    )
    
    cycle = 0
    generated = 0
    
    try:
        while generated < max_procs or pm.active_processes:
            cycle += 1
            pm.increment_time()
            
            # Generar nuevo proceso
            if cycle >= next_arrival and generated < max_procs:
                proc = generate_process(config, pm)
                generated += 1
                pm.allocate_process(proc)
                pm.log(f"LLEGADA: P{proc.pid} ({proc.size_kb}KB, CPU:{proc.cpu_burst}, Prio:{proc.priority})")
                
                next_arrival = cycle + random.randint(
                    config.getint('SIMULATION', 'process_arrival_min'),
                    config.getint('SIMULATION', 'process_arrival_max')
                )
            
            # Planificacion de CPU (FCFS)
            pm.schedule_cpu()
            
            # Simular accesos a memoria
            for proc in list(pm.active_processes):
                if proc.num_pages > 0 and proc.state.value in ["En Ejecucion", "Listo"]:
                    for _ in range(random.randint(1, min(3, proc.num_pages))):
                        page = random.randint(0, proc.num_pages - 1)
                        pm.access_page(proc, page)
                
                # Decrementar vida
                proc.remaining_lifetime -= 1
                if proc.remaining_lifetime <= 0 and proc.state.value != "Terminado":
                    pm.terminate_process(proc)
            
            # Detectar deadlock
            deadlocked = pm.detect_deadlock()
            if deadlocked:
                print(f"\nDEADLOCK DETECTADO con {len(deadlocked)} procesos")
                for proc in deadlocked:
                    pm.force_terminate_process(proc, TerminationCause.DEADLOCK)
            
            # Mostrar estado
            if cycle % 1 == 0:
                clear_screen()
                pm.display_status()
                
                if pm.active_processes:
                    print(f"\nPROCESOS ACTIVOS (Top 10):")
                    print(f"{'PID':<6} {'Estado':<12} {'CPU':<8} {'Vida':<6} {'Prio':<6}")
                    print("-"*50)
                    for p in pm.active_processes[:10]:
                        print(f"P{p.pid:<5} {p.state.value:<12} "
                              f"{p.remaining_cpu:<8} {p.remaining_lifetime:<6} {p.priority:<6}")
            
            time.sleep(0.8)
            
            if generated >= max_procs and not pm.active_processes and not pm.waiting_queue:
                print("\nSimulacion completada")
                break
    
    except KeyboardInterrupt:
        print("\n\nSimulacion detenida")

def run_interactive_mode(pm, config):
    """Modo interactivo con comandos completos"""
    print("\nModo Interactivo")
    print("\nComandos disponibles:")
    print("  n - Generar nuevo proceso")
    print("  s - Simular un ciclo")
    print("  c - Estado de CPU")
    print("  m - Mapa de RAM")
    print("  w - Mapa de Swap")
    print("  p - Ver procesos activos")
    print("  t - Tabla de paginas")
    print("  suspend <pid> - Suspender proceso")
    print("  resume <pid> - Reanudar proceso")
    print("  kill <pid> - Terminar proceso forzadamente")
    print("  sem - Crear semaforo")
    print("  deadlock - Detectar deadlock")
    print("  e - Estadisticas")
    print("  q - Salir")
    
    generated = 0
    max_procs = config.getint('SIMULATION', 'max_processes')
    
    while True:
        cmd = input("\n> ").strip().lower()
        parts = cmd.split()
        cmd_base = parts[0] if parts else ""
        
        if cmd_base == 'n':
            if generated < max_procs:
                proc = generate_process(config, pm)
                generated += 1
                if pm.allocate_process(proc):
                    print(f"P{proc.pid} asignado ({proc.size_kb}KB, CPU:{proc.cpu_burst}, Prio:{proc.priority})")
                else:
                    print(f"P{proc.pid} en cola de espera")
            else:
                print("Maximo de procesos alcanzado")
        
        elif cmd_base == 's':
            pm.increment_time()
            pm.schedule_cpu()
            
            for proc in list(pm.active_processes):
                if proc.num_pages > 0:
                    for _ in range(random.randint(1, min(2, proc.num_pages))):
                        pm.access_page(proc, random.randint(0, proc.num_pages - 1))
                
                proc.remaining_lifetime -= 1
                if proc.remaining_lifetime <= 0:
                    pm.terminate_process(proc)
            
            print(f"Ciclo {pm.current_time} ejecutado")
        
        elif cmd_base == 'c':
            print(f"\n{'='*60}")
            print("ESTADO DE CPU")
            print(f"{'='*60}")
            if pm.cpu.current_process:
                proc = pm.cpu.current_process
                print(f"Proceso en ejecucion: P{proc.pid}")
                print(f"  CPU restante:       {proc.remaining_cpu}")
                print(f"  Prioridad:          {proc.priority}")
            else:
                print("CPU en IDLE")
            print(f"\nUtilizacion:     {pm.cpu.get_utilization():.2f}%")
            print(f"Context switches: {pm.cpu.context_switches}")
            print(f"{'='*60}")
        
        elif cmd_base == 'm':
            display_memory_map(pm)
        
        elif cmd_base == 'w':
            display_swap_map(pm)
        
        elif cmd_base == 'p':
            pm.display_processes()
        
        elif cmd_base == 't':
            if len(parts) > 1:
                try:
                    display_page_table(pm, int(parts[1]))
                except:
                    print("PID invalido")
            else:
                pid = input("  PID: P")
                try:
                    display_page_table(pm, int(pid))
                except:
                    print("PID invalido")
        
        elif cmd_base == 'suspend':
            if len(parts) > 1:
                try:
                    pid = int(parts[1])
                    proc = next((p for p in pm.active_processes if p.pid == pid), None)
                    if proc:
                        pm.suspend_process(proc)
                    else:
                        print(f"Proceso P{pid} no encontrado")
                except:
                    print("Comando invalido: suspend <pid>")
            else:
                print("Uso: suspend <pid>")
        
        elif cmd_base == 'resume':
            if len(parts) > 1:
                try:
                    pid = int(parts[1])
                    proc = next((p for p in pm.blocked_processes if p.pid == pid), None)
                    if proc:
                        pm.resume_process(proc)
                    else:
                        print(f"Proceso P{pid} no encontrado o no esta bloqueado")
                except:
                    print("Comando invalido: resume <pid>")
            else:
                print("Uso: resume <pid>")
        
        elif cmd_base == 'kill':
            if len(parts) > 1:
                try:
                    pid = int(parts[1])
                    proc = next((p for p in pm.all_processes if p.pid == pid), None)
                    if proc and proc.state.value != "Terminado":
                        pm.force_terminate_process(proc, TerminationCause.FORCED)
                    else:
                        print(f"Proceso P{pid} no encontrado o ya terminado")
                except:
                    print("Comando invalido: kill <pid>")
            else:
                print("Uso: kill <pid>")
        
        elif cmd_base == 'sem':
            name = input("  Nombre del semaforo: ").strip()
            value = input("  Valor inicial (default=1): ").strip()
            value = int(value) if value else 1
            pm.create_semaphore(name, value)
            print(f"Semaforo '{name}' creado")
        
        elif cmd_base == 'deadlock':
            deadlocked = pm.detect_deadlock()
            if deadlocked:
                print(f"\nDEADLOCK DETECTADO:")
                for proc in deadlocked:
                    print(f"  - P{proc.pid} bloqueado en: {proc.blocked_on}")
            else:
                print("No se detecto deadlock")
        
        elif cmd_base == 'e':
            pm.display_stats()
        
        elif cmd_base == 'q':
            break
        
        else:
            print("Comando no reconocido")

def display_memory_map(pm):
    """Muestra mapa de RAM"""
    print(f"\n{'='*70}")
    print(f"MAPA DE MEMORIA RAM")
    print(f"{'='*70}")
    used = sum(1 for f in pm.ram if f is not None)
    print(f"Frames: {used}/{pm.total_frames} | Utilizacion: {pm.get_ram_utilization():.1f}%")
    print(f"{'-'*70}")
    for i in range(min(20, pm.total_frames)):
        if pm.ram[i]:
            _, page = pm.frame_map[i]
            print(f"Marco {i:2d}: P{pm.ram[i]} - Pagina {page}")
        else:
            print(f"Marco {i:2d}: [Libre]")
    if pm.total_frames > 20:
        print(f"... ({pm.total_frames - 20} marcos mas)")
    print(f"{'='*70}\n")

def display_swap_map(pm):
    """Muestra mapa de Swap"""
    print(f"\n{'='*70}")
    print(f"MAPA DE SWAP")
    print(f"{'='*70}")
    print(f"Frames: {pm.swap.used}/{pm.swap.total_frames} | "
          f"Utilizacion: {pm.swap.get_utilization():.1f}%")
    print(f"{'-'*70}")
    count = 0
    for i, data in enumerate(pm.swap.frames):
        if data:
            pid, page = data
            print(f"Frame {i:2d}: P{pid} - Pagina {page}")
            count += 1
            if count >= 20:
                remaining = pm.swap.used - count
                if remaining > 0:
                    print(f"... ({remaining} frames mas)")
                break
    print(f"{'='*70}\n")

def display_page_table(pm, pid):
    """Muestra tabla de paginas"""
    if pid not in pm.page_tables:
        print(f"Proceso P{pid} no encontrado")
        return
    
    pt = pm.page_tables[pid]
    print(f"\n{'='*60}")
    print(f"TABLA DE PAGINAS - Proceso P{pid}")
    print(f"{'='*60}")
    print(f"{'Pag':<10} {'Marco':<10} {'Estado':<15}")
    print(f"{'-'*60}")
    for page_num in sorted(pt.entries.keys()):
        entry = pt.entries[page_num]
        if entry.in_ram:
            print(f"{page_num:<10} {entry.frame:<10} {'RAM':<15}")
        elif entry.swap_loc is not None:
            print(f"{page_num:<10} {'-':<10} {'SWAP':<15}")
        else:
            print(f"{page_num:<10} {'-':<10} {'No cargada':<15}")
    print(f"{'='*60}\n")

def main():
    """Funcion principal"""
    print(f"\n{'#'*70}")
    print("=== SIMULADOR COMPLETO DE GESTION DE PROCESOS ===")
    print("=== CPU (FCFS) | Memoria | Sincronizacion ===")
    print(f"{'#'*70}")
    
    # Inicializar
    pm = ProcessManager('config.ini')
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    print("\nSimulador inicializado")
    print("Planificador: FCFS (First Come, First Served)")
    if pm.logger:
        print(f"Logs: {config.get('LOGS', 'log_file')}")
    
    # Menu principal
    while True:
        print(f"\n{'='*70}")
        print("MENU PRINCIPAL")
        print(f"{'='*70}")
        print("  [1] Modo Automatico")
        print("  [2] Modo Interactivo")
        print("  [3] Productor-Consumidor")
        print("  [4] Salir")
        
        choice = input("\nOpcion: ").strip()
        
        if choice == '1':
            run_automatic_mode(pm, config)
            pm.display_stats()
            break
        elif choice == '2':
            run_interactive_mode(pm, config)
            pm.display_stats()
            break
        elif choice == '3':
            demo_producer_consumer(pm)
        elif choice == '4':
            print("\nHasta luego!")
            break
        else:
            print("Opcion invalida")
    
    # Cerrar
    if pm.logger:
        pm.logger.info("="*70)
        pm.logger.info("SIMULADOR FINALIZADO")
        pm.logger.info("="*70)
        print(f"\nLogs guardados")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
