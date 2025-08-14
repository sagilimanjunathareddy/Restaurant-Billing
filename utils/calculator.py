

def calculate_bill(items, gst_percent=5.0, discount_percent=0.0):
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    gst = subtotal * (gst_percent / 100)
    discount = subtotal * (discount_percent / 100)
    total = subtotal + gst - discount
    return {
        "subtotal": round(subtotal, 2),
        "gst": round(gst, 2),
        "discount": round(discount, 2),
        "total": round(total, 2)
    }
