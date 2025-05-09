# blockchain.py - Versión optimizada para Raspberry Pi
import hashlib
import json
import os
from datetime import datetime
from PIL import Image, UnidentifiedImageError

class Block:
    def __init__(self, index, timestamp, factura_data, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.factura_data = factura_data  # { "nombre_archivo": "factura1.jpg", "monto": 150.50 }
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        # Versión optimizada para RPi con cálculo de hash más eficiente
        block_data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "factura": self.factura_data,
            "previous_hash": self.previous_hash
        }
        block_string = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.facturas_dir = "facturas/"
        os.makedirs(self.facturas_dir, exist_ok=True)

    def create_genesis_block(self):
        return Block(0, datetime.now().isoformat(), {"nombre_archivo": "genesis", "monto": 0}, "0")

    def add_factura(self, imagen_path, monto):
        # Validar si el archivo es una imagen válida
        try:
            img = Image.open(imagen_path)
            img.verify()  # Verifica si es una imagen válida
        except (UnidentifiedImageError, FileNotFoundError):
            raise ValueError("El archivo proporcionado no es una imagen válida o no existe.")

        # Guardar imagen en carpeta
        img_name = os.path.basename(imagen_path)
        save_path = os.path.join(self.facturas_dir, img_name)

        # Renombrar automáticamente si el archivo ya existe
        base_name, ext = os.path.splitext(img_name)
        counter = 1
        while os.path.exists(save_path):
            save_path = os.path.join(self.facturas_dir, f"{base_name}_{counter}{ext}")
            counter += 1

        try:
            img = Image.open(imagen_path)  # Reabrir para guardar
            img.thumbnail((800, 800))  # Reducir tamaño para ahorrar espacio
            img.save(save_path, optimize=True, quality=85)
        except Exception as e:
            raise ValueError(f"No se pudo guardar la imagen: {str(e)}")

        # Crear bloque
        new_block = Block(
            index=len(self.chain),
            timestamp=datetime.now().isoformat(),
            factura_data={"nombre_archivo": os.path.basename(save_path), "monto": monto},
            previous_hash=self.chain[-1].hash
        )
        self.chain.append(new_block)
        return new_block

    def generate_report(self, periodo="mensual"):
        # Versión optimizada para reducir carga de CPU
        reporte = {"total": 0.0, "facturas": []}
        hoy = datetime.now()

        for block in self.chain[1:]:  # Ignorar bloque génesis
            try:
                block_date = datetime.fromisoformat(block.timestamp)
                include = False

                if periodo == "semanal" and (hoy - block_date).days <= 7:
                    include = True
                elif periodo == "mensual" and block_date.month == hoy.month and block_date.year == hoy.year:
                    include = True
                elif periodo == "anual" and block_date.year == hoy.year:
                    include = True
                elif periodo == "completo":
                    include = True

                if include:
                    reporte["facturas"].append(block.factura_data)
            except Exception:
                continue  # Si hay error con un bloque, continuar con el siguiente

        # Cálculo total optimizado
        reporte["total"] = round(sum(f.get("monto", 0) for f in reporte["facturas"]), 2)
        return reporte