import hashlib
import json
import os
from datetime import datetime
from PIL import Image, UnidentifiedImageError

class Block:
    def __init__(self, index, timestamp, factura_data, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.factura_data = factura_data
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        """Hash optimizado para RPi"""
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
        return Block(0, datetime.now().isoformat(), 
                   {"nombre_archivo": "genesis", "monto": 0}, "0")

    def add_factura(self, imagen_path, monto):
        """Método optimizado para RPi"""
        try:
            # Verificación de imagen optimizada
            with Image.open(imagen_path) as img:
                img.verify()  # Verificación rápida
                img = Image.open(imagen_path)  # Reabrir para guardar
                
                # Guardar imagen optimizada
                img_name = os.path.basename(imagen_path)
                save_path = os.path.join(self.facturas_dir, img_name)
                
                if os.path.exists(save_path):
                    raise FileExistsError(f"Archivo '{img_name}' ya existe")
                
                # Guardar con calidad reducida para ahorrar espacio
                img.save(save_path, quality=85)

            # Crear bloque
            new_block = Block(
                index=len(self.chain),
                timestamp=datetime.now().isoformat(),
                factura_data={"nombre_archivo": img_name, "monto": monto},
                previous_hash=self.chain[-1].hash
            )
            self.chain.append(new_block)
            return new_block
            
        except (UnidentifiedImageError, FileNotFoundError) as e:
            raise ValueError("Archivo no es una imagen válida")
        except Exception as e:
            raise

    def generate_report(self, periodo="mensual"):
        """Generación de reportes optimizada"""
        reporte = {"total": 0, "facturas": []}
        hoy = datetime.now()

        for block in self.chain[1:]:  # Ignorar bloque génesis
            block_date = datetime.fromisoformat(block.timestamp)
            
            # Lógica de periodo optimizada
            if periodo == "semanal" and (hoy - block_date).days <= 7:
                reporte["facturas"].append(block.factura_data)
            elif periodo == "mensual" and block_date.month == hoy.month and block_date.year == hoy.year:
                reporte["facturas"].append(block.factura_data)
            elif periodo == "anual" and block_date.year == hoy.year:
                reporte["facturas"].append(block.factura_data)
            elif periodo == "completo":
                reporte["facturas"].append(block.factura_data)

        reporte["total"] = sum(f["monto"] for f in reporte["facturas"])
        return reporte