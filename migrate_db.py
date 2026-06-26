import sqlite3
import os

DB_NAME = "instance/billing.db"

def migrate():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Add columns to Settings
    try: cursor.execute('ALTER TABLE Settings ADD COLUMN email TEXT DEFAULT ""')
    except: pass
    try: cursor.execute('ALTER TABLE Settings ADD COLUMN owner_name TEXT DEFAULT ""')
    except: pass
    try: cursor.execute('ALTER TABLE Settings ADD COLUMN terms_conditions TEXT DEFAULT "1. Goods once sold cannot be returned. 2. Subject to local jurisdiction."')
    except: pass
    try: cursor.execute('ALTER TABLE Settings ADD COLUMN stamp_name TEXT DEFAULT ""')
    except: pass
    try: cursor.execute('ALTER TABLE Settings ADD COLUMN tax_rate REAL DEFAULT 18.0')
    except: pass
    try: cursor.execute('ALTER TABLE Settings ADD COLUMN bill_template TEXT DEFAULT "standard"')
    except: pass

    # Add columns to Bills
    try: cursor.execute('ALTER TABLE Bills ADD COLUMN finance_by TEXT DEFAULT ""')
    except: pass
    try: cursor.execute('ALTER TABLE Bills ADD COLUMN base_amount REAL DEFAULT 0.0')
    except: pass
    try: cursor.execute('ALTER TABLE Bills ADD COLUMN cgst_amount REAL DEFAULT 0.0')
    except: pass
    try: cursor.execute('ALTER TABLE Bills ADD COLUMN sgst_amount REAL DEFAULT 0.0')
    except: pass
    
    # Add columns to Bill_Items
    try: cursor.execute('ALTER TABLE Bill_Items ADD COLUMN hsn_code TEXT DEFAULT ""')
    except: pass
    try: cursor.execute('ALTER TABLE Bill_Items ADD COLUMN category TEXT DEFAULT ""')
    except: pass

    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
    print("Migration successful.")
