# PyFlow Manager — Angular v17

Réplica completa del dashboard PyFlow Manager en Angular 17 con Standalone Components, Signals, Tailwind CSS y Chart.js.

## 🚀 Instalación y arranque

```bash
# 1. Instalar dependencias
npm install

# 2. Iniciar servidor de desarrollo
npm start
# → Abre http://localhost:4200
```

## 🏗️ Estructura del proyecto

```
src/app/
├── app.component.ts          # Layout raíz (header + sidebar + main)
├── app.config.ts             # Config standalone (router, animations)
├── models/
│   └── models.ts             # Interfaces: Script, Execution, Schedule, Toast
├── services/
│   └── pyflow.service.ts     # Estado global con Angular Signals + mock data
└── components/
    ├── header/               # Header superior con búsqueda y usuario
    ├── sidebar/              # Sidebar de navegación
    ├── dashboard/            # KPIs + Chart.js + tabla de ejecuciones
    ├── scripts/              # Tabla de scripts con filtros
    ├── script-detail/        # Detalle de script + consola simulada
    ├── schedules/            # Formulario de programación + cronograma
    ├── logs/                 # Historial filtrable + exportación .txt
    ├── settings/             # Rutas, variables globales, alertas, reintentos
    ├── import-modal/         # Modal para importar nuevos scripts
    └── toast/                # Notificaciones toast
```

## ✨ Tecnologías usadas

| Tecnología | Versión | Uso |
|---|---|---|
| Angular | 17 | Framework principal |
| Angular Signals | 17 | Estado reactivo sin NgRx |
| Tailwind CSS | 3.x | Estilos utilitarios |
| Chart.js | 4.x | Gráfico de ejecuciones históricas |
| Lucide (SVGs inline) | — | Iconografía |

## 🎯 Funcionalidades implementadas

- ✅ Dashboard con KPIs, gráfico de barras y tabla de ejecuciones recientes
- ✅ Listado de scripts con filtros por nombre, categoría y estado
- ✅ Detalle del script con consola simulada en tiempo real
- ✅ Barra de progreso animada durante la ejecución
- ✅ Programaciones CRON con formulario y tabla de cronogramas activos
- ✅ Logs e histórico con filtros por script, estado y usuario
- ✅ Exportación del historial como archivo `.txt`
- ✅ Configuración global: rutas, variables de entorno, alertas SMTP/Webhook, reintentos
- ✅ Modal de importación de scripts
- ✅ Sistema de toasts para notificaciones
- ✅ Diseño oscuro fiel al original (slate-900/950)
