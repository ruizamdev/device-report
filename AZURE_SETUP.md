# Configuración de Azure AD para OneDrive

Esta guía te ayudará a configurar una aplicación en Azure AD para que **Device Report** pueda subir archivos a tu OneDrive automáticamente usando Microsoft Graph API.

## 🔧 Requisitos Previos

- Una cuenta de Microsoft (Outlook, Hotmail, o Microsoft 365)
- Acceso a [Azure Portal](https://portal.azure.com) (gratuito)

---

## 📝 Pasos de Configuración

### 1. Acceder a Azure Portal

1. Ve a [https://portal.azure.com](https://portal.azure.com)
2. Inicia sesión con tu cuenta de Microsoft
3. Si es tu primera vez, acepta los términos de servicio

### 2. Registrar una Nueva Aplicación

1. En el menú de la izquierda, busca **"Azure Active Directory"** o **"Microsoft Entra ID"**
2. En el menú lateral, haz clic en **"App registrations"** (Registros de aplicaciones)
3. Haz clic en **"+ New registration"** (Nuevo registro)

### 3. Configurar la Aplicación

Completa el formulario con los siguientes datos:

- **Name** (Nombre): `DeviceReport` (o el nombre que prefieras)
- **Supported account types** (Tipos de cuenta compatibles):
  - Selecciona: **"Accounts in any organizational directory and personal Microsoft accounts"**
  - (Cuentas de cualquier directorio organizativo y cuentas personales de Microsoft)
- **Redirect URI** (URI de redirección): Déjalo en blanco por ahora

Haz clic en **"Register"** (Registrar)

### 4. Copiar el Client ID

Una vez creada la aplicación, verás la página de **Overview** (Información general):

1. Busca el campo **"Application (client) ID"**
2. Copia este valor (tiene formato: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
3. Guárdalo temporalmente en un bloc de notas

### 5. Crear un Client Secret

1. En el menú lateral de tu aplicación, haz clic en **"Certificates & secrets"** (Certificados y secretos)
2. En la pestaña **"Client secrets"**, haz clic en **"+ New client secret"**
3. Agrega una descripción: `DeviceReport Secret`
4. Selecciona una duración:
   - **6 months** (6 meses)
   - **12 months** (12 meses)
   - **24 months** (24 meses) - **Recomendado**
5. Haz clic en **"Add"**
6. **¡IMPORTANTE!** Copia el **Value** (Valor) del secreto **inmediatamente**
   - Este valor solo se muestra una vez
   - Si no lo copias ahora, tendrás que crear un nuevo secreto
7. Guárdalo en tu bloc de notas junto con el Client ID

### 6. Configurar Permisos de API

1. En el menú lateral, haz clic en **"API permissions"** (Permisos de API)
2. Haz clic en **"+ Add a permission"** (Agregar un permiso)
3. Selecciona **"Microsoft Graph"**
4. Selecciona **"Application permissions"** (Permisos de aplicación)
5. Busca y selecciona los siguientes permisos:
   - `Files.ReadWrite.All` - Leer y escribir archivos en todas las colecciones

   **IMPORTANTE**: Para usar permisos de aplicación, necesitas una cuenta de Microsoft 365. Si solo tienes una cuenta personal (Outlook/Hotmail), usa **Delegated permissions** en su lugar:

   **Alternativa para cuentas personales:**
   - Selecciona **"Delegated permissions"** en lugar de "Application permissions"
   - Busca y selecciona: `Files.ReadWrite.All`

6. Haz clic en **"Add permissions"**

### 7. Conceder Consentimiento de Administrador (Solo para Application Permissions)

Si usaste **Application permissions**:

1. En la página de permisos, haz clic en **"Grant admin consent for [tu organización]"**
2. Confirma haciendo clic en **"Yes"**
3. Verás un checkmark verde en la columna **Status**

Si usaste **Delegated permissions**, omite este paso.

---

## 📋 Configurar config.json

Ahora que tienes tu **Client ID** y **Client Secret**, edita el archivo `config.json`:

```json
{
  "OneDrive": {
    "TenantId": "common",
    "ClientId": "PEGA_AQUI_TU_CLIENT_ID",
    "ClientSecret": "PEGA_AQUI_TU_CLIENT_SECRET",
    "UploadFolder": "DeviceReports",
    "RedirectUri": "http://localhost"
  },
  ...
}
```

### Notas sobre TenantId:

- Para **cuentas personales** (Outlook, Hotmail): usa `"common"`
- Para **Microsoft 365 organizacional**: usa tu Tenant ID específico (lo encuentras en Azure AD > Overview)

---

## 🔐 Autenticación con Delegated Permissions (Cuentas Personales)

Si configuraste **Delegated permissions** (para cuentas personales), necesitarás modificar ligeramente el módulo `Send-ToOneDrive.ps1` para usar autenticación interactiva:

### Opción 1: Device Code Flow (Recomendado para cuentas personales)

El módulo actual usa `client_credentials` que solo funciona con Application permissions. Para cuentas personales, implementaremos Device Code Flow en una actualización futura.

### Opción 2: Usar una cuenta Microsoft 365

Si tienes acceso a Microsoft 365 (de trabajo o escuela), puedes usar Application permissions sin modificaciones.

---

## ✅ Verificar la Configuración

Una vez configurado, ejecuta el script:

```powershell
.\DeviceReport.ps1
```

Si todo está bien configurado, cuando estés **fuera de la red del taller**, el script:

1. Se autenticará con Microsoft Graph API
2. Creará la carpeta en OneDrive (si no existe)
3. Subirá el archivo ZIP automáticamente

---

## 🛠️ Solución de Problemas

### Error: "ClientId no configurado"
- Verifica que hayas reemplazado `YOUR_CLIENT_ID_HERE` en `config.json`

### Error: "ClientSecret no configurado"
- Verifica que hayas reemplazado `YOUR_CLIENT_SECRET_HERE` en `config.json`

### Error: "No se pudo obtener el token de acceso"
- Verifica que el Client ID y Client Secret sean correctos
- Verifica que los permisos estén correctamente configurados
- Si usaste Application permissions, verifica que hayas dado consentimiento de administrador

### Error: "Access Denied" al subir archivos
- Verifica que hayas agregado el permiso `Files.ReadWrite.All`
- Verifica que el permiso tenga el checkmark verde (consentimiento otorgado)

---

## 📚 Referencias

- [Microsoft Graph API Documentation](https://docs.microsoft.com/en-us/graph/)
- [Azure AD App Registration](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
- [Microsoft Graph Permissions](https://docs.microsoft.com/en-us/graph/permissions-reference)

---

## 🔄 Renovación del Client Secret

Los Client Secrets expiran. Cuando esto suceda:

1. Ve a Azure Portal > Tu aplicación > Certificates & secrets
2. Elimina el secreto expirado
3. Crea uno nuevo siguiendo los pasos 5-6
4. Actualiza el `ClientSecret` en `config.json`

---

**¿Tienes problemas?** Consulta los logs del script o contacta al administrador del sistema.
