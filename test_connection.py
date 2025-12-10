import os
import sys
import pyodbc
import re

# Add src to path to import our server module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mssql_mcp_server.server import get_connection_string

try:
    print("Loading database configuration from environment variables...")
    conn_str = get_connection_string()
    
    # Mask sensitive information for display
    safe_conn_str = re.sub(r'PWD=[^;]+', 'PWD=***', conn_str)
    print(f"Connection String: {safe_conn_str}")
    
    print("\nAttempting to connect to SQL Server...")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    print("Connection successful!")
    
    print("\nTesting query execution...")
    cursor.execute("SELECT TOP 5 TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} tables:")
    for row in rows:
        print(f"  - {row[0]}")
    
    cursor.close()
    conn.close()
    print("\nConnection test completed successfully!")
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
