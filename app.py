from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime
import os
import random
import string
from database import get_db_connection, init_db
from migrate_db import migrate
import sys

# Determine if running as a script or a frozen exe
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

# Initialize and migrate database
init_db()
migrate()

# Ensure invoices directory exists
os.makedirs("invoices", exist_ok=True)



@app.route('/')
@app.route('/new_bill')
def new_bill():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Auto-generate simple bill number
    cursor.execute("SELECT MAX(id) FROM Bills")
    max_id = cursor.fetchone()[0]
    next_id = max_id + 1 if max_id else 1
    bill_number = f"INV-{1000 + next_id}"
    
    cursor.execute("SELECT name FROM Categories ORDER BY name")
    categories = [row['name'] for row in cursor.fetchall()]
    cursor.execute("SELECT name FROM Brands ORDER BY name")
    brands = [row['name'] for row in cursor.fetchall()]
    cursor.execute("SELECT tax_rate FROM Settings LIMIT 1")
    settings = cursor.fetchone()
    tax_rate = settings['tax_rate'] if settings else 18.0
    conn.close()
    
    return render_template('new_bill.html', bill_number=bill_number, current_datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), categories=categories, brands=brands, tax_rate=tax_rate)

@app.route('/api/save_bill', methods=['POST'])
def save_bill():
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if customer exists
        cursor.execute("SELECT id FROM Customers WHERE phone = ?", (data['customer']['phone'],))
        customer = cursor.fetchone()
        
        if customer:
            customer_id = customer['id']
            # Update customer details
            cursor.execute("UPDATE Customers SET name = ?, address = ? WHERE id = ?", 
                           (data['customer']['name'], data['customer']['address'], customer_id))
        else:
            # Insert new customer
            cursor.execute("INSERT INTO Customers (name, phone, address) VALUES (?, ?, ?)",
                           (data['customer']['name'], data['customer']['phone'], data['customer']['address']))
            customer_id = cursor.lastrowid
            
        # Insert Bill
        cursor.execute("""
            INSERT INTO Bills (bill_number, customer_id, total_amount, base_amount, cgst_amount, sgst_amount, finance_by, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (data['bill_number'], customer_id, data['total_amount'], data.get('base_amount', 0), data.get('cgst_amount', 0), data.get('sgst_amount', 0), data.get('finance_by', ''), datetime.now()))
        bill_id = cursor.lastrowid
        
        # Insert Bill Items
        for item in data['items']:
            cursor.execute("""
                INSERT INTO Bill_Items (bill_id, product_name, brand, category, hsn_code, quantity, unit_price, total_price) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (bill_id, item['product_name'], item['brand'], item.get('category', ''), item.get('hsn_code', ''), item['quantity'], item['unit_price'], item['total_price']))
            
        conn.commit()
        
        try:
            # Here we will call the PDF generation
            from pdf_generator import generate_invoice
            pdf_path = generate_invoice(bill_id)
        except Exception as e:
            print(f"Warning: PDF generation failed during save: {e}")
        
        conn.close()
        return jsonify({"success": True, "bill_id": bill_id, "pdf_url": f"/download_pdf/{bill_id}"})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "error": str(e)})

@app.route('/history')
def history():
    return render_template('bill_history.html')

@app.route('/api/bills')
def api_bills():
    search = request.args.get('search', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT Bills.id, Bills.bill_number, Bills.total_amount, Bills.created_at, Customers.name, Customers.phone 
        FROM Bills 
        JOIN Customers ON Bills.customer_id = Customers.id
        WHERE Bills.bill_number LIKE ? OR Customers.name LIKE ? OR Customers.phone LIKE ?
        ORDER BY Bills.created_at DESC
    """
    search_param = f"%{search}%"
    cursor.execute(query, (search_param, search_param, search_param))
    bills = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify(bills)

@app.route('/download_pdf/<int:bill_id>')
def download_pdf(bill_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT bill_number FROM Bills WHERE id = ?", (bill_id,))
    bill = cursor.fetchone()
    conn.close()
    
    if bill:
        pdf_path = os.path.join(os.getcwd(), 'invoices', f"{bill['bill_number']}.pdf")
        if not os.path.exists(pdf_path):
            try:
                from pdf_generator import generate_invoice
                generate_invoice(bill_id)
            except Exception as e:
                print(f"Failed to generate PDF on the fly: {e}")
                
        if os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True)
    
    return "PDF not found", 404

@app.route('/print_bill/<int:bill_id>')
def print_bill(bill_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM Settings LIMIT 1")
    settings = cursor.fetchone()
    
    cursor.execute("""
        SELECT Bills.*, Customers.name, Customers.phone, Customers.address 
        FROM Bills 
        JOIN Customers ON Bills.customer_id = Customers.id
        WHERE Bills.id = ?
    """, (bill_id,))
    bill = cursor.fetchone()
    
    cursor.execute("SELECT * FROM Bill_Items WHERE bill_id = ?", (bill_id,))
    items = cursor.fetchall()
    
    conn.close()
    
    if not bill:
        return "Bill not found", 404
        
    settings_dict = dict(settings) if settings else {}
    bill_dict = dict(bill) if bill else {}
    items_list = [dict(i) for i in items]
    
    template_name = 'print_bill_modern.html' if settings_dict.get('bill_template') == 'modern' else 'print_bill.html'
    return render_template(template_name, settings=settings_dict, bill=bill_dict, items=items_list)

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/api/analytics_data')
def api_analytics_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Top selling categories
    cursor.execute("""
        SELECT COALESCE(NULLIF(category, ''), 'Unknown') as category_name, SUM(quantity) as total_qty, SUM(total_price) as total_revenue
        FROM Bill_Items
        GROUP BY COALESCE(NULLIF(category, ''), 'Unknown')
        ORDER BY total_qty DESC
        LIMIT 5
    """)
    top_categories = [dict(row) for row in cursor.fetchall()]
    
    # Top selling brands
    cursor.execute("""
        SELECT COALESCE(NULLIF(brand, ''), 'Unknown') as brand_name, SUM(quantity) as total_qty, SUM(total_price) as total_revenue
        FROM Bill_Items
        GROUP BY COALESCE(NULLIF(brand, ''), 'Unknown')
        ORDER BY total_qty DESC
        LIMIT 5
    """)
    top_brands = [dict(row) for row in cursor.fetchall()]
    
    # Daily sales for the last 7 days
    cursor.execute("""
        SELECT date(created_at) as date, SUM(total_amount) as revenue
        FROM Bills
        WHERE created_at >= date('now', '-7 days')
        GROUP BY date(created_at)
        ORDER BY date(created_at)
    """)
    daily_sales = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({"top_categories": top_categories, "top_brands": top_brands, "daily_sales": daily_sales})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        store_name = request.form['store_name']
        store_address = request.form['store_address']
        phone = request.form['phone']
        gst_number = request.form['gst_number']
        email = request.form.get('email', '')
        owner_name = request.form.get('owner_name', '')
        terms_conditions = request.form.get('terms_conditions', '')
        stamp_name = request.form.get('stamp_name', '')
        bill_template = request.form.get('bill_template', 'standard')
        try:
            tax_rate = float(request.form.get('tax_rate', 18.0))
        except ValueError:
            tax_rate = 18.0
        
        cursor.execute("""
            UPDATE Settings 
            SET store_name = ?, store_address = ?, phone = ?, gst_number = ?,
                email = ?, owner_name = ?, terms_conditions = ?, stamp_name = ?, tax_rate = ?, bill_template = ?
            WHERE id = (SELECT id FROM Settings LIMIT 1)
        """, (store_name, store_address, phone, gst_number, email, owner_name, terms_conditions, stamp_name, tax_rate, bill_template))
        conn.commit()
        
    cursor.execute("SELECT * FROM Settings LIMIT 1")
    settings_data = cursor.fetchone()
    
    cursor.execute("SELECT * FROM Categories ORDER BY name")
    categories = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Brands ORDER BY name")
    brands = cursor.fetchall()
    
    conn.close()
    
    settings_dict = dict(settings_data) if settings_data else {}
    return render_template('settings.html', settings=settings_dict, categories=categories, brands=brands)

@app.route('/api/add_category', methods=['POST'])
def add_category():
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required"})
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Categories (name) VALUES (?)", (name,))
        conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Category already exists"})
    finally:
        conn.close()

@app.route('/api/delete_category/<int:cat_id>', methods=['DELETE'])
def delete_category(cat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/add_brand', methods=['POST'])
def add_brand():
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required"})
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Brands (name) VALUES (?)", (name,))
        conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Brand already exists"})
    finally:
        conn.close()

@app.route('/api/delete_brand/<int:brand_id>', methods=['DELETE'])
def delete_brand(brand_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Brands WHERE id = ?", (brand_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

import webview
import shutil
import os

class AppApi:
    def save_pdf(self, bill_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bill_number FROM Bills WHERE id = ?", (bill_id,))
        bill = cursor.fetchone()
        conn.close()
        
        if bill:
            pdf_path = os.path.join(os.getcwd(), 'invoices', f"{bill['bill_number']}.pdf")
            if os.path.exists(pdf_path):
                window = webview.windows[0]
                save_filename = window.create_file_dialog(
                    webview.SAVE_DIALOG, 
                    directory=os.getcwd(), 
                    save_filename=f"{bill['bill_number']}.pdf"
                )
                if save_filename:
                    if isinstance(save_filename, tuple) or isinstance(save_filename, list):
                        save_filename = save_filename[0]
                    shutil.copy(pdf_path, save_filename)
                    return True
        return False

if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        webview.create_window('Electronics Billing', app, js_api=AppApi())
        webview.start()
    else:
        app.run(debug=True, port=5000)
