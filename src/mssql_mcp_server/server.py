import asyncio
import logging
import os
import re
import pyodbc
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
from pydantic import AnyUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mssql_mcp_server")

def validate_table_name(table_name: str) -> str:
    """Validate and escape table name to prevent SQL injection."""
    # Allow only alphanumeric, underscore, and dot (for schema.table)
    if not re.match(r'^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)?$', table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    
    # Split schema and table if present
    parts = table_name.split('.')
    if len(parts) == 2:
        # Escape both schema and table name
        return f"[{parts[0]}].[{parts[1]}]"
    else:
        # Just table name
        return f"[{table_name}]"

def get_connection_string():
    """Get database connection string from environment variables."""
    server = os.getenv("MSSQL_SERVER", "localhost")
    database = os.getenv("MSSQL_DATABASE")
    user = os.getenv("MSSQL_USER")
    password = os.getenv("MSSQL_PASSWORD")
    port = os.getenv("MSSQL_PORT", "1433")
    
    # Handle LocalDB
    if server.startswith("(localdb)\\"):
        # For ODBC, LocalDB format is typically (localdb)\InstanceName
        pass # pyodbc handles this usually
    
    logger.info(f"Using server: {server}")

    # Build connection string
    # Try using 'ODBC Driver 17 for SQL Server' as default
    driver = "{ODBC Driver 17 for SQL Server}"
    
    # Check if we should fallback to standard 'SQL Server' driver (often pre-installed on Windows)
    # Ideally we'd scan available drivers, but for now let's try a robust default approach
    # We can also check pyodbc.drivers() if needed, but let's stick to simple env config first.
    
    # Check if user specified a driver
    env_driver = os.getenv("MSSQL_DRIVER")
    if env_driver:
        driver = f"{{{env_driver}}}"
    
    conn_str = f"DRIVER={driver};SERVER={server},{port};DATABASE={database}"
    
    if os.getenv("MSSQL_WINDOWS_AUTH", "false").lower() == "true":
         conn_str += ";Trusted_Connection=yes"
    else:
        if not user or not password:
             raise ValueError("MSSQL_USER and MSSQL_PASSWORD are required for SQL Authentication")
        conn_str += f";UID={user};PWD={password}"
    
    # Add encryption if requested
    if os.getenv("MSSQL_ENCRYPT", "false").lower() == "true":
        conn_str += ";Encrypt=yes"
        if os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "false").lower() == "true":
             conn_str += ";TrustServerCertificate=yes"
             
    return conn_str

def get_command():
    """Get the command to execute SQL queries."""
    return os.getenv("MSSQL_COMMAND", "execute_sql")

def is_select_query(query: str) -> bool:
    """
    Check if a query is a SELECT statement, accounting for comments.
    Handles both single-line (--) and multi-line (/* */) SQL comments.
    """
    # Remove multi-line comments /* ... */
    query_cleaned = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
    
    # Remove single-line comments -- ...
    lines = query_cleaned.split('\n')
    cleaned_lines = []
    for line in lines:
        # Find -- comment marker and remove everything after it
        comment_pos = line.find('--')
        if comment_pos != -1:
            line = line[:comment_pos]
        cleaned_lines.append(line)
    
    query_cleaned = '\n'.join(cleaned_lines)
    
    # Get the first non-empty word after stripping whitespace
    first_word = query_cleaned.strip().split()[0] if query_cleaned.strip() else ""
    return first_word.upper() == "SELECT"

# Global connection handler
class DBConnection:
    _conn = None
    
    @classmethod
    def get_connection(cls):
        conn_str = get_connection_string()
        # If no connection or closed, connect
        if cls._conn is None:
            logger.info("Initializing new persistent connection...")
            cls._conn = pyodbc.connect(conn_str)
        else:
            # Check if connection is still alive using a lightweight valid check
            try:
                # Need to verify if the connection is really open. 
                # Pyodbc doesn't have a reliable .open property that checks network state.
                # We'll try a fast no-op query.
                cursor = cls._conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchall() # Consume result
                cursor.close()
            except Exception as e:
                logger.warning(f"Connection lost ({e}), reconnecting...")
                try:
                    cls._conn.close()
                except:
                    pass
                cls._conn = pyodbc.connect(conn_str)
        
        return cls._conn


# Initialize server
app = Server("mssql_mcp_server")

@app.list_resources()
async def list_resources() -> list[Resource]:
    """List SQL Server tables as resources."""
    try:
        conn = DBConnection.get_connection()
        cursor = conn.cursor()
        # Query to get user tables from the current database
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        tables = cursor.fetchall()
        logger.info(f"Found tables: {tables}")
        
        resources = []
        for table in tables:
            resources.append(
                Resource(
                    uri=f"mssql://{table[0]}/data",
                    name=f"Table: {table[0]}",
                    mimeType="text/plain",
                    description=f"Data in table: {table[0]}"
                )
            )
        cursor.close()
        # Do not close global conn
        return resources
    except Exception as e:
        logger.error(f"Failed to list resources: {str(e)}")
        return []

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Read table contents."""
    uri_str = str(uri)
    logger.info(f"Reading resource: {uri_str}")
    
    if not uri_str.startswith("mssql://"):
        raise ValueError(f"Invalid URI scheme: {uri_str}")
        
    parts = uri_str[8:].split('/')
    table = parts[0]
    
    try:
        # Validate table name to prevent SQL injection
        safe_table = validate_table_name(table)
        
        conn = DBConnection.get_connection()
        cursor = conn.cursor()
        # Use TOP 100 for MSSQL (equivalent to LIMIT in MySQL)
        cursor.execute(f"SELECT TOP 100 * FROM {safe_table}")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        result = [",".join(map(str, row)) for row in rows]
        cursor.close()
        # Do not close global conn
        return "\n".join([",".join(columns)] + result)
                
    except Exception as e:
        logger.error(f"Database error reading resource {uri}: {str(e)}")
        raise RuntimeError(f"Database error: {str(e)}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available SQL Server tools."""
    command = get_command()
    logger.info("Listing tools...")
    return [
        Tool(
            name=command,
            description="Execute an SQL query on the SQL Server",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute SQL commands."""
    command = get_command()
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    if name != command:
        raise ValueError(f"Unknown tool: {name}")
    
    query = arguments.get("query")
    if not query:
        raise ValueError("Query is required")
    
    try:
        conn = DBConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Special handling for table listing
        if is_select_query(query) and "INFORMATION_SCHEMA.TABLES" in query.upper():
            tables = cursor.fetchall()
            # Need to get database name differently or parse it from conn string, 
            # but simpler to just use generic header or omit
            result = ["Tables_found"] 
            result.extend([table[0] for table in tables])
            cursor.close()
            # Do not close global conn
            return [TextContent(type="text", text="\n".join(result))]
        
        # Regular SELECT queries
        elif is_select_query(query):
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            result = [",".join(map(str, row)) for row in rows]
            cursor.close()
            # Do not close global conn
            return [TextContent(type="text", text="\n".join([",".join(columns)] + result))]
        
        # Non-SELECT queries
        else:
            conn.commit()
            affected_rows = cursor.rowcount
            cursor.close()
            # Do not close global conn
            return [TextContent(type="text", text=f"Query executed successfully. Rows affected: {affected_rows}")]
                
    except Exception as e:
        logger.error(f"Error executing SQL '{query}': {e}")
        return [TextContent(type="text", text=f"Error executing query: {str(e)}")]

async def main():
    """Main entry point to run the MCP server."""
    from mcp.server.stdio import stdio_server
    
    logger.info("Starting MSSQL MCP server...")
    conn_str = get_connection_string()
    # Log connection info (sanitize password for logs)
    safe_conn_str = re.sub(r'PWD=[^;]+', 'PWD=***', conn_str)
    logger.info(f"Database connection string: {safe_conn_str}")
    
    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())
