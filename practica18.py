import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue

# ============ CLASE PRINCIPAL ============
class AudioVisualizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizador de Audio Circular")
        self.root.geometry("900x700")
        self.root.configure(bg='#1e1e1e')
        
        # Parámetros del visualizador
        self.sample_rate = 44100
        self.block_size = 2048
        self.num_bins = 180
        self.radio_base = 1.0
        self.ganancia = 8.0
        self.suavizado = 0.75
        self.rango_freq = (80, 4000)
        
        # Estado
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.audio_buffer = np.zeros(self.sample_rate, dtype=np.float32)
        self.buffer_pos = 0
        self.smoothed = np.zeros(self.num_bins, dtype=np.float32)
        self.stream = None
        self.current_device = None
        
        # Configurar dispositivos
        self.devices = self.get_audio_devices()
        
        # Crear interfaz
        self.setup_ui()
        self.setup_visualizer()
        
    def get_audio_devices(self):
        """Obtiene lista de dispositivos de audio de entrada."""
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
        """Configura la interfaz gráfica."""
        # Frame principal dividido
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Panel izquierdo: Visualizador
        self.viz_frame = tk.Frame(main_frame, bg='#1e1e1e')
        self.viz_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Panel derecho: Controles
        control_frame = tk.Frame(main_frame, bg='#2d2d2d', width=250)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        control_frame.pack_propagate(False)
        
        # Título de controles
        tk.Label(control_frame, text="Controles", 
                font=('Arial', 14, 'bold'),
                bg='#2d2d2d', fg='#ffffff').pack(pady=10)
        
        # Selector de micrófono
        tk.Label(control_frame, text="Micrófono:", 
                bg='#2d2d2d', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.device_var = tk.StringVar()
        device_names = [f"{i}: {name}" for i, name in self.devices]
        self.device_combo = ttk.Combobox(control_frame, textvariable=self.device_var,
                                         values=device_names, state='readonly')
        self.device_combo.pack(fill=tk.X, padx=10, pady=5)
        if self.devices:
            self.device_combo.current(0)
        
        # Separador
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10, padx=10)
        
        # Control de ganancia
        tk.Label(control_frame, text=f"Ganancia: {self.ganancia}", 
                bg='#2d2d2d', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.gain_var = tk.DoubleVar(value=self.ganancia)
        self.gain_scale = tk.Scale(control_frame, from_=1, to=30, resolution=0.5,
                                   orient=tk.HORIZONTAL, variable=self.gain_var,
                                   bg='#2d2d2d', fg='#ffffff', troughcolor='#3d3d3d',
                                   command=self.update_gain)
        self.gain_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # Control de suavizado
        tk.Label(control_frame, text=f"Suavizado: {self.suavizado}", 
                bg='#2d2d2d', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.smooth_var = tk.DoubleVar(value=self.suavizado)
        self.smooth_scale = tk.Scale(control_frame, from_=0, to=0.99, resolution=0.01,
                                     orient=tk.HORIZONTAL, variable=self.smooth_var,
                                     bg='#2d2d2d', fg='#ffffff', troughcolor='#3d3d3d',
                                     command=self.update_smooth)
        self.smooth_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # Control de radio base
        tk.Label(control_frame, text=f"Radio base: {self.radio_base}", 
                bg='#2d2d2d', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.radio_var = tk.DoubleVar(value=self.radio_base)
        self.radio_scale = tk.Scale(control_frame, from_=0.5, to=3.0, resolution=0.1,
                                    orient=tk.HORIZONTAL, variable=self.radio_var,
                                    bg='#2d2d2d', fg='#ffffff', troughcolor='#3d3d3d',
                                    command=self.update_radio)
        self.radio_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # Separador
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10, padx=10)
        
        # Selector de color
        tk.Label(control_frame, text="Color del círculo:", 
                bg='#2d2d2d', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.color_var = tk.StringVar(value='cyan')
        color_frame = tk.Frame(control_frame, bg='#2d2d2d')
        color_frame.pack(fill=tk.X, padx=10, pady=5)
        colors = ['cyan', 'magenta', 'lime', 'yellow', 'orange', 'red', 'white']
        for color in colors:
            btn = tk.Button(color_frame, bg=color, width=2,
                          command=lambda c=color: self.update_color(c))
            btn.pack(side=tk.LEFT, padx=2)
        
        # Separador
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10, padx=10)
        
        # Indicador de volumen
        tk.Label(control_frame, text="Nivel de volumen:", 
                bg='#2d2d2d', fg='#cccccc').pack(anchor=tk.W, padx=10, pady=(5, 0))
        self.volume_var = tk.DoubleVar(value=0)
        self.volume_bar = ttk.Progressbar(control_frame, variable=self.volume_var,
                                          maximum=100, mode='determinate')
        self.volume_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # Separador
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10, padx=10)
        
        # Botones de control
        btn_frame = tk.Frame(control_frame, bg='#2d2d2d')
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
        
        # Info
        tk.Label(control_frame, text="Habla al micrófono\npara ver el efecto", 
                bg='#2d2d2d', fg='#888888',
                font=('Arial', 9)).pack(pady=10)
    
    def setup_visualizer(self):
        """Configura el visualizador matplotlib."""
        self.fig = Figure(figsize=(6, 6), dpi=100, facecolor='#1e1e1e')
        self.ax = self.fig.add_subplot(111, projection='polar')
        self.ax.set_facecolor('#1e1e1e')
        self.ax.set_ylim(0, self.radio_base + self.ganancia + 0.5)
        self.ax.set_yticks([])
        self.ax.set_xticks([])
        self.ax.spines['polar'].set_visible(False)
        self.ax.grid(False)
        
        # Línea inicial
        theta_init = np.linspace(0, 2*np.pi, self.num_bins+1)
        self.line, = self.ax.plot(theta_init, 
                                  np.full_like(theta_init, self.radio_base),
                                  color='cyan', linewidth=2)
        
        # Embed en Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Preparar FFT
        freqs = np.fft.rfftfreq(self.block_size, d=1.0/self.sample_rate)
        mask = (freqs >= self.rango_freq[0]) & (freqs <= self.rango_freq[1])
        freq_indices = np.where(mask)[0]
        
        if len(freq_indices) < self.num_bins:
            self.bin_map = np.array([freq_indices[i % len(freq_indices)] 
                                    for i in range(self.num_bins)])
        else:
            step = len(freq_indices) / self.num_bins
            self.bin_map = np.array([freq_indices[int(i*step)] 
                                    for i in range(self.num_bins)])
        
        # Iniciar actualización
        self.update_visualizer()
    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback para capturar audio."""
        if status:
            print(status)
        data = indata[:, 0].astype(np.float32)
        self.audio_queue.put(data)
    
    def process_audio(self):
        """Procesa el audio en un hilo separado."""
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
    
    def update_visualizer(self):
        """Actualiza el visualizador periódicamente."""
        if self.is_running and len(self.audio_buffer) > 0:
            # FFT
            spectrum = np.abs(np.fft.rfft(self.audio_buffer))
            values = spectrum[self.bin_map]
            values = np.clip(values / 50.0, 0, 1) * self.ganancia
            
            # Suavizado
            self.smoothed[:] = self.suavizado * self.smoothed + (1 - self.suavizado) * values
            
            # Actualizar línea
            theta = np.linspace(0, 2*np.pi, self.num_bins, endpoint=False)
            r = self.radio_base + self.smoothed
            theta_closed = np.append(theta, theta[0])
            r_closed = np.append(r, r[0])
            self.line.set_data(theta_closed, r_closed)
            
            # Actualizar volumen
            volume = np.mean(np.abs(self.audio_buffer)) * 100
            self.volume_var.set(min(volume * 10, 100))
            
            self.canvas.draw()
        
        # Llamar de nuevo en 30ms
        self.root.after(30, self.update_visualizer)
    
    def toggle_audio(self):
        """Inicia o detiene la captura de audio."""
        if not self.is_running:
            self.start_audio()
        else:
            self.stop_audio()
    
    def start_audio(self):
        """Inicia la captura de audio."""
        try:
            # Obtener dispositivo seleccionado
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
            
            # Iniciar hilo de procesamiento
            self.process_thread = threading.Thread(target=self.process_audio, daemon=True)
            self.process_thread.start()
            
            # Actualizar botones
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar el audio:\n{e}")
    
    def stop_audio(self):
        """Detiene la captura de audio."""
        self.is_running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # Actualizar botones
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.volume_var.set(0)
    
    def update_gain(self, value):
        """Actualiza la ganancia."""
        self.ganancia = float(value)
        self.gain_scale.config(label=f"Ganancia: {self.ganancia:.1f}")
        self.ax.set_ylim(0, self.radio_base + self.ganancia + 0.5)
    
    def update_smooth(self, value):
        """Actualiza el suavizado."""
        self.suavizado = float(value)
        self.smooth_scale.config(label=f"Suavizado: {self.suavizado:.2f}")
    
    def update_radio(self, value):
        """Actualiza el radio base."""
        self.radio_base = float(value)
        self.radio_scale.config(label=f"Radio base: {self.radio_base:.1f}")
        self.ax.set_ylim(0, self.radio_base + self.ganancia + 0.5)
    
    def update_color(self, color):
        """Actualiza el color del círculo."""
        self.color_var.set(color)
        self.line.set_color(color)
        self.canvas.draw()
    
    def on_closing(self):
        """Maneja el cierre de la ventana."""
        self.stop_audio()
        self.root.destroy()

# ============ EJECUTAR APLICACIÓN ============
if __name__ == "__main__":
    root = tk.Tk()
    app = AudioVisualizerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()