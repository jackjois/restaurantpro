-- ==========================================================
-- ESTRUCTURA COMPLETA DE BASE DE DATOS: RESTAURANTPRO
-- Motor: PostgreSQL 17 (Supabase)
-- Última actualización: Abril 2026
-- ==========================================================

-- --------------------------------------------------------
-- 1. Tabla `categories`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    color VARCHAR(20) DEFAULT '#007bff',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------
-- 2. Tabla `users`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(120) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'waiter',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------
-- 3. Tabla `settings`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) DEFAULT 'RestaurantPro',
    subtitle VARCHAR(150) DEFAULT 'Sistema POS',
    ruc VARCHAR(20) DEFAULT '',
    address VARCHAR(200) DEFAULT '',
    phone VARCHAR(50) DEFAULT '',
    thank_you_message VARCHAR(200) DEFAULT '¡Gracias por su preferencia!',
    logo_url VARCHAR(255)
);

-- --------------------------------------------------------
-- 4. Tabla `tables`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS tables (
    id SERIAL PRIMARY KEY,
    number INTEGER NOT NULL UNIQUE,
    capacity INTEGER NOT NULL DEFAULT 4,
    status VARCHAR(50) DEFAULT 'free',
    location VARCHAR(100),
    qr_code VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------
-- 5. Tabla `products`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    price NUMERIC(10,2) DEFAULT 0.00,
    cost NUMERIC(10,2) DEFAULT 0.00,
    image_url VARCHAR(255),
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    is_available BOOLEAN DEFAULT TRUE,
    track_stock BOOLEAN DEFAULT FALSE,
    stock INTEGER DEFAULT 0,
    preparation_time INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);

-- --------------------------------------------------------
-- 6. Tabla `orders`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    table_id INTEGER REFERENCES tables(id),
    user_id INTEGER REFERENCES users(id),
    order_type VARCHAR(50) DEFAULT 'dine_in',
    customer_name VARCHAR(100),
    customer_phone VARCHAR(50),
    delivery_address TEXT,
    delivery_fee NUMERIC(10,2) DEFAULT 0.00,
    order_number VARCHAR(50) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount NUMERIC(10,2) DEFAULT 0.00,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_order_type CHECK (order_type IN ('dine_in', 'takeaway', 'delivery')),
    CONSTRAINT chk_order_status CHECK (status IN ('pending', 'preparing', 'ready', 'served', 'paid', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);

-- --------------------------------------------------------
-- 7. Tabla `order_items`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(10,2),
    subtotal NUMERIC(10,2),
    status VARCHAR(50) DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_order_item_status CHECK (status IN ('pending', 'preparing', 'ready', 'delivered', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_order_items_status ON order_items(status);

-- --------------------------------------------------------
-- 8. Tabla `cash_sessions`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS cash_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    opening_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closing_time TIMESTAMPTZ,
    opening_amount NUMERIC(10,2) NOT NULL,
    closing_amount NUMERIC(10,2),
    expected_amount NUMERIC(10,2),
    status VARCHAR(50) DEFAULT 'open',
    CONSTRAINT chk_cash_session_status CHECK (status IN ('open', 'closed'))
);

-- --------------------------------------------------------
-- 9. Tabla `cash_expenses`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS cash_expenses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    cash_session_id INTEGER REFERENCES cash_sessions(id),
    amount NUMERIC(10,2) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------
-- 10. Tabla `payments`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    amount NUMERIC(10,2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    reference_code VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',
    created_by INTEGER REFERENCES users(id),
    cash_session_id INTEGER REFERENCES cash_sessions(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_payment_method CHECK (payment_method IN ('cash', 'card', 'yape', 'plin', 'transfer')),
    CONSTRAINT chk_payment_status CHECK (status IN ('pending', 'completed', 'failed', 'refunded'))
);

CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(created_at);
CREATE INDEX IF NOT EXISTS idx_payments_created_by ON payments(created_by);

-- --------------------------------------------------------
-- 11. Tabla `invoices`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER REFERENCES payments(id),
    invoice_type VARCHAR(50) NOT NULL,
    document_number VARCHAR(50) UNIQUE,
    customer_name VARCHAR(150),
    customer_document VARCHAR(50),
    customer_address TEXT,
    subtotal NUMERIC(10,2),
    tax_amount NUMERIC(10,2),
    total_amount NUMERIC(10,2),
    pdf_path VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_invoice_type CHECK (invoice_type IN ('boleta', 'factura'))
);

-- --------------------------------------------------------
-- 12. Tabla `notifications`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) DEFAULT 'system',
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);

-- --------------------------------------------------------
-- 13. Tabla `audit_logs`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    details TEXT,
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);

-- --------------------------------------------------------
-- 14. Tabla `app_signals` (Supabase Realtime)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_signals (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    entity VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
);

-- --------------------------------------------------------
-- SECUENCIAS DE NEGOCIO
-- --------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS order_number_seq START 1;
CREATE SEQUENCE IF NOT EXISTS boleta_seq START 1;
CREATE SEQUENCE IF NOT EXISTS factura_seq START 1;

-- --------------------------------------------------------
-- ROW LEVEL SECURITY (RLS)
-- --------------------------------------------------------
-- Habilitar RLS en todas las tablas
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tables ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_signals ENABLE ROW LEVEL SECURITY;

-- Políticas: acceso completo para postgres (backend Flask)
DO $$ 
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY['categories','users','settings','tables','products','orders','order_items','cash_sessions','cash_expenses','payments','invoices','notifications','audit_logs','app_signals'])
  LOOP
    -- Postgres no soporta "CREATE POLICY IF NOT EXISTS", así que lo hacemos idempotente vía pg_policies.
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies p
      WHERE p.schemaname='public' AND p.tablename=t AND p.policyname='service_role_full_access'
    ) THEN
      EXECUTE format('CREATE POLICY service_role_full_access ON public.%I FOR ALL TO postgres USING (true) WITH CHECK (true)', t);
    END IF;
  END LOOP;
END $$;

-- Política: anon solo puede leer app_signals (para Supabase Realtime)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies p
    WHERE p.schemaname='public' AND p.tablename='app_signals' AND p.policyname='anon_read_signals'
  ) THEN
    EXECUTE 'CREATE POLICY anon_read_signals ON public.app_signals FOR SELECT TO anon USING (true)';
  END IF;
END $$;

-- --------------------------------------------------------
-- TRIGGER: Auto-limpieza de app_signals (mantener 24h)
-- --------------------------------------------------------
CREATE OR REPLACE FUNCTION clean_old_app_signals()
RETURNS trigger AS $$
BEGIN
  DELETE FROM public.app_signals WHERE created_at < NOW() - INTERVAL '24 hours';
  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = public;

DROP TRIGGER IF EXISTS trg_clean_old_signals ON public.app_signals;
CREATE TRIGGER trg_clean_old_signals
  AFTER INSERT ON public.app_signals
  FOR EACH STATEMENT
  EXECUTE FUNCTION clean_old_app_signals();

-- --------------------------------------------------------
-- DATOS POR DEFECTO PARA INSTALACIÓN NUEVA
-- --------------------------------------------------------
INSERT INTO settings (name, subtitle, ruc, address, phone, thank_you_message)
SELECT 'RestaurantPro', 'Sistema POS', '00000000000', 'Tu Dirección Aquí', '', '¡Gracias por su preferencia!'
WHERE NOT EXISTS (SELECT 1 FROM settings LIMIT 1);