from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import os

def generate_pdf_bill(order_items, bill_summary, filename="final_bill.pdf"):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, y, "Restaurant Final Bill")
    y -= 30

    c.setFont("Helvetica", 12)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.drawString(50, y, f"Date: {now}")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Item")
    c.drawString(250, y, "Qty")
    c.drawString(300, y, "Price")
    y -= 20

    c.setFont("Helvetica", 12)
    for item in order_items:
        c.drawString(50, y, item['name'])
        c.drawString(250, y, str(item['quantity']))
        total_price = item['price'] * item['quantity']
        c.drawString(300, y, f"₹{total_price:.2f}")
        y -= 20

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Subtotal: ₹{bill_summary['subtotal']:.2f}")
    y -= 20
    c.drawString(50, y, f"GST: ₹{bill_summary['gst']:.2f}")
    y -= 20
    c.drawString(50, y, f"Discount: ₹{bill_summary['discount']:.2f}")
    y -= 20
    c.drawString(50, y, f"TOTAL: ₹{bill_summary['total']:.2f}")

    c.save()
    os.startfile(filename)  # Opens the PDF on Windows
