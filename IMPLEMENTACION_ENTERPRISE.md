# PyFlow Manager - Mejoras Enterprise agregadas

Se agregaron funcionalidades sin eliminar los módulos existentes de scripts, ejecuciones, logs, programaciones, dashboard y variables globales.

## Nuevos módulos

- Autenticación local con usuario/contraseña en base de datos.
- Preparación para Microsoft Entra ID / Azure AD y proveedores futuros.
- Recuperación de contraseña por token temporal con expiración.
- Módulo de usuarios, roles, permisos, método de autenticación, estado y tema visual.
- Configuración avanzada del sistema con validación de PIN administrativo.
- Auditoría de cambios críticos y auditoría de inicio de sesión.
- Selector de temas visuales con 20 temas iniciales.
- Auto-refresh centralizado por pantalla usando `AUTO_REFRESH_INTERVAL_SECONDS`.

## Pasos de instalación

1. Ejecutar el script SQL:

```sql
backend/src/migrations/20260602_enterprise_security_settings.sql
```

2. Levantar backend:

```bash
cd backend
npm install
npm run dev
```

3. Levantar frontend:

```bash
cd frontend
npm install
npm start
```

4. Ingresar con usuario inicial:

- Usuario: `admin`
- Contraseña: `PyFlow123*`
- PIN administrativo inicial para configuración crítica: `1234`

Cambiar ambos valores después del primer ingreso.

## Endpoints agregados

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/:id`
- `POST /api/users/:id/password`
- `GET /api/themes`
- `POST /api/themes/me`
- `POST /api/settings/system`
- `GET /api/settings/audit`

## Tablas agregadas

- `SystemSettings`
- `Users`
- `Roles`
- `Permissions`
- `UserRoles`
- `RolePermissions`
- `AuthMethods`
- `UserAuthConfig`
- `RoleAuthConfig`
- `ConfigurationAudit`
- `LoginAudit`
- `PasswordResetTokens`
- `Themes`
- `UserPreferences`

## Nota sobre Entra ID / Azure AD

El backend queda preparado para redirigir/validar proveedor externo. Para producción se debe registrar la aplicación en Microsoft Entra ID y configurar MSAL en Angular, además de validar el `id_token` en backend contra los metadatos de Microsoft.
