window.PYFLOW_MANUAL_DATA = {
  "settings": [
    {
      "id": "16",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "EMAIL_ENABLED",
      "setting_value": "true",
      "setting_type": "string",
      "category": "general",
      "description": "Habilitar envío de correos PROD",
      "is_critical": "0",
      "display_value": "true",
      "manual_description": "Habilitar envío de correos DEV",
      "doc": {
        "title": "Envío de correos habilitado",
        "category": "Correo",
        "desc": "Activa o desactiva funcionalidades que envían correos en el ambiente seleccionado. Útil para evitar envíos reales en desarrollo o QA."
      }
    },
    {
      "id": "15",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "EXPORT_RETENTION_DAYS",
      "setting_value": "60",
      "setting_type": "string",
      "category": "general",
      "description": "Días de retención de exportaciones PROD",
      "is_critical": "0",
      "display_value": "60",
      "manual_description": "Días de retención de exportaciones DEV",
      "doc": {
        "title": "Retención de exportaciones",
        "category": "Archivos",
        "desc": "Cantidad de días que se conservan los archivos exportados antes de limpieza o depuración."
      }
    },
    {
      "id": "3",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "exports_base_path",
      "setting_value": "C:\\PyFlow\\prod\\exports\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta de exportaciones PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\exports\\",
      "manual_description": "Carpeta de exportaciones DEV",
      "doc": {
        "title": "Carpeta base de exportaciones",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan los archivos exportados en el ambiente seleccionado."
      }
    },
    {
      "id": "14",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "LOG_RETENTION_DAYS",
      "setting_value": "120",
      "setting_type": "string",
      "category": "general",
      "description": "Días de retención de logs PROD",
      "is_critical": "0",
      "display_value": "120",
      "manual_description": "Días de retención de logs DEV",
      "doc": {
        "title": "Retención de logs",
        "category": "Logs",
        "desc": "Cantidad de días que se conservan los logs de ejecución antes de limpieza o depuración."
      }
    },
    {
      "id": "2",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "logs_base_path",
      "setting_value": "C:\\PyFlow\\prod\\logs\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta de logs PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\logs\\",
      "manual_description": "Carpeta de logs DEV",
      "doc": {
        "title": "Carpeta base de logs",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan logs generados por ejecuciones y procesos."
      }
    },
    {
      "id": "13",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "MAX_CONCURRENT_EXECUTIONS",
      "setting_value": "10",
      "setting_type": "string",
      "category": "general",
      "description": "Máximo de ejecuciones simultáneas PROD",
      "is_critical": "0",
      "display_value": "10",
      "manual_description": "Máximo de ejecuciones simultáneas DEV",
      "doc": {
        "title": "Máximo global de ejecuciones",
        "category": "Cola y concurrencia",
        "desc": "Número máximo de ejecuciones simultáneas permitidas a nivel global."
      }
    },
    {
      "id": "4",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "python_interpreter",
      "setting_value": "py",
      "setting_type": "string",
      "category": "general",
      "description": "Intérprete Python PROD",
      "is_critical": "0",
      "display_value": "py",
      "manual_description": "Intérprete Python DEV",
      "doc": {
        "title": "Intérprete Python",
        "category": "Ejecución",
        "desc": "Comando o ruta del intérprete de Python usado para ejecutar scripts. Ejemplos: py, python o una ruta completa."
      }
    },
    {
      "id": "1",
      "environment_id": "1",
      "environment_name": "Development",
      "setting_key": "scripts_base_path",
      "setting_value": "C:\\PyFlow\\prod\\scripts\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta base de scripts PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\scripts\\",
      "manual_description": "Carpeta base de scripts DEV",
      "doc": {
        "title": "Carpeta base de scripts",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan o preparan los scripts de ejecución para el ambiente seleccionado."
      }
    },
    {
      "id": "20",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "EMAIL_ENABLED",
      "setting_value": "true",
      "setting_type": "string",
      "category": "general",
      "description": "Habilitar envío de correos PROD",
      "is_critical": "0",
      "display_value": "true",
      "manual_description": "Habilitar envío de correos QA",
      "doc": {
        "title": "Envío de correos habilitado",
        "category": "Correo",
        "desc": "Activa o desactiva funcionalidades que envían correos en el ambiente seleccionado. Útil para evitar envíos reales en desarrollo o QA."
      }
    },
    {
      "id": "19",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "EXPORT_RETENTION_DAYS",
      "setting_value": "60",
      "setting_type": "string",
      "category": "general",
      "description": "Días de retención de exportaciones PROD",
      "is_critical": "0",
      "display_value": "60",
      "manual_description": "Días de retención de exportaciones QA",
      "doc": {
        "title": "Retención de exportaciones",
        "category": "Archivos",
        "desc": "Cantidad de días que se conservan los archivos exportados antes de limpieza o depuración."
      }
    },
    {
      "id": "7",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "exports_base_path",
      "setting_value": "C:\\PyFlow\\prod\\exports\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta de exportaciones PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\exports\\",
      "manual_description": "Carpeta de exportaciones QA",
      "doc": {
        "title": "Carpeta base de exportaciones",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan los archivos exportados en el ambiente seleccionado."
      }
    },
    {
      "id": "18",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "LOG_RETENTION_DAYS",
      "setting_value": "120",
      "setting_type": "string",
      "category": "general",
      "description": "Días de retención de logs PROD",
      "is_critical": "0",
      "display_value": "120",
      "manual_description": "Días de retención de logs QA",
      "doc": {
        "title": "Retención de logs",
        "category": "Logs",
        "desc": "Cantidad de días que se conservan los logs de ejecución antes de limpieza o depuración."
      }
    },
    {
      "id": "6",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "logs_base_path",
      "setting_value": "C:\\PyFlow\\prod\\logs\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta de logs PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\logs\\",
      "manual_description": "Carpeta de logs QA",
      "doc": {
        "title": "Carpeta base de logs",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan logs generados por ejecuciones y procesos."
      }
    },
    {
      "id": "17",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "MAX_CONCURRENT_EXECUTIONS",
      "setting_value": "10",
      "setting_type": "string",
      "category": "general",
      "description": "Máximo de ejecuciones simultáneas PROD",
      "is_critical": "0",
      "display_value": "10",
      "manual_description": "Máximo de ejecuciones simultáneas QA",
      "doc": {
        "title": "Máximo global de ejecuciones",
        "category": "Cola y concurrencia",
        "desc": "Número máximo de ejecuciones simultáneas permitidas a nivel global."
      }
    },
    {
      "id": "8",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "python_interpreter",
      "setting_value": "py",
      "setting_type": "string",
      "category": "general",
      "description": "Intérprete Python PROD",
      "is_critical": "0",
      "display_value": "py",
      "manual_description": "Intérprete Python QA",
      "doc": {
        "title": "Intérprete Python",
        "category": "Ejecución",
        "desc": "Comando o ruta del intérprete de Python usado para ejecutar scripts. Ejemplos: py, python o una ruta completa."
      }
    },
    {
      "id": "5",
      "environment_id": "2",
      "environment_name": "QA",
      "setting_key": "scripts_base_path",
      "setting_value": "C:\\PyFlow\\prod\\scripts\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta base de scripts PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\scripts\\",
      "manual_description": "Carpeta base de scripts QA",
      "doc": {
        "title": "Carpeta base de scripts",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan o preparan los scripts de ejecución para el ambiente seleccionado."
      }
    },
    {
      "id": "31",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "AUTH_GLOBAL_METHOD",
      "setting_value": "mixed",
      "setting_type": "string",
      "category": "auth",
      "description": "Método global de autenticación",
      "is_critical": "1",
      "display_value": "mixed",
      "manual_description": "Método global de autenticación",
      "doc": {
        "title": "Método global de autenticación",
        "category": "Autenticación",
        "desc": "Define el modo de acceso predeterminado del sistema. Puede trabajar junto con la configuración por rol o por usuario. Valores habituales: local, entra o mixed."
      }
    },
    {
      "id": "28",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "EXECUTION_TIMEOUT_SECONDS",
      "setting_value": "7200",
      "setting_type": "number",
      "category": "execution",
      "description": "Tiempo máximo por ejecución",
      "is_critical": "1",
      "display_value": "7200",
      "manual_description": "Tiempo máximo por ejecución",
      "doc": {
        "title": "Tiempo máximo por ejecución",
        "category": "Ejecución",
        "desc": "Límite máximo en segundos que puede durar una ejecución antes de considerarse vencida o candidata a cancelación según la lógica del backend."
      }
    },
    {
      "id": "26",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "MAX_CONCURRENT_EXECUTIONS_PER_SCRIPT",
      "setting_value": "3",
      "setting_type": "number",
      "category": "execution",
      "description": "Máximo concurrente por script",
      "is_critical": "1",
      "display_value": "3",
      "manual_description": "Máximo concurrente por script",
      "doc": {
        "title": "Máximo concurrente por script",
        "category": "Cola y concurrencia",
        "desc": "Cantidad máxima de ejecuciones simultáneas permitidas para el mismo script. Las ejecuciones adicionales quedan en cola."
      }
    },
    {
      "id": "27",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "MAX_CONCURRENT_EXECUTIONS_PER_USER",
      "setting_value": "2",
      "setting_type": "number",
      "category": "execution",
      "description": "Máximo concurrente por usuario",
      "is_critical": "1",
      "display_value": "2",
      "manual_description": "Máximo concurrente por usuario",
      "doc": {
        "title": "Máximo concurrente por usuario",
        "category": "Cola y concurrencia",
        "desc": "Cantidad máxima de ejecuciones simultáneas permitidas por usuario."
      }
    },
    {
      "id": "24",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "EMAIL_ENABLED",
      "setting_value": "true",
      "setting_type": "string",
      "category": "general",
      "description": "Habilitar envío de correos PROD",
      "is_critical": "0",
      "display_value": "true",
      "manual_description": "Habilitar envío de correos PROD",
      "doc": {
        "title": "Envío de correos habilitado",
        "category": "Correo",
        "desc": "Activa o desactiva funcionalidades que envían correos en el ambiente seleccionado. Útil para evitar envíos reales en desarrollo o QA."
      }
    },
    {
      "id": "23",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "EXPORT_RETENTION_DAYS",
      "setting_value": "60",
      "setting_type": "string",
      "category": "general",
      "description": "Días de retención de exportaciones PROD",
      "is_critical": "0",
      "display_value": "60",
      "manual_description": "Días de retención de exportaciones PROD",
      "doc": {
        "title": "Retención de exportaciones",
        "category": "Archivos",
        "desc": "Cantidad de días que se conservan los archivos exportados antes de limpieza o depuración."
      }
    },
    {
      "id": "11",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "exports_base_path",
      "setting_value": "C:\\PyFlow\\prod\\exports\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta de exportaciones PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\exports\\",
      "manual_description": "Carpeta de exportaciones PROD",
      "doc": {
        "title": "Carpeta base de exportaciones",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan los archivos exportados en el ambiente seleccionado."
      }
    },
    {
      "id": "22",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "LOG_RETENTION_DAYS",
      "setting_value": "120",
      "setting_type": "string",
      "category": "general",
      "description": "Días de retención de logs PROD",
      "is_critical": "0",
      "display_value": "120",
      "manual_description": "Días de retención de logs PROD",
      "doc": {
        "title": "Retención de logs",
        "category": "Logs",
        "desc": "Cantidad de días que se conservan los logs de ejecución antes de limpieza o depuración."
      }
    },
    {
      "id": "10",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "logs_base_path",
      "setting_value": "C:\\PyFlow\\prod\\logs\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta de logs PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\logs\\",
      "manual_description": "Carpeta de logs PROD",
      "doc": {
        "title": "Carpeta base de logs",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan logs generados por ejecuciones y procesos."
      }
    },
    {
      "id": "21",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "MAX_CONCURRENT_EXECUTIONS",
      "setting_value": "10",
      "setting_type": "string",
      "category": "general",
      "description": "Máximo de ejecuciones simultáneas PROD",
      "is_critical": "0",
      "display_value": "10",
      "manual_description": "Máximo de ejecuciones simultáneas PROD",
      "doc": {
        "title": "Máximo global de ejecuciones",
        "category": "Cola y concurrencia",
        "desc": "Número máximo de ejecuciones simultáneas permitidas a nivel global."
      }
    },
    {
      "id": "12",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "python_interpreter",
      "setting_value": "py",
      "setting_type": "string",
      "category": "general",
      "description": "Intérprete Python PROD",
      "is_critical": "0",
      "display_value": "py",
      "manual_description": "Intérprete Python PROD",
      "doc": {
        "title": "Intérprete Python",
        "category": "Ejecución",
        "desc": "Comando o ruta del intérprete de Python usado para ejecutar scripts. Ejemplos: py, python o una ruta completa."
      }
    },
    {
      "id": "9",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "scripts_base_path",
      "setting_value": "C:\\PyFlow\\prod\\scripts\\",
      "setting_type": "string",
      "category": "general",
      "description": "Carpeta base de scripts PROD",
      "is_critical": "0",
      "display_value": "C:\\PyFlow\\prod\\scripts\\",
      "manual_description": "Carpeta base de scripts PROD",
      "doc": {
        "title": "Carpeta base de scripts",
        "category": "Rutas",
        "desc": "Ruta física donde se almacenan o preparan los scripts de ejecución para el ambiente seleccionado."
      }
    },
    {
      "id": "29",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "QUEUE_PROCESS_INTERVAL_MS",
      "setting_value": "30000",
      "setting_type": "number",
      "category": "queue",
      "description": "Intervalo de procesamiento de cola",
      "is_critical": "1",
      "display_value": "30000",
      "manual_description": "Intervalo de procesamiento de cola",
      "doc": {
        "title": "Intervalo de procesamiento de cola",
        "category": "Cola y concurrencia",
        "desc": "Frecuencia en milisegundos con la que el procesador revisa trabajos pendientes en cola."
      }
    },
    {
      "id": "32",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "ADMIN_SECURITY_PIN",
      "setting_value": "1234",
      "setting_type": "secret",
      "category": "security",
      "description": "PIN administrativo para cambios críticos",
      "is_critical": "1",
      "display_value": "********",
      "manual_description": "PIN administrativo para cambios críticos",
      "doc": {
        "title": "PIN administrativo",
        "category": "Seguridad",
        "desc": "PIN requerido para guardar cambios críticos desde la pantalla de configuración. Debe tratarse como secreto y cambiarse en ambientes reales."
      }
    },
    {
      "id": "33",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "DEFAULT_THEME",
      "setting_value": "dark-blue",
      "setting_type": "string",
      "category": "themes",
      "description": "Tema predeterminado",
      "is_critical": "0",
      "display_value": "dark-blue",
      "manual_description": "Tema predeterminado",
      "doc": {
        "title": "Tema predeterminado",
        "category": "Temas",
        "desc": "Tema visual aplicado por defecto cuando el usuario no tiene una preferencia guardada."
      }
    },
    {
      "id": "30",
      "environment_id": "3",
      "environment_name": "Production",
      "setting_key": "AUTO_REFRESH_INTERVAL_SECONDS",
      "setting_value": "30",
      "setting_type": "number",
      "category": "ui",
      "description": "Intervalo de actualización automática por pantalla",
      "is_critical": "0",
      "display_value": "30",
      "manual_description": "Intervalo de actualización automática por pantalla",
      "doc": {
        "title": "Intervalo de auto-refresh",
        "category": "Interfaz",
        "desc": "Cantidad de segundos entre actualizaciones automáticas de las pantallas que refrescan datos sin recargar el navegador."
      }
    }
  ],
  "roles": [
    {
      "id": "1",
      "role_name": "Super Administrador",
      "description": "Acceso total",
      "auth_method": "mixed",
      "created_at": "46175.960004293978"
    },
    {
      "id": "2",
      "role_name": "Administrador del Sistema",
      "description": "Administra configuración y usuarios",
      "auth_method": "entra",
      "created_at": "46175.960004293978"
    },
    {
      "id": "3",
      "role_name": "Supervisor",
      "description": "Supervisión y operación",
      "auth_method": "mixed",
      "created_at": "46175.960004293978"
    },
    {
      "id": "4",
      "role_name": "Operador",
      "description": "Operación de scripts",
      "auth_method": "local",
      "created_at": "46175.960004293978"
    }
  ],
  "permissions": [
    {
      "id": "1",
      "permission_key": "dashboard.view",
      "module_key": "dashboard",
      "action_key": "view",
      "description": "Ver dashboard"
    },
    {
      "id": "2",
      "permission_key": "scripts.view",
      "module_key": "scripts",
      "action_key": "view",
      "description": "Ver scripts"
    },
    {
      "id": "3",
      "permission_key": "scripts.create",
      "module_key": "scripts",
      "action_key": "create",
      "description": "Crear scripts"
    },
    {
      "id": "4",
      "permission_key": "scripts.edit",
      "module_key": "scripts",
      "action_key": "edit",
      "description": "Editar scripts"
    },
    {
      "id": "5",
      "permission_key": "scripts.execute",
      "module_key": "scripts",
      "action_key": "execute",
      "description": "Ejecutar scripts"
    },
    {
      "id": "6",
      "permission_key": "executions.cancel",
      "module_key": "executions",
      "action_key": "cancel",
      "description": "Cancelar ejecuciones"
    },
    {
      "id": "7",
      "permission_key": "logs.view",
      "module_key": "logs",
      "action_key": "view",
      "description": "Ver logs"
    },
    {
      "id": "8",
      "permission_key": "schedules.create",
      "module_key": "schedules",
      "action_key": "create",
      "description": "Crear programaciones"
    },
    {
      "id": "9",
      "permission_key": "schedules.delete",
      "module_key": "schedules",
      "action_key": "delete",
      "description": "Eliminar programaciones"
    },
    {
      "id": "10",
      "permission_key": "users.manage",
      "module_key": "users",
      "action_key": "manage",
      "description": "Administrar usuarios"
    },
    {
      "id": "11",
      "permission_key": "settings.manage",
      "module_key": "settings",
      "action_key": "manage",
      "description": "Administrar configuración"
    },
    {
      "id": "12",
      "permission_key": "auth.manage",
      "module_key": "auth",
      "action_key": "manage",
      "description": "Cambiar métodos de autenticación"
    },
    {
      "id": "13",
      "permission_key": "themes.manage",
      "module_key": "themes",
      "action_key": "manage",
      "description": "Gestionar temas"
    }
  ],
  "authMethods": [
    {
      "method_key": "entra",
      "method_name": "Microsoft Entra ID / Azure AD",
      "is_enabled": "1",
      "config_json": ""
    },
    {
      "method_key": "local",
      "method_name": "Usuario y contraseña",
      "is_enabled": "1",
      "config_json": ""
    },
    {
      "method_key": "mixed",
      "method_name": "Autenticación mixta",
      "is_enabled": "1",
      "config_json": ""
    }
  ],
  "themes": [
    {
      "theme_key": "aurora",
      "theme_name": "Aurora",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "banking-blue",
      "theme_name": "Banking Blue",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "corporate-gray",
      "theme_name": "Corporate Gray",
      "is_dark": "0",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "crimson",
      "theme_name": "Crimson",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "cyberpunk",
      "theme_name": "Cyberpunk",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "dark-blue",
      "theme_name": "Dark Blue",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "dracula",
      "theme_name": "Dracula",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "emerald",
      "theme_name": "Emerald",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "github-dark",
      "theme_name": "GitHub Dark",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "gold",
      "theme_name": "Gold",
      "is_dark": "0",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "light",
      "theme_name": "Light",
      "is_dark": "0",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "matrix",
      "theme_name": "Matrix",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "monokai",
      "theme_name": "Monokai",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "navy",
      "theme_name": "Navy",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "nord",
      "theme_name": "Nord",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "obsidian",
      "theme_name": "Obsidian",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "ocean",
      "theme_name": "Ocean",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "purple",
      "theme_name": "Purple",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "titanium",
      "theme_name": "Titanium",
      "is_dark": "0",
      "tokens_json": "",
      "is_enabled": "1"
    },
    {
      "theme_key": "vscode-dark",
      "theme_name": "VS Code Dark",
      "is_dark": "1",
      "tokens_json": "",
      "is_enabled": "1"
    }
  ],
  "schema": {
    "Schedules": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "script_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "created_by_user_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "cron_expression",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "frequency_label",
        "type": "nvarchar(150)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "timezone_name",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "next_run_at",
        "type": "datetime2(0)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "last_run_at",
        "type": "datetime2(0)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "last_status",
        "type": "nvarchar(20)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "last_error",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "run_on_startup",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_active",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "max_retries",
        "type": "smallint",
        "nullable": false,
        "identity": false
      },
      {
        "name": "retry_delay_seconds",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "updated_at",
        "type": "datetime2(0)",
        "nullable": true,
        "identity": false
      }
    ],
    "ScriptExecutions": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "script_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "script_version_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "schedule_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "triggered_by_user_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "parent_execution_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "status",
        "type": "nvarchar(20)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "trigger_type",
        "type": "nvarchar(20)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "start_time",
        "type": "datetime2(3)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "end_time",
        "type": "datetime2(3)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "duration_seconds",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "exit_code",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "retry_attempt",
        "type": "smallint",
        "nullable": false,
        "identity": false
      },
      {
        "name": "process_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "machine_name",
        "type": "nvarchar(255)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "command_line",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "working_directory",
        "type": "nvarchar(1000)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "error_message",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      }
    ],
    "Environments": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "name",
        "type": "nvarchar(50)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(255)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "is_active",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      }
    ],
    "Users": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "username",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "email",
        "type": "nvarchar(255)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "display_name",
        "type": "nvarchar(255)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "auth_provider",
        "type": "nvarchar(30)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "azure_ad_object_id",
        "type": "nvarchar(100)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "domain_user",
        "type": "nvarchar(150)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "password_hash",
        "type": "nvarchar(512)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "role",
        "type": "nvarchar(50)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_active",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "updated_at",
        "type": "datetime2(0)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "last_login",
        "type": "datetime2(0)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "theme_key",
        "type": "nvarchar(100)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "preferred_theme",
        "type": "nvarchar(100)",
        "nullable": true,
        "identity": false
      }
    ],
    "Scripts": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "created_by_user_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "environment_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "name",
        "type": "nvarchar(255)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(1000)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "category",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "current_version",
        "type": "nvarchar(30)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "file_path",
        "type": "nvarchar(1000)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "working_directory",
        "type": "nvarchar(1000)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "python_interpreter",
        "type": "nvarchar(1000)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "author",
        "type": "nvarchar(255)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "is_active",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "allow_manual_run",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "updated_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      }
    ],
    "ExecutionFiles": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "execution_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "file_name",
        "type": "nvarchar(255)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "file_path",
        "type": "nvarchar(1000)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "file_type",
        "type": "nvarchar(30)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "mime_type",
        "type": "nvarchar(150)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "file_size_bytes",
        "type": "bigint",
        "nullable": true,
        "identity": false
      },
      {
        "name": "checksum_sha256",
        "type": "nvarchar(128)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "is_deleted",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      }
    ],
    "ExecutionLogs": [
      {
        "name": "id",
        "type": "bigint",
        "nullable": false,
        "identity": true
      },
      {
        "name": "execution_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "log_level",
        "type": "nvarchar(10)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "message",
        "type": "nvarchar(max)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "logged_at",
        "type": "datetime2(3)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "line_number",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "source",
        "type": "nvarchar(100)",
        "nullable": true,
        "identity": false
      }
    ],
    "AuthMethods": [
      {
        "name": "method_key",
        "type": "nvarchar(50)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "method_name",
        "type": "nvarchar(120)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_enabled",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "config_json",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      }
    ],
    "ConfigurationAudit": [
      {
        "name": "id",
        "type": "bigint",
        "nullable": false,
        "identity": true
      },
      {
        "name": "module_key",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "setting_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "old_value",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "new_value",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "changed_by",
        "type": "nvarchar(150)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "ip_address",
        "type": "nvarchar(80)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "user_agent",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "changed_at",
        "type": "datetime2(7)",
        "nullable": false,
        "identity": false
      }
    ],
    "ExecutionParameters": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "execution_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "param_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "param_value",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": true,
        "identity": false
      }
    ],
    "ExecutionQueue": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "script_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "schedule_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "parameters_json",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "status",
        "type": "nvarchar(20)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "started_at",
        "type": "datetime2(7)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "completed_at",
        "type": "datetime2(7)",
        "nullable": true,
        "identity": false
      }
    ],
    "GlobalVariables": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "var_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "var_value",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "is_secret",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "updated_at",
        "type": "datetime2(7)",
        "nullable": true,
        "identity": false
      }
    ],
    "LoginAudit": [
      {
        "name": "id",
        "type": "bigint",
        "nullable": false,
        "identity": true
      },
      {
        "name": "user_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "username",
        "type": "nvarchar(150)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "auth_method",
        "type": "nvarchar(50)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "success",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "ip_address",
        "type": "nvarchar(80)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "user_agent",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "message",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": false,
        "identity": false
      }
    ],
    "PasswordResetTokens": [
      {
        "name": "id",
        "type": "bigint",
        "nullable": false,
        "identity": true
      },
      {
        "name": "user_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "token_hash",
        "type": "nvarchar(128)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "channel",
        "type": "nvarchar(20)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "expires_at",
        "type": "datetime2(7)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "used_at",
        "type": "datetime2(7)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": false,
        "identity": false
      }
    ],
    "Permissions": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "permission_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "module_key",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "action_key",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      }
    ],
    "RoleAuthConfig": [
      {
        "name": "role_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "method_key",
        "type": "nvarchar(50)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_required",
        "type": "bit",
        "nullable": false,
        "identity": false
      }
    ],
    "RolePermissions": [
      {
        "name": "role_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "permission_id",
        "type": "int",
        "nullable": false,
        "identity": false
      }
    ],
    "Roles": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "role_name",
        "type": "nvarchar(120)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "auth_method",
        "type": "nvarchar(50)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": false,
        "identity": false
      }
    ],
    "ScheduleParameters": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "schedule_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "param_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "param_value",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": true,
        "identity": false
      }
    ],
    "ScriptDependencies": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "script_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "depends_on_script_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "execution_order",
        "type": "smallint",
        "nullable": false,
        "identity": false
      },
      {
        "name": "dependency_type",
        "type": "nvarchar(20)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_active",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      }
    ],
    "ScriptParameters": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "script_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "secret_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "param_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "param_value",
        "type": "nvarchar(1000)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "param_type",
        "type": "nvarchar(30)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_secret",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "updated_at",
        "type": "datetime2(0)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "options_json",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "label",
        "type": "nvarchar(255)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "is_required",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "control_type",
        "type": "nvarchar(30)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "global_key",
        "type": "nvarchar(150)",
        "nullable": true,
        "identity": false
      }
    ],
    "ScriptVersions": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "script_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "version",
        "type": "nvarchar(30)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "file_path",
        "type": "nvarchar(1000)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "checksum_sha256",
        "type": "nvarchar(128)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "change_notes",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_by_user_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_current",
        "type": "bit",
        "nullable": false,
        "identity": false
      }
    ],
    "Secrets": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "secret_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "encrypted_value",
        "type": "varbinary(max)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "updated_by_user_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "updated_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      }
    ],
    "SystemSettings": [
      {
        "name": "id",
        "type": "int",
        "nullable": false,
        "identity": true
      },
      {
        "name": "environment_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "setting_key",
        "type": "nvarchar(150)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "setting_value",
        "type": "nvarchar(1000)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "description",
        "type": "nvarchar(500)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "updated_by_user_id",
        "type": "int",
        "nullable": true,
        "identity": false
      },
      {
        "name": "updated_at",
        "type": "datetime2(0)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "setting_type",
        "type": "nvarchar(50)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "category",
        "type": "nvarchar(80)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "is_critical",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "updated_by",
        "type": "nvarchar(150)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "created_at",
        "type": "datetime2(7)",
        "nullable": false,
        "identity": false
      }
    ],
    "Themes": [
      {
        "name": "theme_key",
        "type": "nvarchar(80)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "theme_name",
        "type": "nvarchar(120)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_dark",
        "type": "bit",
        "nullable": false,
        "identity": false
      },
      {
        "name": "tokens_json",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      },
      {
        "name": "is_enabled",
        "type": "bit",
        "nullable": false,
        "identity": false
      }
    ],
    "UserAuthConfig": [
      {
        "name": "user_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "method_key",
        "type": "nvarchar(50)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "is_required",
        "type": "bit",
        "nullable": false,
        "identity": false
      }
    ],
    "UserPreferences": [
      {
        "name": "user_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "preference_key",
        "type": "nvarchar(100)",
        "nullable": false,
        "identity": false
      },
      {
        "name": "preference_value",
        "type": "nvarchar(max)",
        "nullable": true,
        "identity": false
      }
    ],
    "UserRoles": [
      {
        "name": "user_id",
        "type": "int",
        "nullable": false,
        "identity": false
      },
      {
        "name": "role_id",
        "type": "int",
        "nullable": false,
        "identity": false
      }
    ]
  },
  "fks": [
    {
      "from_table": "AuthMethods",
      "from_column": "execution_id",
      "to_table": "ScriptExecutions",
      "to_column": "id"
    },
    {
      "from_table": "ExecutionFiles",
      "from_column": "execution_id",
      "to_table": "ScriptExecutions",
      "to_column": "id"
    },
    {
      "from_table": "ExecutionLogs",
      "from_column": "execution_id",
      "to_table": "ScriptExecutions",
      "to_column": "id"
    },
    {
      "from_table": "ExecutionParameters",
      "from_column": "user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "RoleAuthConfig",
      "from_column": "role_id",
      "to_table": "Roles",
      "to_column": "id"
    },
    {
      "from_table": "RolePermissions",
      "from_column": "permission_id",
      "to_table": "Permissions",
      "to_column": "id"
    },
    {
      "from_table": "RolePermissions",
      "from_column": "role_id",
      "to_table": "Roles",
      "to_column": "id"
    },
    {
      "from_table": "ScheduleParameters",
      "from_column": "schedule_id",
      "to_table": "Schedules",
      "to_column": "id"
    },
    {
      "from_table": "ScheduleParameters",
      "from_column": "script_id",
      "to_table": "Scripts",
      "to_column": "id"
    },
    {
      "from_table": "Schedules",
      "from_column": "created_by_user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "Schedules",
      "from_column": "depends_on_script_id",
      "to_table": "Scripts",
      "to_column": "id"
    },
    {
      "from_table": "ScriptDependencies",
      "from_column": "script_id",
      "to_table": "Scripts",
      "to_column": "id"
    },
    {
      "from_table": "ScriptDependencies",
      "from_column": "parent_execution_id",
      "to_table": "ScriptExecutions",
      "to_column": "id"
    },
    {
      "from_table": "ScriptExecutions",
      "from_column": "schedule_id",
      "to_table": "Schedules",
      "to_column": "id"
    },
    {
      "from_table": "ScriptExecutions",
      "from_column": "script_id",
      "to_table": "Scripts",
      "to_column": "id"
    },
    {
      "from_table": "ScriptExecutions",
      "from_column": "script_version_id",
      "to_table": "ScriptVersions",
      "to_column": "id"
    },
    {
      "from_table": "ScriptExecutions",
      "from_column": "triggered_by_user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "ScriptExecutions",
      "from_column": "script_id",
      "to_table": "Scripts",
      "to_column": "id"
    },
    {
      "from_table": "ScriptParameters",
      "from_column": "secret_id",
      "to_table": "Secrets",
      "to_column": "id"
    },
    {
      "from_table": "ScriptParameters",
      "from_column": "environment_id",
      "to_table": "Environments",
      "to_column": "id"
    },
    {
      "from_table": "Scripts",
      "from_column": "created_by_user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "Scripts",
      "from_column": "script_id",
      "to_table": "Scripts",
      "to_column": "id"
    },
    {
      "from_table": "ScriptVersions",
      "from_column": "created_by_user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "ScriptVersions",
      "from_column": "updated_by_user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "Secrets",
      "from_column": "environment_id",
      "to_table": "Environments",
      "to_column": "id"
    },
    {
      "from_table": "SystemSettings",
      "from_column": "updated_by_user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "SystemSettings",
      "from_column": "user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "UserPreferences",
      "from_column": "user_id",
      "to_table": "Users",
      "to_column": "id"
    },
    {
      "from_table": "UserRoles",
      "from_column": "role_id",
      "to_table": "Roles",
      "to_column": "id"
    },
    {
      "from_table": "UserRoles",
      "from_column": "user_id",
      "to_table": "Users",
      "to_column": "id"
    }
  ],
  "checks": [
    {
      "table": "AuthMethods",
      "name": "CK_ExecutionFiles_type",
      "definition": "[file_type]='other' OR [file_type]='png' OR [file_type]='log' OR [file_type]='json' OR [file_type]='txt' OR [file_type]='zip' OR [file_type]='pdf' OR [file_type]='csv' OR [file_type]='xlsx'"
    },
    {
      "table": "ExecutionFiles",
      "name": "CK_ExecutionLogs_level",
      "definition": "[log_level]='CRITICAL' OR [log_level]='ERROR' OR [log_level]='WARNING' OR [log_level]='INFO' OR [log_level]='DEBUG'"
    },
    {
      "table": "ExecutionLogs",
      "name": "CK_Schedules_retries",
      "definition": "[max_retries]>=(0) AND [max_retries]<=(10"
    },
    {
      "table": "Schedules",
      "name": "CK_Schedules_retry_delay",
      "definition": "[retry_delay_seconds]>=(0) AND [retry_delay_seconds]<=(86400"
    },
    {
      "table": "Schedules",
      "name": "CK_Schedules_status",
      "definition": "[last_status] IS NULL OR ([last_status]='Ejecutando' OR [last_status]='Cancelado' OR [last_status]='Error' OR [last_status]='Exitoso'"
    },
    {
      "table": "Schedules",
      "name": "CK_ScriptDependencies_no_self",
      "definition": "[script_id]<>[depends_on_script_id]"
    },
    {
      "table": "ScriptDependencies",
      "name": "CK_ScriptDependencies_type",
      "definition": "[dependency_type]='soft' OR [dependency_type]='hard'"
    },
    {
      "table": "ScriptDependencies",
      "name": "CK_Executions_status",
      "definition": "[status]='Cancelado' OR [status]='Error' OR [status]='Exitoso' OR [status]='Ejecutando'"
    },
    {
      "table": "ScriptExecutions",
      "name": "CK_Executions_trigger",
      "definition": "[trigger_type]='system' OR [trigger_type]='api' OR [trigger_type]='dependency' OR [trigger_type]='schedule' OR [trigger_type]='manual'"
    },
    {
      "table": "ScriptExecutions",
      "name": "CK_ScriptParameters_secret_consistency",
      "definition": "[is_secret]=(0) AND [param_value] IS NOT NULL OR [is_secret]=(1) AND [secret_id] IS NOT NULL"
    },
    {
      "table": "ScriptParameters",
      "name": "CK_ScriptParameters_type",
      "definition": "[param_type]='config' OR [param_type]='argv' OR [param_type]='env'"
    },
    {
      "table": "ScriptParameters",
      "name": "CK_Users_auth_provider",
      "definition": "[auth_provider]='entra_id' OR [auth_provider]='active_directory' OR [auth_provider]='local'"
    },
    {
      "table": "Users",
      "name": "CK_Users_password_provider",
      "definition": "[auth_provider]='local' AND [password_hash] IS NOT NULL OR ([auth_provider]='entra_id' OR [auth_provider]='active_directory'"
    },
    {
      "table": "Users",
      "name": "CK_Users_role",
      "definition": "[role]='Viewer' OR [role]='Operator' OR [role]='Developer' OR [role]='DataArchitect' OR [role]='Admin'"
    }
  ],
  "tableDescriptions": {
    "Scripts": "Catálogo principal de scripts administrados por PyFlow. Guarda nombre, descripción, rutas, estado, ambiente y metadatos.",
    "ScriptVersions": "Historial de versiones de cada script. Permite mantener control sobre cambios y ejecutar versiones específicas.",
    "ScriptParameters": "Definición de parámetros requeridos por cada script, incluyendo tipo, obligatoriedad, origen y valores predeterminados.",
    "ExecutionParameters": "Valores concretos usados en una ejecución individual.",
    "ScriptExecutions": "Registro maestro de cada ejecución: estado, fechas, usuario, salida, códigos y métricas.",
    "ExecutionLogs": "Bitácora detallada generada durante la ejecución de scripts.",
    "ExecutionFiles": "Archivos generados o asociados a una ejecución.",
    "ExecutionQueue": "Cola de ejecución usada para controlar concurrencia y orden de procesamiento.",
    "Schedules": "Programaciones automáticas de scripts usando expresiones cron y zona horaria.",
    "ScheduleParameters": "Parámetros que se aplican a ejecuciones disparadas por una programación.",
    "ScriptDependencies": "Relaciones de dependencia entre scripts.",
    "GlobalVariables": "Variables globales reutilizables en scripts, como credenciales, rutas, endpoints y parámetros comunes.",
    "Secrets": "Valores sensibles cifrados o protegidos.",
    "SystemSettings": "Parámetros del sistema por ambiente: concurrencia, rutas, retención, scheduler, temas, seguridad y auto-refresh.",
    "Environments": "Catálogo de ambientes como DEV, QA y PROD.",
    "Users": "Usuarios del sistema, credenciales locales, estado, proveedor de autenticación, tema y datos básicos.",
    "Roles": "Roles funcionales o administrativos.",
    "Permissions": "Permisos granulares por módulo y acción.",
    "UserRoles": "Relación muchos a muchos entre usuarios y roles.",
    "RolePermissions": "Relación muchos a muchos entre roles y permisos.",
    "AuthMethods": "Métodos de autenticación disponibles: local, Entra ID, mixto u otros futuros.",
    "UserAuthConfig": "Configuración de autenticación específica por usuario.",
    "RoleAuthConfig": "Configuración de autenticación por rol.",
    "LoginAudit": "Auditoría de inicios de sesión exitosos y fallidos.",
    "ConfigurationAudit": "Auditoría de cambios en configuraciones críticas.",
    "PasswordResetTokens": "Tokens temporales para recuperación de contraseña.",
    "Themes": "Temas visuales disponibles en el sistema.",
    "UserPreferences": "Preferencias individuales del usuario."
  },
  "paramDocs": {
    "AUTH_GLOBAL_METHOD": {
      "title": "Método global de autenticación",
      "category": "Autenticación",
      "desc": "Define el modo de acceso predeterminado del sistema. Puede trabajar junto con la configuración por rol o por usuario. Valores habituales: local, entra o mixed."
    },
    "ADMIN_SECURITY_PIN": {
      "title": "PIN administrativo",
      "category": "Seguridad",
      "desc": "PIN requerido para guardar cambios críticos desde la pantalla de configuración. Debe tratarse como secreto y cambiarse en ambientes reales."
    },
    "AUTO_REFRESH_INTERVAL_SECONDS": {
      "title": "Intervalo de auto-refresh",
      "category": "Interfaz",
      "desc": "Cantidad de segundos entre actualizaciones automáticas de las pantallas que refrescan datos sin recargar el navegador."
    },
    "DEFAULT_THEME": {
      "title": "Tema predeterminado",
      "category": "Temas",
      "desc": "Tema visual aplicado por defecto cuando el usuario no tiene una preferencia guardada."
    },
    "EMAIL_ENABLED": {
      "title": "Envío de correos habilitado",
      "category": "Correo",
      "desc": "Activa o desactiva funcionalidades que envían correos en el ambiente seleccionado. Útil para evitar envíos reales en desarrollo o QA."
    },
    "EXECUTION_TIMEOUT_SECONDS": {
      "title": "Tiempo máximo por ejecución",
      "category": "Ejecución",
      "desc": "Límite máximo en segundos que puede durar una ejecución antes de considerarse vencida o candidata a cancelación según la lógica del backend."
    },
    "EXPORT_RETENTION_DAYS": {
      "title": "Retención de exportaciones",
      "category": "Archivos",
      "desc": "Cantidad de días que se conservan los archivos exportados antes de limpieza o depuración."
    },
    "LOG_RETENTION_DAYS": {
      "title": "Retención de logs",
      "category": "Logs",
      "desc": "Cantidad de días que se conservan los logs de ejecución antes de limpieza o depuración."
    },
    "MAX_CONCURRENT_EXECUTIONS": {
      "title": "Máximo global de ejecuciones",
      "category": "Cola y concurrencia",
      "desc": "Número máximo de ejecuciones simultáneas permitidas a nivel global."
    },
    "MAX_CONCURRENT_EXECUTIONS_PER_SCRIPT": {
      "title": "Máximo concurrente por script",
      "category": "Cola y concurrencia",
      "desc": "Cantidad máxima de ejecuciones simultáneas permitidas para el mismo script. Las ejecuciones adicionales quedan en cola."
    },
    "MAX_CONCURRENT_EXECUTIONS_PER_USER": {
      "title": "Máximo concurrente por usuario",
      "category": "Cola y concurrencia",
      "desc": "Cantidad máxima de ejecuciones simultáneas permitidas por usuario."
    },
    "QUEUE_PROCESS_INTERVAL_MS": {
      "title": "Intervalo de procesamiento de cola",
      "category": "Cola y concurrencia",
      "desc": "Frecuencia en milisegundos con la que el procesador revisa trabajos pendientes en cola."
    },
    "exports_base_path": {
      "title": "Carpeta base de exportaciones",
      "category": "Rutas",
      "desc": "Ruta física donde se almacenan los archivos exportados en el ambiente seleccionado."
    },
    "logs_base_path": {
      "title": "Carpeta base de logs",
      "category": "Rutas",
      "desc": "Ruta física donde se almacenan logs generados por ejecuciones y procesos."
    },
    "scripts_base_path": {
      "title": "Carpeta base de scripts",
      "category": "Rutas",
      "desc": "Ruta física donde se almacenan o preparan los scripts de ejecución para el ambiente seleccionado."
    },
    "python_interpreter": {
      "title": "Intérprete Python",
      "category": "Ejecución",
      "desc": "Comando o ruta del intérprete de Python usado para ejecutar scripts. Ejemplos: py, python o una ruta completa."
    }
  },
  "modules": [
    {
      "title": "Dashboard",
      "keywords": "dashboard métricas resumen indicadores actualización automática",
      "content": "Pantalla principal para visualizar el estado general del sistema, últimas ejecuciones, métricas operativas y estado de servicios."
    },
    {
      "title": "Scripts",
      "keywords": "scripts versiones parámetros python ejecutar editar crear",
      "content": "Permite registrar, versionar, revisar y ejecutar scripts. Los parámetros pueden venir del formulario, variables globales o configuración del ambiente."
    },
    {
      "title": "Ejecuciones",
      "keywords": "ejecuciones historial estado cancelación timeout cola",
      "content": "Muestra el historial de ejecuciones, estado, duración, usuario, script ejecutado y resultado final."
    },
    {
      "title": "Logs",
      "keywords": "logs consola progreso errores seguimiento tiempo real",
      "content": "Centraliza mensajes de ejecución y diagnóstico. Se usa para revisar progreso, errores y eventos técnicos."
    },
    {
      "title": "Programaciones",
      "keywords": "scheduler cron horarios automatización periodicidad",
      "content": "Permite programar scripts para ejecutarse automáticamente según horarios o recurrencias."
    },
    {
      "title": "Cola de ejecución",
      "keywords": "cola concurrencia pendientes running límites",
      "content": "Gestiona trabajos pendientes y en ejecución, aplicando límites globales, por script y por usuario."
    },
    {
      "title": "Variables globales",
      "keywords": "variables globales secretos credenciales configuración scripts",
      "content": "Administra valores reutilizables por scripts, incluyendo secretos que se muestran enmascarados."
    },
    {
      "title": "Usuarios",
      "keywords": "usuarios roles permisos autenticación tema estado",
      "content": "Módulo para crear, editar y administrar usuarios, estado, proveedor de autenticación, tema y roles."
    },
    {
      "title": "Roles y permisos",
      "keywords": "roles permisos requirePermission users.manage settings.manage",
      "content": "Controla el acceso a módulos y acciones mediante relaciones UserRoles, RolePermissions y Permissions."
    },
    {
      "title": "Configuración del sistema",
      "keywords": "systemsettings ambiente parámetros pin configuración crítica",
      "content": "Administra parámetros por ambiente, seguridad, ejecución, cola, correo, rutas, temas y auto-refresh."
    },
    {
      "title": "Temas visuales",
      "keywords": "themes dark light visual apariencia css",
      "content": "Permite cambiar la apariencia visual del sistema y guardar la preferencia del usuario."
    },
    {
      "title": "Recuperación de contraseña",
      "keywords": "forgot password reset token correo sms pbkdf2",
      "content": "Genera tokens temporales para restablecimiento de contraseña y permite preparar envíos por correo o canales alternativos."
    }
  ],
  "troubles": [
    {
      "title": "Credenciales inválidas con usuario existente",
      "body": "Verifica que Users.password_hash use formato pbkdf2$120000$salt$hash si el backend usa verifyPassword con PBKDF2. Los hashes bcrypt $2b$ no serán válidos con esa función."
    },
    {
      "title": "Invalid column name status/auth_method/full_name",
      "body": "El modelo Enterprise puede usar nombres distintos a la base existente. En esta instalación los equivalentes principales son is_active, auth_provider y display_name."
    },
    {
      "title": "Validation failed for parameter is_active",
      "body": "La columna Users.is_active es BIT. El backend debe enviar true/false o 1/0, no ACTIVE/INACTIVE como texto."
    },
    {
      "title": "CHECK constraint CK_Users_auth_provider",
      "body": "Users.auth_provider solo acepta los valores definidos por la restricción de la base. Si mixed es configuración de rol o global, no debe guardarse necesariamente en Users.auth_provider."
    },
    {
      "title": "Parámetros repetidos",
      "body": "No siempre son duplicados. Muchos parámetros existen una vez por ambiente: Development, QA y Production."
    },
    {
      "title": "GROUP BY con SELECT u.*",
      "body": "Si se usa STRING_AGG con Users, evita SELECT u.* con GROUP BY. Usa OUTER APPLY para roles y así no se rompe cuando se agregan columnas."
    },
    {
      "title": "PIN administrativo inválido",
      "body": "Los cambios críticos validan ADMIN_SECURITY_PIN. El valor debe revisarse en SystemSettings y no mostrarse en pantallas o manuales."
    }
  ],
  "metadata": {
    "title": "Manual PyFlow Manager",
    "version": "Enterprise",
    "updatedAt": "2026-06-03 07:41"
  }
};