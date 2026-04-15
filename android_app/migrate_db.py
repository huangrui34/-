import sqlite3
import os

# Define database paths relative to the script's location or as absolute paths
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_paths = [
    os.path.join(base_dir, "backend_server", "tv_launcher.db"),
    # Keep old paths just in case
    r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\backend\tv_launcher.db",
]

def migrate(db_path):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}, skipping.")
        return

    print(f"Migrating database at {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        if not cursor.fetchone():
            print("Table 'devices' not found, skipping.")
            conn.close()
            return

        cursor.execute("PRAGMA table_info(devices)")
        columns = [col[1] for col in cursor.fetchall()]

        new_columns = {
            "installed_apps": "TEXT",
            "wifi_ip": "VARCHAR(64)",
            "eth_ip": "VARCHAR(64)",
            "wifi_mac": "VARCHAR(32)",
            "eth_mac": "VARCHAR(32)",
            "network_ssid": "VARCHAR(128)",
            "room_name": "VARCHAR(128)",
            "ram_usage": "VARCHAR(64)",
            "storage_usage": "VARCHAR(64)"
        }

        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                print(f"Adding {col_name} column to devices table...")
                cursor.execute(f"ALTER TABLE devices ADD COLUMN {col_name} {col_type}")
                conn.commit()
            else:
                print(f"Column {col_name} already exists.")

        conn.close()
        print(f"Migration for {db_path} finished.")
    except Exception as e:
        print(f"Error migrating database {db_path}: {e}")

def migrate_operation_logs(db_path):
    if not os.path.exists(db_path):
        return

    print(f"Checking operation_logs table at {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='operation_logs'")
        if cursor.fetchone():
            conn.close()
            return

        cursor.execute("""
            CREATE TABLE operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                device_name VARCHAR(128),
                action VARCHAR(64) NOT NULL,
                detail TEXT,
                operator VARCHAR(128) DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        print(f"Operation logs table created at {db_path}.")
    except Exception as e:
        print(f"Error creating operation_logs table at {db_path}: {e}")

for path in db_paths:
    migrate(path)
    migrate_operation_logs(path)
