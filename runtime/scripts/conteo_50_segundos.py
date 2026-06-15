import time

for i in range(1, 51):
    progress = int((i / 50) * 100)
    print(f"PYFLOW_PROGRESS={progress}", flush=True)
    print(f"[INFO] Paso {i} de 50", flush=True)
    time.sleep(1)