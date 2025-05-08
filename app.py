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

class FacturacionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🧾 Facturación Inteligente v7.0")
        self.root.geometry("1100x850")
        
        # Configuración de logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='facturacion.log'
        )
        
        # Configuración mejorada de OCR
        self.setup_ocr()
        
        # Configuración de API
        self.API_URL = "https://api.deepseek.com/v1/chat/completions"
        self.API_KEY = "sk-5397f99b3feb44c9a51ec8a079f1b5a0"
        if not self.API_KEY:
            self.root.destroy()
            return
            
        self.blockchain = Blockchain()
        self.current_image = None
        self.setup_ui()

    def setup_ocr(self):
        """Configuración robusta de Tesseract OCR"""
        try:
            # Detección automática de rutas
            possible_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                '/usr/bin/tesseract',
                '/usr/local/bin/tesseract'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    os.environ['TESSDATA_PREFIX'] = os.path.join(os.path.dirname(path), 'tessdata')
                    break
            
            # Verificación de idiomas instalados
            if not os.path.exists(os.path.join(os.environ.get('TESSDATA_PREFIX', ''), 'spa.traineddata')):
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

    def obtener_api_key(self):
        """Obtención segura de API key con validación"""
        for intento in range(3):
            api_key = simpledialog.askstring(
                "Configuración API",
                f"Ingrese su API Key de DeepSeek (Intento {intento + 1}/3):",
                parent=self.root,
                show='*'
            )
            if api_key and len(api_key) > 30:
                if self.validar_api_key(api_key):
                    return api_key
                else:
                    messagebox.showerror("Error", "API Key no válida o sin permisos")
        messagebox.showerror("Error", "No se proporcionó una API Key válida")
        return None

    def validar_api_key(self, api_key):
        """Validación de la API Key"""
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(
                "https://api.deepseek.com/v1/models",
                headers=headers,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error validando API Key: {str(e)}")
            return False

    def analizar_con_api(self, img_path):
        """Método robusto para análisis con API"""
        try:
            # Validación de archivo
            if not os.path.exists(img_path):
                raise FileNotFoundError("Archivo no encontrado")
            
            # Procesamiento de imagen
            with open(img_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')

            headers = {
                "Authorization": f"Bearer {self.API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json"
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
                "max_tokens": 30,
                "top_p": 0.9
            }

            logging.info("Enviando solicitud a la API...")
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=60
            )

            # Manejo especial de errores HTTP
            if response.status_code != 200:
                error_msg = f"Error en API (Código: {response.status_code})"
                try:
                    error_detail = response.json().get('error', {}).get('message', '')
                    error_msg += f"\nDetalle: {error_detail}"
                except json.JSONDecodeError:
                    error_msg += "\nRespuesta no es JSON válido"
                raise ValueError(error_msg)

            # Validación de respuesta JSON
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
        """Procesamiento avanzado de respuesta de API"""
        try:
            # Limpieza de texto
            texto = texto.replace(',', '.').upper()
            
            # Patrones para identificar TOTAL
            patrones = [
                r'TOTAL[\s:]*([\d.,]+\d{2})',  # Para "TOTAL: 199.55"
                r'([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*€?$',  # Para "199.55 €"
                r'IMPORTE[\s:]*([\d.,]+\d{2})',  # Para "IMPORTE: 199.55"
                r'([\d]+[.,]\d{2})\s*$'  # Para "199.55" al final
            ]
            
            for patron in patrones:
                match = re.search(patron, texto)
                if match:
                    monto_str = match.group(1).replace('.', '').replace(',', '.')
                    try:
                        monto = float(monto_str)
                        if 0.01 <= monto <= 1000000:  # Validación de rango
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

    def analizar_con_ocr(self, img_path):
        """Método de respaldo con OCR mejorado"""
        try:
            # Preprocesamiento de imagen
            img = Image.open(img_path)
            
            # Convertir a escala de grises y aumentar contraste
            img = img.convert('L')
            img = img.point(lambda x: 0 if x < 140 else 255)
            
            # Configuración para facturas en español
            custom_config = r'--oem 3 --psm 6 -l spa+eng'
            
            # Análisis OCR
            text = image_to_string(img, config=custom_config)
            logging.info(f"Texto extraído por OCR:\n{text}")
            
            # Búsqueda inteligente del TOTAL
            lineas = text.split('\n')
            for linea in reversed(lineas):  # Buscar desde el final
                if "TOTAL" in linea.upper():
                    # Extraer el valor numérico
                    match = re.search(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})', linea)
                    if match:
                        try:
                            monto_str = match.group(1).replace('.', '').replace(',', '.')
                            monto = float(monto_str)
                            if 0.01 <= monto <= 1000000:
                                return monto
                        except ValueError:
                            continue
            
            # Fallback: Buscar el número más grande que parezca un total
            numeros = re.findall(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})', text)
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
            logging.error(f"Error en análisis OCR: {str(e)}")
            return None

    def setup_ui(self):
        """Configuración de interfaz gráfica"""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f7fa")
        style.configure("TButton", font=("Arial", 10), padding=8, background="#5b7bb4", foreground="white")
        style.map("TButton", background=[("active", "#46649b")])

        # Frame principal
        main_frame = ttk.Frame(self.root, padding=(20, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            title_frame,
            text="🏷️ Sistema de Facturación Inteligente",
            font=("Arial", 20, "bold"),
            background="#f5f7fa"
        ).pack()

        # Notebook (pestañas)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Pestaña de Subir Factura
        upload_tab = ttk.Frame(notebook)
        notebook.add(upload_tab, text="📤 Subir Factura")

        # Panel de control
        control_frame = ttk.Frame(upload_tab)
        control_frame.pack(pady=15, fill=tk.X)

        ttk.Button(
            control_frame,
            text="Seleccionar Factura",
            command=self.cargar_documento,
            width=20
        ).pack(side=tk.LEFT, padx=5)

        self.btn_reintentar = ttk.Button(
            control_frame,
            text="Reanalizar",
            command=self.reintentar_analisis,
            state=tk.DISABLED,
            width=15
        )
        self.btn_reintentar.pack(side=tk.LEFT)

        # Área de visualización
        display_frame = ttk.Frame(upload_tab)
        display_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.lbl_imagen = ttk.Label(display_frame)
        self.lbl_imagen.pack()

        self.lbl_resultado = ttk.Label(
            display_frame,
            text="Monto detectado: -",
            font=("Arial", 14, "bold"),
            foreground="#333",
            background="#f5f7fa"
        )
        self.lbl_resultado.pack(pady=15)

        # Pestaña de Reportes
        report_tab = ttk.Frame(notebook)
        notebook.add(report_tab, text="📊 Reportes")

        # Controles de reporte
        report_control = ttk.Frame(report_tab)
        report_control.pack(pady=15)

        ttk.Label(
            report_control,
            text="Periodo:",
            font=("Arial", 11)
        ).pack(side=tk.LEFT, padx=5)

        self.cbo_periodo = ttk.Combobox(
            report_control,
            values=["Semanal", "Mensual", "Anual", "Completo"],
            state="readonly",
            width=12
        )
        self.cbo_periodo.current(1)
        self.cbo_periodo.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            report_control,
            text="Generar",
            command=self.generar_reporte,
            width=10
        ).pack(side=tk.LEFT, padx=10)

        # Área de reporte
        report_display = ttk.Frame(report_tab)
        report_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.txt_reporte = tk.Text(
            report_display,
            height=18,
            width=90,
            font=("Consolas", 10),
            wrap=tk.WORD,
            padx=15,
            pady=15,
            bg="#fafafa",
            relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(report_display, command=self.txt_reporte.yview)
        self.txt_reporte.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_reporte.pack(fill=tk.BOTH, expand=True)

    def cargar_documento(self):
        """Manejo de carga de documentos con retroalimentación"""
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
        self.lbl_resultado.config(text="🔍 Analizando...", foreground="#5b7bb4")
        self.root.update()

        try:
            # Vista previa para imágenes
            if path.lower().endswith(('.jpg', '.jpeg', '.png')):
                img = Image.open(path)
                img.thumbnail((450, 450))
                img_tk = ImageTk.PhotoImage(img)
                self.lbl_imagen.config(image=img_tk)
                self.lbl_imagen.image = img_tk
            else:
                self.lbl_imagen.config(text="📄 Documento cargado (vista previa no disponible)")

            # Primero intentar con API
            try:
                monto = self.analizar_con_api(path)
                if monto is not None:
                    self.registrar_factura(path, monto)
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
                f"No se pudo procesar el documento:\n{str(e)}\n\n"
                "Consulte el archivo facturacion.log para más detalles."
            )

    def registrar_factura(self, path, monto):
        """Registro de factura con manejo de errores"""
        try:
            self.blockchain.add_factura(path, monto)
            self.lbl_resultado.config(
                text=f"✅ Total registrado: {monto:.2f} €",
                foreground="#2e7d32"
            )
            messagebox.showinfo(
                "Éxito",
                f"Factura registrada correctamente:\n\n"
                f"Archivo: {os.path.basename(path)}\n"
                f"Monto: {monto:.2f} €"
            )
        except Exception as e:
            logging.error(f"Error registrando factura: {str(e)}")
            messagebox.showerror(
                "Error",
                f"No se pudo registrar la factura:\n{str(e)}"
            )

    def solicitar_monto_manual(self, path):
        """Interfaz para entrada manual mejorada"""
        manual_window = tk.Toplevel(self.root)
        manual_window.title("Registro Manual")
        manual_window.geometry("500x500")
        
        # Frame principal
        main_frame = ttk.Frame(manual_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Vista previa
        if path.lower().endswith(('.jpg', '.jpeg', '.png')):
            img = Image.open(path)
            img.thumbnail((300, 300))
            img_tk = ImageTk.PhotoImage(img)
            ttk.Label(main_frame, image=img_tk).pack(pady=10)
            manual_window.image = img_tk

        # Instrucciones
        ttk.Label(
            main_frame,
            text="Ingrese el monto TOTAL del recibo:",
            font=("Arial", 11)
        ).pack(pady=(10, 5))

        # Validación de entrada
        def validar_entrada(texto):
            return re.match(r'^\d*[,.]?\d{0,2}$', texto) is not None

        val_cmd = (manual_window.register(validar_entrada), '%P')
        self.entry_monto = ttk.Entry(
            main_frame,
            validate="key",
            validatecommand=val_cmd,
            font=("Arial", 14),
            width=15
        )
        self.entry_monto.pack(pady=10)

        # Botones
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)

        ttk.Button(
            btn_frame,
            text="Cancelar",
            command=manual_window.destroy
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(
            btn_frame,
            text="Registrar",
            command=lambda: self.procesar_monto_manual(path, manual_window),
            style="Accent.TButton"
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

    def reintentar_analisis(self):
        """Reintento de análisis"""
        if self.current_image:
            self.cargar_documento()

    def generar_reporte(self):
        """Generación de reportes"""
        periodo = self.cbo_periodo.get().lower()
        datos = self.blockchain.generate_report(periodo)

        self.txt_reporte.config(state=tk.NORMAL)
        self.txt_reporte.delete(1.0, tk.END)
        
        # Encabezado
        self.txt_reporte.tag_configure("center", justify='center')
        self.txt_reporte.insert(tk.END, "═"*80 + "\n", "center")
        self.txt_reporte.insert(tk.END, f" 📅 REPORTE {periodo.upper()} \n", "center")
        self.txt_reporte.insert(tk.END, "═"*80 + "\n\n", "center")
        
        # Resumen
        self.txt_reporte.insert(tk.END, f" ▪ Período: {periodo.capitalize()}\n")
        self.txt_reporte.insert(tk.END, f" ▪ Facturas procesadas: {len(datos['facturas'])}\n")
        self.txt_reporte.insert(tk.END, f" ▪ Total facturado: {datos['total']:,.2f} €\n\n")
        
        # Detalle
        if datos['facturas']:
            self.txt_reporte.insert(tk.END, " 📋 Detalle de Facturas:\n")
            for factura in datos['facturas']:
                self.txt_reporte.insert(tk.END, 
                    f"    • {factura['nombre_archivo']: <40} {factura['monto']: >10.2f} €\n")
        else:
            self.txt_reporte.insert(tk.END, " ℹ️ No se encontraron facturas para este período\n")
        
        self.txt_reporte.insert(tk.END, "\n" + "═"*80, "center")
        self.txt_reporte.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = FacturacionApp(root)
    root.mainloop()