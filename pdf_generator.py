import os
from flask import render_template
from playwright.sync_api import sync_playwright
from database import get_db_connection

def generate_invoice(bill_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch Settings
    cursor.execute("SELECT * FROM Settings LIMIT 1")
    settings = cursor.fetchone()
    if not settings:
        settings = {}
    
    # Fetch Bill and Customer Info
    cursor.execute("""
        SELECT Bills.*, Customers.name, Customers.phone, Customers.address 
        FROM Bills 
        JOIN Customers ON Bills.customer_id = Customers.id
        WHERE Bills.id = ?
    """, (bill_id,))
    bill = cursor.fetchone()
    
    # Fetch Bill Items
    cursor.execute("SELECT * FROM Bill_Items WHERE bill_id = ?", (bill_id,))
    items = cursor.fetchall()
    
    conn.close()
    
    if not bill:
        return None

    filename = f"{bill['bill_number']}.pdf"
    filepath = os.path.join("invoices", filename)
    
    # Render the HTML template with the fetched data
    html_string = render_template('print_bill.html', settings=settings, bill=bill, items=items)
    
    # Generate PDF using Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_string)
        page.pdf(
            path=filepath, 
            format="A4", 
            print_background=True,
            scale=0.9,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"}
        )
        browser.close()
    
    return filepath

