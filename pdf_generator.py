from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os
from database import get_db_connection

def draw_wrapped_text(c, text, x, y, max_width, line_height=12):
    lines = str(text).split('\n')
    for raw_line in lines:
        words = raw_line.split()
        current_line = ""
        for word in words:
            if c.stringWidth(current_line + word) < max_width:
                current_line += word + " "
            else:
                c.drawString(x, y, current_line.strip())
                y -= line_height
                current_line = word + " "
        if current_line:
            c.drawString(x, y, current_line.strip())
            y -= line_height
    return y

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
    
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    
    # Margins and Coordinates
    margin_x = 30
    margin_y = 30
    top_y = height - margin_y
    bottom_y = margin_y
    right_x = width - margin_x
    
    font_bold = "Helvetica-Bold"
    font_regular = "Helvetica"
    
    # Outer Border
    c.rect(margin_x, bottom_y, width - 2*margin_x, height - 2*margin_y)
    
    # Top Info (Contact & GST)
    c.setFont(font_bold, 14)
    contact_val = settings['phone'] if 'phone' in settings.keys() and settings['phone'] else ""
    if contact_val:
        c.drawString(margin_x + 5, top_y - 20, f"Ph: {contact_val}")
        
    gst_val = settings['gst_number'] if 'gst_number' in settings.keys() and settings['gst_number'] else ""
    if gst_val:
        c.drawRightString(right_x - 5, top_y - 20, f"GST NO: {gst_val}")
    
    # Shop Name
    c.setFont(font_bold, 32)
    store_name = settings['store_name'] if 'store_name' in settings.keys() else "STORE"
    c.drawCentredString(width/2.0, top_y - 50, str(store_name))
    
    # Shop Address Line
    c.line(margin_x, top_y - 65, right_x, top_y - 65)
    c.setFont(font_bold, 11)
    addr = settings['store_address'] if 'store_address' in settings.keys() else ""
    c.drawCentredString(width/2.0, top_y - 80, str(addr))
    
    # Details Section Line
    c.line(margin_x, top_y - 95, right_x, top_y - 95)
    y_details_top = top_y - 95
    
    # Party Details (Left side)
    c.setFont(font_bold, 16)
    c.drawString(margin_x + 10, y_details_top - 25, "CUSTOMER DETAILS")
    
    c.line(margin_x, y_details_top - 35, right_x, y_details_top - 35)
    
    c.setFont(font_bold, 11)
    c.drawString(margin_x + 10, y_details_top - 50, f"MR {str(bill['name'])}")
    c.setFont(font_regular, 10)
    draw_wrapped_text(c, bill['address'], margin_x + 10, y_details_top - 65, 280)
    if bill['phone']:
        c.drawString(margin_x + 10, y_details_top - 100, f"Phone: {bill['phone']}")
    
    # Middle Divider
    x_divider = width/2.0 + 50
    c.line(x_divider, y_details_top, x_divider, y_details_top - 180)
    
    # Invoice No / Date Divider
    x_subdivider = x_divider + 60
    c.line(x_subdivider, y_details_top, x_subdivider, y_details_top - 80)
    
    c.drawString(x_divider + 5, y_details_top - 20, "Invoice No:-")
    c.drawRightString(right_x - 5, y_details_top - 20, bill['bill_number'])
    c.line(x_divider, y_details_top - 40, right_x, y_details_top - 40)
    
    c.drawString(x_divider + 5, y_details_top - 60, "Date:-")
    c.drawRightString(right_x - 5, y_details_top - 60, bill['created_at'].split()[0])
    c.line(x_divider, y_details_top - 80, right_x, y_details_top - 80)
    
    # Table Header Line
    y_table_header = y_details_top - 180
    c.line(margin_x, y_table_header, right_x, y_table_header)
    
    # Table Columns
    cols = [
        {"name": "SNO", "width": 35},
        {"name": "Description Of Goods", "width": 275},
        {"name": "Qty", "width": 35},
        {"name": "Rate", "width": 70},
        {"name": "Amount", "width": 120}  # Will auto calc to remaining width
    ]
    cols[4]['width'] = right_x - margin_x - sum(c['width'] for c in cols[:-1])
    
    y_col_text = y_table_header - 15
    c.setFont(font_bold, 9)
    current_x = margin_x
    col_x_positions = []
    
    for col in cols:
        col_x_positions.append(current_x)
        c.drawCentredString(current_x + col['width']/2.0, y_col_text, col['name'])
        current_x += col['width']
    col_x_positions.append(right_x)
    
    y_table_data = y_table_header - 25
    c.line(margin_x, y_table_data, right_x, y_table_data)
    
    # Items
    y_item = y_table_data - 20
    c.setFont(font_regular, 11)
    for i, item in enumerate(items):
        c.drawCentredString(col_x_positions[0] + cols[0]['width']/2.0, y_item, str(i+1))
        qty_str = f"{item['quantity']} PCS"
        rate_str = f"{item['unit_price']:.2f}"
        amt_str = f"{item['total_price']:.2f}"
        
        draw_wrapped_text(c, item['product_name'], col_x_positions[1] + 10, y_item, cols[1]['width'] - 20, 14)
        c.drawCentredString(col_x_positions[2] + cols[2]['width']/2.0, y_item, qty_str)
        c.drawCentredString(col_x_positions[3] + cols[3]['width']/2.0, y_item, rate_str)
        c.drawCentredString(col_x_positions[4] + cols[4]['width']/2.0, y_item, amt_str)
        y_item -= 50
        
    y_totals_top = 220
    y_grand_total_bottom = y_totals_top - 72
    
    # Vertical Lines for columns
    for x_pos in col_x_positions[1:-1]:
        c.line(x_pos, y_table_header, x_pos, y_totals_top)
        
    c.line(margin_x, y_totals_top, right_x, y_totals_top)
    
    # Totals Box
    c.setFont(font_bold, 9)
    x_total_label = col_x_positions[3]
    
    c.drawCentredString(x_total_label + cols[3]['width']/2.0, y_totals_top - 12, "AMOUNT")
    c.drawCentredString(col_x_positions[4] + cols[4]['width']/2.0, y_totals_top - 12, f"{bill['base_amount']:.2f}")
    c.line(x_total_label, y_totals_top - 18, right_x, y_totals_top - 18)
    
    c.drawCentredString(x_total_label + cols[3]['width']/2.0, y_totals_top - 30, "CGST")
    c.drawCentredString(col_x_positions[4] + cols[4]['width']/2.0, y_totals_top - 30, f"{bill['cgst_amount']:.2f}")
    c.line(x_total_label, y_totals_top - 36, right_x, y_totals_top - 36)
    
    c.drawCentredString(x_total_label + cols[3]['width']/2.0, y_totals_top - 48, "SGST")
    c.drawCentredString(col_x_positions[4] + cols[4]['width']/2.0, y_totals_top - 48, f"{bill['sgst_amount']:.2f}")
    c.line(x_total_label, y_totals_top - 54, right_x, y_totals_top - 54)
    
    c.drawCentredString(x_total_label + cols[3]['width']/2.0, y_totals_top - 66, "GRAND TOTAL")
    c.drawCentredString(col_x_positions[4] + cols[4]['width']/2.0, y_totals_top - 66, f"{bill['total_amount']:.2f}")
    c.line(margin_x, y_grand_total_bottom, right_x, y_grand_total_bottom)
    
    # Left vertical line for totals box
    c.line(x_total_label, y_totals_top, x_total_label, y_grand_total_bottom)
    # Middle vertical line for totals box
    c.line(col_x_positions[4], y_totals_top, col_x_positions[4], y_grand_total_bottom)
    c.setFont("Helvetica-Bold", 8)    # Footer / Table Setup
    y_footer_line = bottom_y + 300
    y_totals_start = y_footer_line + 80
    
    # Table Grid Lines (Outer borders already handled, we draw vertical column lines)
    c.line(margin_x, y_table_header, margin_x, bottom_y) # Left outer (down to bottom)
    c.line(right_x, y_table_header, right_x, bottom_y) # Right outer (down to bottom)
    
    # SNO, Desc, Qty columns end at the start of Totals
    c.line(col_x_positions[1], y_table_header, col_x_positions[1], y_totals_start)
    c.line(col_x_positions[2], y_table_header, col_x_positions[2], y_totals_start)
    c.line(col_x_positions[3], y_table_header, col_x_positions[3], y_totals_start)
    
    # Rate and Amount separator continues down to the footer line
    c.line(col_x_positions[4], y_table_header, col_x_positions[4], y_footer_line)
    
    # Horizontal lines for Totals rows
    c.line(col_x_positions[3], y_totals_start, right_x, y_totals_start)
    c.line(col_x_positions[3], y_totals_start - 20, right_x, y_totals_start - 20)
    c.line(col_x_positions[3], y_totals_start - 40, right_x, y_totals_start - 40)
    c.line(col_x_positions[3], y_totals_start - 60, right_x, y_totals_start - 60)
    
    # The main horizontal line separating table from footer
    c.line(margin_x, y_footer_line, right_x, y_footer_line)
    
    # Footer Vertical Divider (Terms | Stamp)
    x_footer_divider = x_divider
    c.line(x_footer_divider, y_footer_line, x_footer_divider, bottom_y)
    
    # Totals Section Text
    x_totals_label = col_x_positions[3]
    x_totals_value = col_x_positions[4]
    
    c.setFont(font_bold, 11)
    
    # AMOUNT
    y = y_totals_start - 15
    c.drawCentredString(x_totals_label + (cols[3]['width']/2), y, "AMOUNT")
    c.drawRightString(right_x - 5, y, f"{bill['base_amount']:.2f}" if bill['base_amount'] else "0.00")
    
    # CGST
    y -= 20
    c.drawCentredString(x_totals_label + (cols[3]['width']/2), y, "CGST")
    c.drawRightString(right_x - 5, y, f"{bill['cgst_amount']:.2f}" if bill['cgst_amount'] else "0.00")
    
    # SGST
    y -= 20
    c.drawCentredString(x_totals_label + (cols[3]['width']/2), y, "SGST")
    c.drawRightString(right_x - 5, y, f"{bill['sgst_amount']:.2f}" if bill['sgst_amount'] else "0.00")
    
    # GRAND TOTAL
    y -= 20
    c.drawCentredString(x_totals_label + (cols[3]['width']/2), y, "GRAND TOTAL")
    c.drawRightString(right_x - 5, y, f"{bill['total_amount']:.2f}")
    
    # Terms and Conditions
    c.setFont(font_bold, 11)
    c.drawString(margin_x + 10, y_footer_line - 20, "Terms & Conditions")
    
    c.setFont(font_regular, 9)
    terms = settings['terms_conditions'] if 'terms_conditions' in settings.keys() else "1. Received the above goods in good conditions."
    draw_wrapped_text(c, terms, margin_x + 10, y_footer_line - 40, (x_footer_divider - margin_x) - 20, 12)
    
    # Stamp Box
    c.setFont(font_bold, 16)
    stamp_name = settings['stamp_name'] if 'stamp_name' in settings.keys() and settings['stamp_name'] else store_name
    c.drawCentredString(x_footer_divider + (right_x - x_footer_divider)/2.0, bottom_y + 20, stamp_name)
    
    c.save()
    return filepath
