def safe_int(value, default=0, nullable=False):
    if value is None or str(value).strip() == '':
        return None if nullable else default
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return None if nullable else default

def safe_float(value, default=0.0, nullable=False):
    if value is None or str(value).strip() == '':
        return None if nullable else default
    try:
        return float(str(value).strip())
    except ValueError:
        return None if nullable else default

def format_payment_method(val):
    if not val:
        return 'Desconocido'
    methods = {
        'cash': 'Efectivo',
        'card': 'Tarjeta (Visa/Mastercard)',
        'yape': 'Yape',
        'plin': 'Plin',
        'transfer': 'Transferencia'
    }
    return methods.get(val.lower(), val.upper())
