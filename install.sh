#!/bin/bash

# Actualizar el sistema
sudo apt update
sudo apt full-upgrade -y

# Instalar dependencias esenciales
sudo apt install -y \
    python3 \
    python3-pip \
    python3-tk \
    python3-pil.imagetk \
    tesseract-ocr \
    tesseract-ocr-spa \
    libjpeg-dev \
    zlib1g-dev

# Instalar paquetes Python con pip
pip3 install --upgrade pip
pip3 install pytesseract requests pillow

# Configurar entorno (opcional para entornos virtuales)
python3 -m venv --system-site-packages venv
source venv/bin/activate

# Verificar instalación de Tkinter
python3 -c "import tkinter; print('>>> Tkinter está correctamente instalado')" || echo "Error: Tkinter no funciona"

# Clonar tu repositorio (opcional)
# git clone https://github.com/tu-usuario/tu-repositorio.git
# cd tu-repositorio

echo "¡Instalación completada! Ejecuta tu app con: python3 app.py"