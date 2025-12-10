# Microsoft SQL Server MCP Server

Un servidor personalizado para MCP (Model Context Protocol) que permite conectar tu asistente de IA (Claude, Windsurf, Cursor) con tu base de datos Microsoft SQL Server.

## Características

*   **Consultas Naturales:** Pregunta cosas como "¿Cuántos usuarios hay?" y el servidor ejecutará el SQL por ti.
*   **Solo Lectura (Seguro):** Diseñado para inspección y análisis.
*   **Optimizado:** Mantiene una conexión persistente para respuestas instantáneas.
*   **Compatible:** Funciona con Windsurf y Cursor.

## Requisitos

*   Python 3.11 o superior.
*   Driver ODBC para SQL Server 17 (o superior) instalado en Windows.
*   Acceso a una base de datos SQL Server.

## Instalación

1.  Clona este repositorio.
2.  Crea un entorno virtual e instala las dependencias:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
```

## Configuración

Debes configurar las credenciales de tu base de datos en las variables de entorno dentro de la configuración de tu editor.

### 1. Windsurf

Edita tu archivo de configuración de MCP en Windsurf (Generalmente en `%APPDATA%\Windsurf\Config\mcp_config.json` o accesible desde el menú de configuración de MCP).

Añade lo siguiente:

```json
{
  "mcpServers": {
    "sqlServer": {
      "command": "C:\\Ruta\\A\\Tu\\Repo\\venv\\Scripts\\python.exe",
      "args": ["-m", "mssql_mcp_server"],
      "env": {
        "MSSQL_SERVER": "TU_IP_O_HOST",
        "MSSQL_DATABASE": "NOMBRE_BASE_DE_DATOS",
        "MSSQL_USER": "TU_USUARIO",
        "MSSQL_PASSWORD": "TU_CONTRASEÑA",
        "MSSQL_ENCRYPT": "true",
        "MSSQL_TRUST_SERVER_CERTIFICATE": "true",
        "PYTHONPATH": "C:\\Ruta\\A\\Tu\\Repo\\src"
      }
    }
  }
}
```

> **IMPORTANTE:** Reemplaza `C:\\Ruta\\A\\Tu\\Repo` con la ruta absoluta donde clonaste este proyecto. Asegúrate de usar doble barra invertida `\\` en Windows.

### 2. Antigravity (Gemini)

Edita el archivo de configuración de MCP en Antigravity para añadir el servidor.

1.  Localiza el archivo de configuración en:
    `C:\Users\<TU_USUARIO>\.gemini\antigravity\mcp_config.json`

2.  Añade la configuración del servidor dentro del objeto `mcpServers`. Si el archivo ya tiene otros servidores (como `perplexity-ask`), añade `sqlServer` como una nueva clave.

```json
{
  "mcpServers": {
    "sqlServer": {
      "command": "C:\\Ruta\\A\\Tu\\Repo\\venv\\Scripts\\python.exe",
      "args": ["-m", "mssql_mcp_server"],
      "env": {
        "MSSQL_SERVER": "TU_IP_O_HOST",
        "MSSQL_DATABASE": "NOMBRE_BASE_DE_DATOS",
        "MSSQL_USER": "TU_USUARIO",
        "MSSQL_PASSWORD": "TU_CONTRASEÑA",
        "MSSQL_ENCRYPT": "true",
        "MSSQL_TRUST_SERVER_CERTIFICATE": "true",
        "PYTHONPATH": "C:\\Ruta\\A\\Tu\\Repo\\src"
      }
    }
  }
}
```

> **NOTA:** Asegúrate de que las rutas al ejecutable de Python y al repositorio sean correctas y absolutas.

## Desarrollo y Pruebas

Para probar la conexión sin el asistente, usa el script incluido:

```powershell
# Configura las variables en la sesión temporalmente
$env:MSSQL_SERVER="tu_ip"
$env:MSSQL_DATABASE="tu_db"
# ... resto de variables ...

# Ejecuta el test
python test_connection.py
```