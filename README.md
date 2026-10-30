# Laboratorio-2-Implementacion
agenda de contactos almacenada en un archivo de tamaño fijo con interfaz grafica y exportación de datos a un JSON y PDF
Universidad Rafael Landívar — Ingeniería en Informática y Sistemas

## Ejecutar
```bash
sudo apt-get install python3-tk   
pip install fpdf2
cd src && python3 app.py
```

## Registro de tamaño fijo = 100 bytes
id(6) | nombre(30) | teléfono(15) | correo(30) | ciudad(18) | "\n"(1)

## Archivos
- `src/contact_store.py` registros, seek/tell, índice, SHA-256, ZIP, metadatos
- `src/exporter.py` JSON y reporte PDF 
- `src/app.py` GUI y reutilizacion del primer lab
- `data/` contactos.dat, indice.json, contactos.sha256
- `exports/` JSON exportado, reporte PDF
- `Documento_Laboratorio2.docx` documento de sustentación

