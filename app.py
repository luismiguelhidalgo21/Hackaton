import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import requests
import base64
import re
import json
from PIL import Image, ImageTk
from blockchain import Blockchain
import pytesseract
from pytesseract import image_to_string
import logging
import threading
import time

class FacturacionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🧾 Facturación Inteligente v7.0 (RPi)")
        self.root.geometry("800x600")
        
        # Configuración de logging optimizada
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='facturacion.log',
            filemode='a'
        )
        
        # Configuración mejorada de OCR para RPi
        self.setup_ocr()
        
        # Configuración de API
        self.API_URL = "https://api.deepseek.com/v1/chat/completions"
        self.API_KEY = "sk-5397f99b3feb44c9a51ec8a079f1b5a0"
        if not self.API_KEY:
            self.root.destroy()
            return
            
        self.blockchain = Blockchain()
        self.current_image = None
        self.processing = False
        self.setup_ui()

    def setup_ocr(self):
        """Configuración optimizada de Tesseract OCR para RPi"""
        try:
            # Ruta específica para Raspberry Pi
            pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
            os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'
            
            # Verificar si el idioma español está instalado
            if not os.path.exists('/usr/share/tesseract-ocr/4.00/tessdata/spa.traineddata'):
                logging.warning("Datos de idioma español no encontrados")
                messagebox.showwarning(
                    "Configuración OCR",
                    "Datos de idioma español no encontrados. Se usará inglés por defecto."
                )
        except Exception as e:
            logging.error(f"Error configurando OCR: {str(e)}")
            messagebox.showerror(
                "Error OCR",
                f"No se pudo configurar Tesseract OCR:\n{str(e)}\n\n"
                "El análisis de imágenes estará limitado."
            )

    def analizar_con_api(self, img_path):
        """Método optimizado para RPi con manejo de tiempo de espera"""
        try:
            # Reducir tamaño de imagen antes de enviar
            with Image.open(img_path) as img:
                img.thumbnail((800, 800))  # Reducir tamaño para API
                temp_path = "/tmp/temp_img.jpg"
                img.save(temp_path, "JPEG", quality=85)
            
            with open(temp_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Eliminar archivo temporal
            os.remove(temp_path)

            headers = {
                "Authorization": f"Bearer {self.API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            payload = {
                "model": "deepseek-vision",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extrae el valor numérico del TOTAL de esta factura"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}",
                                "detail": "low"  # Reducir detalle para ahorrar ancho de banda
                            }
                        }
                    ]
                }],
                "temperature": 0.1,
                "max_tokens": 30,
                "top_p": 0.9
            }

            # Timeout más corto para RPi
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=30  # Reducido de 60 a 30 segundos
            )

            if response.status_code != 200:
                error_msg = f"Error en API (Código: {response.status_code})"
                try:
                    error_detail = response.json().get('error', {}).get('message', '')
                    error_msg += f"\nDetalle: {error_detail}"
                except json.JSONDecodeError:
                    error_msg += "\nRespuesta no es JSON válido"
                raise ValueError(error_msg)

            try:
                contenido = response.json()
                monto_texto = contenido["choices"][0]["message"]["content"]
                return self.procesar_respuesta_api(monto_texto)
            except (KeyError, json.JSONDecodeError) as e:
                logging.error(f"Error procesando respuesta API: {str(e)}")
                raise ValueError("La API devolvió una respuesta no válida")

        except requests.exceptions.RequestException as e:
            logging.error(f"Error de conexión: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            raise

    def procesar_respuesta_api(self, texto):
        """Procesamiento optimizado de respuesta de API"""
        try:
            texto = texto.replace(',', '.').upper()
            
            # Patrones simplificados para reducir carga de CPU
            patrones = [
                r'TOTAL[\s:]*([\d.,]+\d{2})',
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
            
            return None
        except Exception as e:
            logging.error(f"Error procesando respuesta: {str(e)}")
            return None

    def analizar_con_ocr(self, img_path):
        """OCR optimizado para RPi con preprocesamiento ligero"""
        try:
            # Preprocesamiento optimizado para RPi
            with Image.open(img_path) as img:
                # Convertir a escala de grises y ajustar tamaño
                img = img.convert('L')
                img = img.resize((800, 800), Image.LANCZOS)  # Reducir tamaño para OCR
                
                # Aumentar contraste con método más ligero
                img = img.point(lambda x: 0 if x < 128 else 255)
            
                # Configuración para facturas en español (más ligera)
                custom_config = r'--oem 1 --psm 6 -l spa'  # OEM 1 es más rápido que 3
            
                # Análisis OCR
                text = image_to_string(img, config=custom_config)
                logging.info(f"Texto extraído por OCR:\n{text}")
                
                # Búsqueda simplificada del TOTAL
                lineas = text.split('\n')
                for linea in reversed(lineas):
                    if "TOTAL" in linea.upper():
                        match = re.search(r'(\d+[.,]\d{2})', linea)
                        if match:
                            try:
                                monto_str = match.group(1).replace('.', '').replace(',', '.')
                                monto = float(monto_str)
                                if 0.01 <= monto <= 1000000:
                                    return monto
                            except ValueError:
                                continue
                
                return None
        except Exception as e:
            logging.error(f"Error en análisis OCR: {str(e)}")
            return None

    def setup_ui(self):
        """Interfaz optimizada para RPi"""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Arial", 10))
        style.configure("TFrame", background="#f5f7fa")
        style.configure("TButton", padding=6, background="#5b7bb4", foreground="white")
        style.map("TButton", background=[("active", "#46649b")])

        # Frame principal
        main_frame = ttk.Frame(self.root, padding=(10, 5))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            title_frame,
            text="🏷️ Facturación Inteligente",
            font=("Arial", 16, "bold"),
            background="#f5f7fa"
        ).pack()

        # Notebook (pestañas)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Pestaña de Subir Factura
        upload_tab = ttk.Frame(notebook)
        notebook.add(upload_tab, text="📤 Subir Factura")

        # Panel de control simplificado
        control_frame = ttk.Frame(upload_tab)
        control_frame.pack(pady=10, fill=tk.X)

        ttk.Button(
            control_frame,
            text="Seleccionar Factura",
            command=self.cargar_documento_thread,
            width=18
        ).pack(side=tk.LEFT, padx=5)

        self.btn_reintentar = ttk.Button(
            control_frame,
            text="Reanalizar",
            command=self.reintentar_analisis,
            state=tk.DISABLED,
            width=12
        )
        self.btn_reintentar.pack(side=tk.LEFT)

        # Área de visualización optimizada
        display_frame = ttk.Frame(upload_tab)
        display_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.lbl_imagen = ttk.Label(display_frame)
        self.lbl_imagen.pack()

        self.lbl_resultado = ttk.Label(
            display_frame,
            text="Monto detectado: -",
            font=("Arial", 12),
            foreground="#333",
            background="#f5f7fa"
        )
        self.lbl_resultado.pack(pady=10)

        # Pestaña de Reportes optimizada
        report_tab = ttk.Frame(notebook)
        notebook.add(report_tab, text="📊 Reportes")

        # Controles de reporte
        report_control = ttk.Frame(report_tab)
        report_control.pack(pady=10)

        ttk.Label(
            report_control,
            text="Periodo:",
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=5)

        self.cbo_periodo = ttk.Combobox(
            report_control,
            values=["Semanal", "Mensual", "Anual", "Completo"],
            state="readonly",
            width=10
        )
        self.cbo_periodo.current(1)
        self.cbo_periodo.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            report_control,
            text="Generar",
            command=self.generar_reporte,
            width=8
        ).pack(side=tk.LEFT, padx=5)

        # Área de reporte optimizada
        report_display = ttk.Frame(report_tab)
        report_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.txt_reporte = tk.Text(
            report_display,
            height=12,
            width=70,
            font=("Consolas", 9),
            wrap=tk.WORD,
            padx=10,
            pady=10,
            bg="#fafafa"
        )
        scrollbar = ttk.Scrollbar(report_display, command=self.txt_reporte.yview)
        self.txt_reporte.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_reporte.pack(fill=tk.BOTH, expand=True)

    def cargar_documento_thread(self):
        """Manejo de carga en segundo plano para no bloquear la UI"""
        if self.processing:
            return
            
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

        self.processing = True
        self.current_image = path
        self.btn_reintentar.config(state=tk.NORMAL)
        self.lbl_resultado.config(text="🔍 Analizando...", foreground="#5b7bb4")
        self.root.update()

        # Usar un hilo para no bloquear la interfaz
        threading.Thread(target=self.procesar_documento, args=(path,), daemon=True).start()

    def procesar_documento(self, path):
        """Procesamiento del documento en segundo plano"""
        try:
            # Vista previa optimizada para RPi
            if path.lower().endswith(('.jpg', '.jpeg', '.png')):
                img = Image.open(path)
                img.thumbnail((400, 400))  # Tamaño más pequeño para RPi
                img_tk = ImageTk.PhotoImage(img)
                self.lbl_imagen.config(image=img_tk)
                self.lbl_imagen.image = img_tk
            else:
                self.lbl_imagen.config(text="📄 Documento cargado")

            # Primero intentar con API
            try:
                monto = self.analizar_con_api(path)
                if monto is not None:
                    self.registrar_factura(path, monto)
                    self.processing = False
                    return
            except Exception as api_error:
                logging.warning(f"Fallo en API: {str(api_error)}")
                self.lbl_resultado.config(text="⚠️ Fallo en API, usando OCR...", foreground="orange")
                self.root.update()

            # Si falla API, intentar con OCR
            try:
                monto = self.analizar_con_ocr(path)
                if monto is not None:
                    self.registrar_factura(path, monto)
                    self.processing = False
                    return
            except Exception as ocr_error:
                logging.warning(f"Fallo en OCR: {str(ocr_error)}")
                self.lbl_resultado.config(text="⚠️ Fallo en OCR", foreground="red")
                self.root.update()

            # Si ambos métodos fallan, pedir entrada manual
            self.solicitar_monto_manual(path)
                
        except Exception as e:
            logging.error(f"Error general: {str(e)}")
            messagebox.showerror(
                "Error",
                f"No se pudo procesar el documento:\n{str(e)}"
            )
        finally:
            self.processing = False

    def registrar_factura(self, path, monto):
        """Registro de factura optimizado"""
        try:
            self.blockchain.add_factura(path, monto)
            self.lbl_resultado.config(
                text=f"✅ Total: {monto:.2f} €",
                foreground="#2e7d32"
            )
        except Exception as e:
            logging.error(f"Error registrando factura: {str(e)}")
            messagebox.showerror(
                "Error",
                f"No se pudo registrar la factura:\n{str(e)}"
            )

    def solicitar_monto_manual(self, path):
        """Interfaz manual optimizada"""
        manual_window = tk.Toplevel(self.root)
        manual_window.title("Registro Manual")
        manual_window.geometry("400x400")  # Ventana más pequeña
        
        # Frame principal
        main_frame = ttk.Frame(manual_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Vista previa optimizada
        if path.lower().endswith(('.jpg', '.jpeg', '.png')):
            img = Image.open(path)
            img.thumbnail((300, 300))
            img_tk = ImageTk.PhotoImage(img)
            ttk.Label(main_frame, image=img_tk).pack(pady=5)
            manual_window.image = img_tk

        # Instrucciones
        ttk.Label(
            main_frame,
            text="Ingrese el monto TOTAL:",
            font=("Arial", 10)
        ).pack(pady=(5, 2))

        # Validación de entrada
        def validar_entrada(texto):
            return re.match(r'^\d*[,.]?\d{0,2}$', texto) is not None

        val_cmd = (manual_window.register(validar_entrada), '%P')
        self.entry_monto = ttk.Entry(
            main_frame,
            validate="key",
            validatecommand=val_cmd,
            font=("Arial", 12),
            width=12
        )
        self.entry_monto.pack(pady=5)

        # Botones
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame,
            text="Cancelar",
            command=manual_window.destroy
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Registrar",
            command=lambda: self.procesar_monto_manual(path, manual_window)
        ).pack(side=tk.LEFT)

    def procesar_monto_manual(self, path, ventana):
        """Procesamiento manual optimizado"""
        monto_str = self.entry_monto.get()
        try:
            monto = float(monto_str.replace(',', '.'))
            if monto <= 0:
                raise ValueError("El monto debe ser positivo")
                
            self.blockchain.add_factura(path, monto)
            self.lbl_resultado.config(
                text=f"✏️ Total: {monto:.2f} €",
                foreground="#d32f2f"
            )
            ventana.destroy()
        except ValueError as e:
            messagebox.showerror("Error", f"Monto no válido:\n{str(e)}")

    def reintentar_analisis(self):
        """Reintento de análisis optimizado"""
        if self.current_image and not self.processing:
            self.cargar_documento_thread()

    def generar_reporte(self):
        """Generación de reportes optimizada"""
        periodo = self.cbo_periodo.get().lower()
        datos = self.blockchain.generate_report(periodo)

        self.txt_reporte.config(state=tk.NORMAL)
        self.txt_reporte.delete(1.0, tk.END)
        
        # Encabezado simplificado
        self.txt_reporte.tag_configure("center", justify='center')
        self.txt_reporte.insert(tk.END, f"📅 REPORTE {periodo.upper()}\n", "center")
        self.txt_reporte.insert(tk.END, "═"*50 + "\n\n", "center")
        
        # Resumen optimizado
        self.txt_reporte.insert(tk.END, f"▪ Período: {periodo.capitalize()}\n")
        self.txt_reporte.insert(tk.END, f"▪ Facturas: {len(datos['facturas'])}\n")
        self.txt_reporte.insert(tk.END, f"▪ Total: {datos['total']:,.2f} €\n\n")
        
        # Detalle optimizado
        if datos['facturas']:
            for factura in datos['facturas']:
                self.txt_reporte.insert(tk.END, 
                    f"• {factura['nombre_archivo'][:30]: <32} {factura['monto']: >8.2f} €\n")
        else:
            self.txt_reporte.insert(tk.END, "ℹ️ No hay facturas\n")
        
        self.txt_reporte.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = FacturacionApp(root)
    root.mainloop()