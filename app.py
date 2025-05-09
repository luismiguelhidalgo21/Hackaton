import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import requests
import base64
import re
import json
from PIL import Image, ImageTk, ImageOps
from blockchain import Blockchain
import pytesseract
from pytesseract import image_to_string
import logging
import platform
import sys
import matplotlib.pyplot as plt  # Importar matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # Importar para integrar gráficos en tkinter
from matplotlib.figure import Figure  # Importar para crear figuras de matplotlib

class FacturacionApp:
    def __init__(self, root):
        self.root = root
        self.setup_config()
        self.setup_ui()
        
    def setup_config(self):
        """Configuración inicial optimizada para RPi"""
        self.root.title("🧾 Facturación RPi")
        
        # Detección de hardware
        self.is_rpi = "arm" in platform.machine().lower()
        self.is_linux = sys.platform.startswith('linux')
        
        # Configuración de tamaño según dispositivo
        if self.is_rpi:
            self.root.geometry("720x580")
            self.img_preview_size = (320, 320)
            self.font_size = 10
        else:
            self.root.geometry("900x700")
            self.img_preview_size = (450, 450)
            self.font_size = 11
            
        # Configuración de logging optimizada
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='facturacion.log',
            filemode='a'
        )
        
        # Configuración de OCR
        self.setup_ocr()
        
        # Configuración de API
        self.API_URL = "https://api.deepseek.com/v1/chat/completions"
        self.API_KEY = "sk-5397f99b3feb44c9a51ec8a079f1b5a0"
        
        # Inicializar blockchain
        self.blockchain = Blockchain()
        self.current_image = None
        
    def setup_ocr(self):
        """Configuración de OCR para Raspberry Pi"""
        try:
            # Rutas específicas para Linux/RPi
            possible_paths = [
                '/usr/bin/tesseract',
                '/usr/local/bin/tesseract',
                '/usr/share/tesseract-ocr/4.00/tessdata'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'
                    break
            
            # Verificación de idioma español
            if not os.path.exists(os.path.join(os.environ.get('TESSDATA_PREFIX', ''), 'spa.traineddata')):
                logging.warning("Datos de idioma español no encontrados")
                if self.is_rpi:
                    messagebox.showwarning(
                        "Configuración OCR",
                        "Para mejor rendimiento, instale:\nsudo apt-get install tesseract-ocr-spa"
                    )
        except Exception as e:
            logging.error(f"Error configurando OCR: {str(e)}")
            messagebox.showerror(
                "Error OCR",
                f"Configuración OCR falló:\n{str(e)}\n\n"
                "En Raspberry Pi ejecute:\n"
                "sudo apt-get install tesseract-ocr\n"
                "sudo apt-get install libtesseract-dev"
            )
    
    def setup_ui(self):
        """Interfaz gráfica optimizada para RPi"""
        # Estilo simplificado para mejor rendimiento
        style = ttk.Style()
        style.theme_use('clam' if not self.is_rpi else 'default')
        
        # Configuraciones comunes
        style.configure('.', 
                      font=('Arial', self.font_size),
                      background='#f5f7fa')
        style.configure('TButton', 
                       padding=5,
                       background='#4a6baf',
                       foreground='white')
        style.map('TButton',
                 background=[('active', '#3a5a9f')])
        style.configure('TFrame', background='#f5f7fa')
        style.configure('TLabel', background='#f5f7fa')
        style.configure('TNotebook.Tab', padding=(10, 4))
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 8))
        
        title_font = ('Arial', 16, 'bold') if not self.is_rpi else ('Arial', 14, 'bold')
        ttk.Label(
            title_frame,
            text="🧾 Facturación Inteligente",
            font=title_font,
            background='#f5f7fa'
        ).pack()
        
        # Notebook (pestañas)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña de Subir Factura
        self.setup_upload_tab(notebook)
        
        # Pestaña de Reportes
        self.setup_report_tab(notebook)
        
    def setup_upload_tab(self, notebook):
        """Configuración de la pestaña de subida"""
        upload_tab = ttk.Frame(notebook)
        notebook.add(upload_tab, text="📤 Subir")
        
        # Panel de controles
        control_frame = ttk.Frame(upload_tab)
        control_frame.pack(pady=8, fill=tk.X)
        
        ttk.Button(
            control_frame,
            text="Seleccionar",
            command=self.cargar_documento,
            width=12
        ).pack(side=tk.LEFT, padx=3)
        
        self.btn_reintentar = ttk.Button(
            control_frame,
            text="Reanalizar",
            command=self.reintentar_analisis,
            state=tk.DISABLED,
            width=12
        )
        self.btn_reintentar.pack(side=tk.LEFT, padx=3)
        
        # Área de visualización
        display_frame = ttk.Frame(upload_tab)
        display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.lbl_imagen = ttk.Label(display_frame)
        self.lbl_imagen.pack(pady=5)
        
        self.lbl_resultado = ttk.Label(
            display_frame,
            text="Monto: -",
            font=('Arial', 12, 'bold'),
            foreground='#333'
        )
        self.lbl_resultado.pack(pady=8)
        
    def setup_report_tab(self, notebook):
        """Configuración de la pestaña de reportes"""
        report_tab = ttk.Frame(notebook)
        notebook.add(report_tab, text="📊 Reportes")
        
        # Controles de reporte
        report_control = ttk.Frame(report_tab)
        report_control.pack(pady=8)
        
        ttk.Label(
            report_control,
            text="Periodo:",
            font=('Arial', self.font_size)
        ).pack(side=tk.LEFT, padx=3)
        
        self.cbo_periodo = ttk.Combobox(
            report_control,
            values=["Semanal", "Mensual", "Anual", "Completo"],
            state="readonly",
            width=10
        )
        self.cbo_periodo.current(1)
        self.cbo_periodo.pack(side=tk.LEFT, padx=3)
        
        ttk.Button(
            report_control,
            text="Generar",
            command=self.generar_reporte,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        # Área de reporte
        report_display = ttk.Frame(report_tab)
        report_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        self.txt_reporte = tk.Text(
            report_display,
            height=12 if self.is_rpi else 15,
            width=70 if self.is_rpi else 80,
            font=('DejaVu Sans Mono', 9) if self.is_rpi else ('Consolas', 10),
            wrap=tk.WORD,
            padx=10,
            pady=10,
            bg='#fafafa',
            relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(report_display, command=self.txt_reporte.yview)
        self.txt_reporte.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_reporte.pack(fill=tk.BOTH, expand=True)
        
        # Contenedor para el gráfico
        self.graph_frame = ttk.Frame(report_tab)
        self.graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def preprocess_image(self, img_path):
        """Preprocesamiento optimizado para OCR en RPi"""
        try:
            with Image.open(img_path) as img:
                # Reducir tamaño para RPi
                img.thumbnail((800, 800))
                
                # Convertir a escala de grises
                img = img.convert('L')
                
                # Mejorar contraste
                img = ImageOps.autocontrast(img, cutoff=3)
                
                # Binarización
                img = img.point(lambda x: 0 if x < 140 else 255)
                
                return img
        except Exception as e:
            logging.error(f"Error preprocesando imagen: {str(e)}")
            raise ValueError(f"No se pudo procesar la imagen: {str(e)}")
    
    def analizar_con_ocr(self, img_path):
        """Análisis OCR optimizado para RPi"""
        try:
            img = self.preprocess_image(img_path)
            
            # Configuración optimizada para facturas
            config = '--oem 1 --psm 6 -l spa+eng'  # OEM 1 es más rápido en RPi
            
            # Análisis con timeout para evitar bloqueos
            text = image_to_string(img, config=config, timeout=15)
            logging.info(f"Texto extraído por OCR:\n{text[:500]}...")  # Limitar log
            
            # Búsqueda optimizada del TOTAL
            lineas = text.split('\n')
            for linea in reversed(lineas[-10:]):  # Buscar en últimas líneas
                if "TOTAL" in linea.upper():
                    # Extraer valor numérico
                    nums = re.findall(r'[\d.,]+', linea.replace(' ', ''))
                    if nums:
                        try:
                            monto = float(nums[-1].replace('.', '').replace(',', '.'))
                            if 0.01 <= monto <= 1000000:
                                return round(monto, 2)
                        except ValueError:
                            continue
            
            # Fallback: Buscar número más grande
            nums = re.findall(r'[\d]{1,3}(?:[.,]\d{3})*[.,]\d{2}', text.replace(' ', ''))
            if nums:
                try:
                    montos = [float(n.replace('.', '').replace(',', '.')) for n in nums]
                    valid_montos = [m for m in montos if 0.01 <= m <= 1000000]
                    if valid_montos:
                        return round(max(valid_montos), 2)
                except ValueError:
                    pass
                    
            return None
        except Exception as e:
            logging.error(f"Error en OCR: {str(e)}")
            return None
    
    def analizar_con_api(self, img_path):
        """Método para análisis con API"""
        try:
            # Validación de archivo
            if not os.path.exists(img_path):
                raise FileNotFoundError("Archivo no encontrado")
            
            # Procesamiento de imagen
            with open(img_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')

            headers = {
                "Authorization": f"Bearer {self.API_KEY}",
                "Content-Type": "application/json"
            }

            prompt = """Extrae EXCLUSIVAMENTE el valor numérico del TOTAL de esta factura:
1. Busca específicamente "TOTAL" en mayúsculas
2. Ignora porcentajes como 1.0%, 2.5%, etc.
3. Devuelve solo el número con dos decimales
4. Ejemplo: Para "TOTAL 199.55 €" devuelve 199.55"""

            payload = {
                "model": "deepseek-vision",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }],
                "temperature": 0.1,
                "max_tokens": 30
            }

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                error_msg = f"Error API (Código: {response.status_code})"
                try:
                    error_detail = response.json().get('error', {}).get('message', '')
                    error_msg += f"\nDetalle: {error_detail}"
                except:
                    error_msg += "\nRespuesta no es JSON válido"
                raise ValueError(error_msg)

            contenido = response.json()
            monto_texto = contenido["choices"][0]["message"]["content"]
            return self.procesar_respuesta_api(monto_texto)

        except requests.exceptions.RequestException as e:
            logging.error(f"Error de conexión: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            raise
    
    def procesar_respuesta_api(self, texto):
        """Procesamiento de respuesta de API"""
        try:
            texto = texto.replace(',', '.').upper()
            
            patrones = [
                r'TOTAL[\s:]*([\d.,]+\d{2})',
                r'([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*€?$',
                r'IMPORTE[\s:]*([\d.,]+\d{2})',
                r'([\d]+[.,]\d{2})\s*$'
            ]
            
            for patron in patrones:
                match = re.search(patron, texto)
                if match:
                    monto_str = match.group(1).replace('.', '').replace(',', '.')
                    try:
                        monto = float(monto_str)
                        if 0.01 <= monto <= 1000000:
                            return monto
                    except ValueError:
                        continue
            
            # Fallback: Buscar el número más grande con decimales
            numeros = re.findall(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})', texto)
            if numeros:
                montos = []
                for num in numeros:
                    try:
                        monto = float(num.replace('.', '').replace(',', '.'))
                        if 0.01 <= monto <= 1000000:
                            montos.append(monto)
                    except ValueError:
                        continue
                if montos:
                    return max(montos)
                    
            return None
        except Exception as e:
            logging.error(f"Error procesando respuesta: {str(e)}")
            return None
    
    def cargar_documento(self):
        """Manejo de carga de documentos optimizado"""
        filetypes = [
            ("Imágenes", "*.jpg *.jpeg *.png"),
            ("Todos los archivos", "*.*")
        ]
        
        path = filedialog.askopenfilename(
            title="Seleccionar factura",
            filetypes=filetypes
        )
        
        if not path:
            return
            
        self.current_image = path
        self.btn_reintentar.config(state=tk.NORMAL)
        self.lbl_resultado.config(text="🔍 Analizando...", foreground="#4a6baf")
        self.root.update()
        
        try:
            # Vista previa optimizada
            if path.lower().endswith(('.jpg', '.jpeg', '.png')):
                with Image.open(path) as img:
                    img.thumbnail(self.img_preview_size)
                    img_tk = ImageTk.PhotoImage(img)
                    self.lbl_imagen.config(image=img_tk)
                    self.lbl_imagen.image = img_tk
            else:
                self.lbl_imagen.config(text="📄 Documento cargado")
            
            # En RPi, priorizar OCR local
            if self.is_rpi:
                monto = self.analizar_con_ocr(path)
                if monto is not None:
                    self.registrar_factura(path, monto)
                    return
            
            # Si no es RPi o falló OCR, intentar con API
            try:
                monto = self.analizar_con_api(path)
                if monto is not None:
                    self.registrar_factura(path, monto)
                    return
            except Exception as api_error:
                logging.warning(f"Fallo en API: {str(api_error)}")
                if not self.is_rpi:
                    self.lbl_resultado.config(text="⚠️ Fallo API, usando OCR...", foreground="orange")
                    self.root.update()
                    monto = self.analizar_con_ocr(path)
                    if monto is not None:
                        self.registrar_factura(path, monto)
                        return
            
            # Si todo falla, pedir manualmente
            self.solicitar_monto_manual(path)
                
        except Exception as e:
            logging.error(f"Error general: {str(e)}")
            messagebox.showerror(
                "Error",
                f"No se pudo procesar el documento:\n{str(e)}"
            )
            self.lbl_resultado.config(text="❌ Error al procesar", foreground="red")
    
    def solicitar_monto_manual(self, path):
        """Interfaz para entrada manual"""
        manual_window = tk.Toplevel(self.root)
        manual_window.title("Registro Manual")
        manual_window.geometry("400x400" if self.is_rpi else "500x500")
        
        main_frame = ttk.Frame(manual_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Vista previa
        if path.lower().endswith(('.jpg', '.jpeg', '.png')):
            with Image.open(path) as img:
                img.thumbnail((300, 300) if self.is_rpi else (400, 400))
                img_tk = ImageTk.PhotoImage(img)
                ttk.Label(main_frame, image=img_tk).pack(pady=5)
                manual_window.image = img_tk

        # Instrucciones
        ttk.Label(
            main_frame,
            text="Ingrese el monto TOTAL:",
            font=('Arial', self.font_size)
        ).pack(pady=5)

        # Validación de entrada
        def validar_entrada(texto):
            return re.match(r'^\d*[,.]?\d{0,2}$', texto) is not None

        val_cmd = (manual_window.register(validar_entrada), '%P')
        self.entry_monto = ttk.Entry(
            main_frame,
            validate="key",
            validatecommand=val_cmd,
            font=('Arial', 14),
            width=12
        )
        self.entry_monto.pack(pady=10)

        # Botones
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame,
            text="Cancelar",
            command=manual_window.destroy,
            width=10
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Registrar",
            command=lambda: self.procesar_monto_manual(path, manual_window),
            width=10
        ).pack(side=tk.LEFT)
    
    def procesar_monto_manual(self, path, ventana):
        """Procesamiento del monto manual"""
        monto_str = self.entry_monto.get()
        try:
            monto = float(monto_str.replace(',', '.'))
            if monto <= 0:
                raise ValueError("El monto debe ser positivo")
                
            self.blockchain.add_factura(path, monto)
            self.lbl_resultado.config(
                text=f"✏️ Total manual: {monto:.2f} €",
                foreground="#d32f2f"
            )
            ventana.destroy()
            messagebox.showinfo("Éxito", "Factura registrada manualmente")
        except ValueError as e:
            messagebox.showerror("Error", f"Monto no válido:\n{str(e)}")
    
    def registrar_factura(self, path, monto):
        """Registro de factura optimizado"""
        try:
            self.blockchain.add_factura(path, monto)
            self.lbl_resultado.config(
                text=f"✅ Total: {monto:.2f} €",
                foreground="#2e7d32"
            )
            messagebox.showinfo(
                "Éxito",
                f"Factura registrada:\n\nArchivo: {os.path.basename(path)}\nMonto: {monto:.2f} €"
            )
        except Exception as e:
            logging.error(f"Error registrando factura: {str(e)}")
            messagebox.showerror(
                "Error",
                f"No se pudo registrar:\n{str(e)}"
            )
            self.lbl_resultado.config(text="❌ Error al registrar", foreground="red")
    
    def reintentar_analisis(self):
        """Reintento de análisis"""
        if self.current_image:
            self.cargar_documento()
    
    def generar_reporte(self):
        """Generación de reporte optimizada con gráficos"""
        periodo = self.cbo_periodo.get().lower()
        datos = self.blockchain.generate_report(periodo)
        
        self.txt_reporte.config(state=tk.NORMAL)
        self.txt_reporte.delete(1.0, tk.END)
        
        # Encabezado
        self.txt_reporte.tag_configure("center", justify='center')
        self.txt_reporte.insert(tk.END, "═" * 60 + "\n", "center")
        self.txt_reporte.insert(tk.END, f" 📅 REPORTE {periodo.upper()} \n", "center")
        self.txt_reporte.insert(tk.END, "═" * 60 + "\n\n", "center")
        
        # Resumen
        self.txt_reporte.insert(tk.END, f" ▪ Período: {periodo.capitalize()}\n")
        self.txt_reporte.insert(tk.END, f" ▪ Facturas: {len(datos['facturas'])}\n")
        self.txt_reporte.insert(tk.END, f" ▪ Total: {datos['total']:,.2f} €\n\n")
        
        # Detalle
        if datos['facturas']:
            self.txt_reporte.insert(tk.END, " 📋 Detalle:\n")
            for factura in datos['facturas']:
                self.txt_reporte.insert(tk.END, 
                    f" • {factura['nombre_archivo'][:30]: <32} {factura['monto']: >8.2f} €\n")
        else:
            self.txt_reporte.insert(tk.END, " ℹ️ No hay facturas para este período\n")
        
        self.txt_reporte.insert(tk.END, "\n" + "═" * 60, "center")
        self.txt_reporte.config(state=tk.DISABLED)
        
        # Generar gráfico
        self.mostrar_grafico(datos)

    def mostrar_grafico(self, datos):
        """Generar y mostrar gráfico de pastel en la pestaña de reportes"""
        # Limpiar el contenedor del gráfico
        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        if not datos['facturas']:
            messagebox.showinfo("Sin datos", "No hay facturas para generar el gráfico.")
            return

        # Extraer datos para el gráfico
        nombres = [factura['nombre_archivo'] for factura in datos['facturas']]
        montos = [factura['monto'] for factura in datos['facturas']]

        # Crear figura de matplotlib
        fig = Figure(figsize=(6, 6), dpi=100)
        ax = fig.add_subplot(111)
        ax.pie(
            montos,
            labels=nombres,
            autopct='%1.1f%%',  # Mostrar porcentajes
            startangle=90,  # Rotar para que el primer segmento comience en la parte superior
            colors=plt.cm.Paired.colors  # Colores predefinidos
        )
        ax.set_title("Distribución de Facturación")

        # Incrustar el gráfico en tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    root = tk.Tk()
    
    # Configuración adicional para RPi
    if "arm" in platform.machine().lower():
        root.tk.call('tk', 'scaling', 1.5)  # Mejor escalado para pantallas pequeñas
        
    app = FacturacionApp(root)
    root.mainloop()