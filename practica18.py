import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue

class FloralAudioVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizador Floral de Audio")
        self.root.geometry("900x700")
        self.root.configure(bg='#0a0a1a')
        
        # Parámetros
        self.sample_rate = 44100
        self.block_size = 2048
        self.num_petals = 5  # Número de pétalos
        self.num_lines = 20  # Número de líneas concéntricas
        self.base_radius = 1.0
        self.ganancia = 5.0
        self.suavizado = 0.85
        self.rotation_speed = 0.002
        
        # Estado
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.audio_buffer = np.zeros(self.sample_rate, dtype=np.float32)
        self.buffer_pos = 0
        self.rotation_angle = 0
        self.stream = None
        
        # Preparar FFT
        self.freqs = np.fft.rfftfreq(self.block_size, d=1.0/self.sample_rate)
        mask = (self.freqs >= 80) & (self.freqs <= 4000)
        self.freq_indices = np.where(mask)[0]
        
        # Ángulos para la curva
        self.theta = np.linspace(0, 2*np.pi, 500)
        
        # Crear interfaz
        self.setup_ui()
        self.setup_visualizer()
        
    def get_audio_devices(self):
        try:
            devices = sd.query_devices()
            input_devices = []
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    input_devices.append((i, dev['name']))
            return input_devices
        except:
            return [(0, "Micrófono por defecto")]
    
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg='#0a0a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Panel izquierdo: Visualizador
        self.viz_frame = tk.Frame(main_frame, bg='#0a0a1a')
        self.viz_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Panel derecho: Controles
        control_frame = tk.Frame(main_frame, bg='#1a1a2e', width=250)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        control_frame.pack_propagate(False)
        
        tk.Label(control_frame, text="Controles", 
                font=('Arial', 14, 'bold'),
                bg='#1a1a2e', fg='#ffffff').pack(pady=10)
        
        # Selector de micrófono
        self.devices = self.get_audio_devices()
        tk.Label(control_frame, text="Micrófono:", 
                bg='#1a1a2e', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.device_var = tk.StringVar()
        device_names = [f"{i}: {name}" for i, name in self.devices]
        self.device_combo = ttk.Combobox(control_frame, textvariable=self.device_var,
                                         values=device_names, state='readonly')
        self.device_combo.pack(fill=tk.X, padx=10, pady=5)
        if self.devices:
            self.device_combo.current(0)
        
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10, padx=10)
        
        # Número de pétalos
        tk.Label(control_frame, text=f"Pétalos: {self.num_petals}", 
                bg='#1a1a2e', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.petals_var = tk.IntVar(value=self.num_petals)
        self.petals_scale = tk.Scale(control_frame, from_=3, to=8, resolution=1,
                                     orient=tk.HORIZONTAL, variable=self.petals_var,
                                     bg='#1a1a2e', fg='#ffffff', troughcolor='#2a2a3e',
                                     command=self.update_petals)
        self.petals_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # Control de ganancia
        tk.Label(control_frame, text=f"Ganancia: {self.ganancia}", 
                bg='#1a1a2e', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.gain_var = tk.DoubleVar(value=self.ganancia)
        self.gain_scale = tk.Scale(control_frame, from_=1, to=20, resolution=0.5,
                                   orient=tk.HORIZONTAL, variable=self.gain_var,
                                   bg='#1a1a2e', fg='#ffffff', troughcolor='#2a2a3e',
                                   command=self.update_gain)
        self.gain_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # Control de suavizado
        tk.Label(control_frame, text=f"Suavizado: {self.suavizado}", 
                bg='#1a1a2e', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.smooth_var = tk.DoubleVar(value=self.suavizado)
        self.smooth_scale = tk.Scale(control_frame, from_=0, to=0.99, resolution=0.01,
                                     orient=tk.HORIZONTAL, variable=self.smooth_var,
                                     bg='#1a1a2e', fg='#ffffff', troughcolor='#2a2a3e',
                                     command=self.update_smooth)
        self.smooth_scale.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10, padx=10)
        
        # Indicador de volumen
        tk.Label(control_frame, text="Nivel de volumen:", 
                bg='#1a1a2e', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.volume_var = tk.DoubleVar(value=0)
        self.volume_bar = ttk.Progressbar(control_frame, variable=self.volume_var,
                                          maximum=100, mode='determinate')
        self.volume_bar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10, padx=10)
        
        # Botones
        btn_frame = tk.Frame(control_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_btn = tk.Button(btn_frame, text="▶ Iniciar", 
                                   command=self.toggle_audio,
                                   bg='#4CAF50', fg='white',
                                   font=('Arial', 10, 'bold'),
                                   relief=tk.FLAT, cursor='hand2')
        self.start_btn.pack(fill=tk.X, pady=5)
        
        self.stop_btn = tk.Button(btn_frame, text="⏹ Detener", 
                                  command=self.stop_audio,
                                  bg='#f44336', fg='white',
                                  font=('Arial', 10, 'bold'),
                                  relief=tk.FLAT, cursor='hand2',
                                  state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=5)
        
        tk.Label(control_frame, text="Habla al micrófono\npara ver el efecto", 
                bg='#1a1a2e', fg='#888888',
                font=('Arial', 9)).pack(pady=10)
    
    def setup_visualizer(self):
        self.fig = Figure(figsize=(6, 6), dpi=100, facecolor='#0a0a1a')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#0a0a1a')
        self.ax.set_xlim(-4, 4)
        self.ax.set_ylim(-4, 4)
        self.ax.set_aspect('equal')
        self.ax.axis('off')
        
        # Crear gradiente de colores (rosa → naranja → blanco)
        colors = ['#ff1493', '#ff6b35', '#ffa500', '#ffffff']
        self.cmap = LinearSegmentedColormap.from_list('custom', colors, N=self.num_lines)
        
        # Líneas (se actualizarán en el loop)
        self.lines = []
        for i in range(self.num_lines):
            line, = self.ax.plot([], [], linewidth=0.8, alpha=0.6)
            self.lines.append(line)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.update_visualizer()
    
    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status)
        data = indata[:, 0].astype(np.float32)
        self.audio_queue.put(data)
    
    def process_audio(self):
        while self.is_running:
            try:
                data = self.audio_queue.get(timeout=0.1)
                n = len(data)
                end = self.buffer_pos + n
                if end <= len(self.audio_buffer):
                    self.audio_buffer[self.buffer_pos:end] = data
                else:
                    first = len(self.audio_buffer) - self.buffer_pos
                    self.audio_buffer[self.buffer_pos:] = data[:first]
                    self.audio_buffer[:n-first] = data[first:]
                self.buffer_pos = end % len(self.audio_buffer)
            except queue.Empty:
                continue
    
    def get_audio_amplitude(self):
        """Obtiene la amplitud del audio en diferentes bandas de frecuencia."""
        if len(self.audio_buffer) == 0:
            return np.zeros(self.num_petals)
        
        spectrum = np.abs(np.fft.rfft(self.audio_buffer))
        
        # Dividir el espectro en bandas (una por pétalo)
        band_size = len(spectrum) // self.num_petals
        amplitudes = []
        for i in range(self.num_petals):
            start = i * band_size
            end = (i + 1) * band_size if i < self.num_petals - 1 else len(spectrum)
            band = spectrum[start:end]
            amp = np.mean(band) / 100.0
            amplitudes.append(amp)
        
        return np.array(amplitudes)
    
    def update_visualizer(self):
        if self.is_running:
            # Obtener amplitudes del audio
            amplitudes = self.get_audio_amplitude()
            
            # Suavizar
            if not hasattr(self, 'smoothed_amplitudes'):
                self.smoothed_amplitudes = np.zeros(self.num_petals)
            self.smoothed_amplitudes = (self.suavizado * self.smoothed_amplitudes + 
                                       (1 - self.suavizado) * amplitudes)
            
            # Rotación
            self.rotation_angle += self.rotation_speed
            
            # Dibujar cada línea concéntrica
            for i in range(self.num_lines):
                # Escala para cada línea (más grande hacia afuera)
                scale_factor = 1.0 + (i / self.num_lines) * 0.5
                
                # Radio base con deformación por audio
                r = self.base_radius * scale_factor
                
                # Crear forma de rosa con deformación
                theta_rotated = self.theta + self.rotation_angle
                
                # Fórmula de rosa modificada por audio
                n = self.num_petals
                rose = np.cos(n * theta_rotated)
                
                # Aplicar amplitud de audio a cada pétalo
                for j in range(n):
                    # Ángulo central de cada pétalo
                    petal_angle = (2 * np.pi * j) / n
                    
                    # Encontrar puntos cercanos a este pétalo
                    angle_diff = np.abs(theta_rotated - petal_angle)
                    angle_diff = np.minimum(angle_diff, 2*np.pi - angle_diff)
                    
                    # Peso de influencia (gaussiana)
                    weight = np.exp(-angle_diff**2 / 0.5)
                    
                    # Modificar radio según amplitud del pétalo
                    r += weight * self.smoothed_amplitudes[j] * self.ganancia * scale_factor
                
                # Convertir a coordenadas cartesianas
                x = r * np.cos(theta_rotated)
                y = r * np.sin(theta_rotated)
                
                # Actualizar línea
                self.lines[i].set_data(x, y)
                
                # Color según posición (gradiente)
                color = self.cmap(i / self.num_lines)
                self.lines[i].set_color(color)
                self.lines[i].set_alpha(0.3 + 0.7 * (i / self.num_lines))
            
            # Actualizar volumen
            volume = np.mean(np.abs(self.audio_buffer)) * 100
            self.volume_var.set(min(volume * 10, 100))
            
            self.canvas.draw()
        
        self.root.after(30, self.update_visualizer)
    
    def toggle_audio(self):
        if not self.is_running:
            self.start_audio()
        else:
            self.stop_audio()
    
    def start_audio(self):
        try:
            device_idx = self.device_combo.current()
            if device_idx >= 0:
                device_id = self.devices[device_idx][0]
            else:
                device_id = None
            
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                blocksize=self.block_size,
                device=device_id,
                callback=self.audio_callback
            )
            self.stream.start()
            
            self.is_running = True
            self.smoothed_amplitudes = np.zeros(self.num_petals)
            
            self.process_thread = threading.Thread(target=self.process_audio, daemon=True)
            self.process_thread.start()
            
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar el audio:\n{e}")
    
    def stop_audio(self):
        self.is_running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.volume_var.set(0)
        
        # Resetear líneas
        for line in self.lines:
            line.set_data([], [])
        self.canvas.draw()
    
    def update_petals(self, value):
        self.num_petals = int(value)
        self.petals_scale.config(label=f"Pétalos: {self.num_petals}")
        if hasattr(self, 'smoothed_amplitudes'):
            self.smoothed_amplitudes = np.zeros(self.num_petals)
    
    def update_gain(self, value):
        self.ganancia = float(value)
        self.gain_scale.config(label=f"Ganancia: {self.ganancia:.1f}")
    
    def update_smooth(self, value):
        self.suavizado = float(value)
        self.smooth_scale.config(label=f"Suavizado: {self.suavizado:.2f}")
    
    def on_closing(self):
        self.stop_audio()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FloralAudioVisualizer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()