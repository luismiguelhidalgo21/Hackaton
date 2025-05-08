# blockchain.py (sin cambios)
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
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "factura": self.factura_data,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
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

        if os.path.exists(save_path):
            raise FileExistsError(f"El archivo '{img_name}' ya existe en el directorio de facturas.")

        img = Image.open(imagen_path)  # Reabrir para guardar
        img.save(save_path)

        # Crear bloque
        new_block = Block(
            index=len(self.chain),
            timestamp=datetime.now().isoformat(),
            factura_data={"nombre_archivo": img_name, "monto": monto},
            previous_hash=self.chain[-1].hash
        )
        self.chain.append(new_block)
        return new_block

    def generate_report(self, periodo="mensual"):
        reporte = {"total": 0, "facturas": []}
        hoy = datetime.now()

        for block in self.chain[1:]:  # Ignorar bloque génesis
            block_date = datetime.fromisoformat(block.timestamp)  # Convertir de string a datetime
            if periodo == "semanal" and (hoy - block_date).days <= 7:
                reporte["facturas"].append(block.factura_data)
            elif periodo == "mensual" and block_date.month == hoy.month and block_date.year == hoy.year:
                reporte["facturas"].append(block.factura_data)
            elif periodo == "anual" and block_date.year == hoy.year:
                reporte["facturas"].append(block.factura_data)

        reporte["total"] = sum(f["monto"] for f in reporte["facturas"])
        return reporte