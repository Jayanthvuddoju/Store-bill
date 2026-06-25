import sqlite3
import os

DB_NAME = "instance/billing.db"

def get_db_connection():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT NOT NULL,
            store_address TEXT NOT NULL,
            phone TEXT NOT NULL,
            gst_number TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            total_amount REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES Customers(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Bill_Items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            brand TEXT,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            FOREIGN KEY(bill_id) REFERENCES Bills(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('SELECT COUNT(*) FROM Settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO Settings (store_name, store_address, phone, gst_number)
            VALUES (?, ?, ?, ?)
        ''', ('Electronics Store', '123 Main St, City', '123-456-7890', ''))

    cursor.execute('SELECT COUNT(*) FROM Categories')
    if cursor.fetchone()[0] == 0:
        default_categories = ['TV', 'AC', 'Refrigerator', 'Washing Machine', 'Laptop', 'Mobile Phone']
        for cat in default_categories:
            cursor.execute('INSERT INTO Categories (name) VALUES (?)', (cat,))

    cursor.execute('SELECT COUNT(*) FROM Brands')
    if cursor.fetchone()[0] == 0:
        default_brands = ['LG', 'Samsung', 'IFB', 'Haier', 'Lloyd', 'Sony', 'Whirlpool']
        for brand in default_brands:
            cursor.execute('INSERT INTO Brands (name) VALUES (?)', (brand,))

    conn.commit()
    conn.close()

init_db()
