import time
from datetime import datetime

print("Iniciando script de prueba PyFlow...")
for i in range(1, 6):
    print(f"Procesando lote {i}/5 - {datetime.now().strftime('%H:%M:%S')}")
    time.sleep(1)

print("Script finalizado correctamente.")
