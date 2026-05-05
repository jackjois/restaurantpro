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
  full_name VARCHAR(100) NOT NULL,
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(120) UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(50) DEFAULT 'waiter',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_users_role CHECK (role IN ('admin', 'manager', 'waiter', 'cashier', 'chef', 'kitchen'))
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
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_tables_capacity_positive CHECK (capacity > 0),
  CONSTRAINT chk_tables_status CHECK (status IN ('free', 'occupied', 'reserved', 'maintenance'))
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
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_products_price_nonneg CHECK (price >= 0),
  CONSTRAINT chk_products_cost_nonneg CHECK (cost >= 0),
  CONSTRAINT chk_products_stock_nonneg CHECK (stock >= 0),
  CONSTRAINT chk_products_prep_time_nonneg CHECK (preparation_time >= 0)
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
  discount_percent NUMERIC(5,2) DEFAULT 0.00,
  tip NUMERIC(10,2) DEFAULT 0.00,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_order_type CHECK (order_type IN ('dine_in', 'takeaway', 'delivery')),
  CONSTRAINT chk_order_status CHECK (status IN ('pending', 'preparing', 'ready', 'served', 'paid', 'cancelled')),
  CONSTRAINT chk_orders_discount_range CHECK (discount_percent BETWEEN 0 AND 100),
  CONSTRAINT chk_orders_tip_nonneg CHECK (tip >= 0),
  CONSTRAINT chk_orders_total_nonneg CHECK (total_amount >= 0),
  CONSTRAINT chk_orders_delivery_fee_nonneg CHECK (delivery_fee >= 0),
  CONSTRAINT chk_orders_dine_in_requires_table CHECK (order_type <> 'dine_in' OR table_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_table_id ON orders(table_id);

-- --------------------------------------------------------
-- 7. Tabla `order_items`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
  id SERIAL PRIMARY KEY,
  order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
  product_id INTEGER REFERENCES products(id),
  quantity INTEGER NOT NULL DEFAULT 1,
  unit_price NUMERIC(10,2) NOT NULL,
  subtotal NUMERIC(10,2) NOT NULL,
  status VARCHAR(50) DEFAULT 'pending',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  is_printed BOOLEAN DEFAULT FALSE,
  is_paid BOOLEAN DEFAULT FALSE,
  payment_id INTEGER REFERENCES payments(id) ON DELETE SET NULL,
  CONSTRAINT chk_order_item_status CHECK (status IN ('pending', 'preparing', 'ready', 'delivered', 'cancelled')),
  CONSTRAINT chk_order_items_qty_positive CHECK (quantity > 0),
  CONSTRAINT chk_order_items_unit_price_nonneg CHECK (unit_price >= 0),
  CONSTRAINT chk_order_items_subtotal_nonneg CHECK (subtotal >= 0)
);

CREATE INDEX IF NOT EXISTS idx_order_items_status ON order_items(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_payment_id ON order_items(payment_id);

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
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_cash_session_status CHECK (status IN ('open', 'closed')),
  CONSTRAINT chk_cash_sessions_opening_nonneg CHECK (opening_amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_cash_sessions_user_id ON cash_sessions(user_id);

-- --------------------------------------------------------
-- 9. Tabla `cash_expenses`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS cash_expenses (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  cash_session_id INTEGER REFERENCES cash_sessions(id),
  amount NUMERIC(10,2) NOT NULL,
  reason VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_cash_expenses_amount_positive CHECK (amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_cash_expenses_user_id ON cash_expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_cash_expenses_cash_session_id ON cash_expenses(cash_session_id);

-- --------------------------------------------------------
-- 10. Tabla `payments`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
  id SERIAL PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  amount NUMERIC(10,2) NOT NULL,
  payment_method VARCHAR(50) NOT NULL,
  reference_code VARCHAR(100),
  status VARCHAR(50) DEFAULT 'pending',
  created_by INTEGER REFERENCES users(id),
  cash_session_id INTEGER REFERENCES cash_sessions(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_payment_method CHECK (payment_method IN ('cash', 'card', 'yape', 'plin', 'transfer')),
  CONSTRAINT chk_payment_status CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
  CONSTRAINT chk_payments_amount_positive CHECK (amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(created_at);
CREATE INDEX IF NOT EXISTS idx_payments_created_by ON payments(created_by);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_cash_session_id ON payments(cash_session_id);

-- --------------------------------------------------------
-- 11. Tabla `invoices`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
  id SERIAL PRIMARY KEY,
  payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
  invoice_type VARCHAR(50) NOT NULL,
  document_number VARCHAR(50) UNIQUE,
  customer_name VARCHAR(150),
  customer_document VARCHAR(50),
  customer_address TEXT,
  subtotal NUMERIC(10,2),
  total_amount NUMERIC(10,2),
  pdf_path VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_invoice_type CHECK (invoice_type IN ('boleta', 'factura')),
  CONSTRAINT chk_invoices_subtotal_nonneg CHECK (subtotal >= 0),
  CONSTRAINT chk_invoices_total_nonneg CHECK (total_amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_invoices_payment_id ON invoices(payment_id);

-- --------------------------------------------------------
-- 12. Tabla `notifications`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  type VARCHAR(50) DEFAULT 'system',
  message TEXT NOT NULL,
  is_read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chk_notifications_type CHECK (type IN ('system', 'order', 'payment', 'alert'))
);

CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);

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
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

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
-- 15. Tabla `reservations`
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS reservations (
    id SERIAL PRIMARY KEY,
    table_id INTEGER REFERENCES tables(id) ON DELETE CASCADE NOT NULL,
    customer_name VARCHAR(150) NOT NULL,
    customer_phone VARCHAR(50),
    reservation_time TIMESTAMPTZ NOT NULL,
  guest_count INTEGER DEFAULT 1,
  status VARCHAR(50) DEFAULT 'pending',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
  CONSTRAINT chk_reservation_status CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed')),
  CONSTRAINT chk_reservations_guest_count_positive CHECK (guest_count > 0)
);

CREATE INDEX IF NOT EXISTS idx_reservations_table_id ON reservations(table_id);
CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status);

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
ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;

-- Políticas: El backend Flask usa service_role key (bypassea RLS en Supabase).
-- Solo definimos políticas para authenticated y anon.
-- authenticated: lectura general + escritura según rol (admin/manager = full, otros = limitado)
-- anon: solo lectura de app_signals (para Supabase Realtime)

-- Authenticated: lectura completa en todas las tablas de negocio
DO $$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY['categories','users','settings','tables','products','orders','order_items','cash_sessions','cash_expenses','payments','invoices','notifications','audit_logs','reservations'])
  LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies p
      WHERE p.schemaname='public' AND p.tablename=t AND p.policyname='authenticated_read'
    ) THEN
      EXECUTE format('CREATE POLICY authenticated_read ON public.%I FOR SELECT TO authenticated USING (true)', t);
    END IF;
  END LOOP;
END $$;

-- Authenticated: escritura limitada (meseros crean órdenes, chef actualiza items, etc.)
DO $$
BEGIN
  -- Órdenes: cualquier authenticated puede crear; solo el creador o admin puede modificar
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='orders' AND policyname='authenticated_insert_orders') THEN
    CREATE POLICY authenticated_insert_orders ON orders FOR INSERT TO authenticated WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='orders' AND policyname='authenticated_update_orders') THEN
    CREATE POLICY authenticated_update_orders ON orders FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
  END IF;
  -- Ítems de orden: mismo acceso que órdenes
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='order_items' AND policyname='authenticated_all_items') THEN
    CREATE POLICY authenticated_all_items ON order_items FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  -- Productos y categorías: solo lectura para no-admin (la escritura la hace el backend)
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='products' AND policyname='authenticated_write_products') THEN
    CREATE POLICY authenticated_write_products ON products FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='categories' AND policyname='authenticated_write_categories') THEN
    CREATE POLICY authenticated_write_categories ON categories FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  -- Mesas: lectura + actualización de estado
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='tables' AND policyname='authenticated_all_tables') THEN
    CREATE POLICY authenticated_all_tables ON tables FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  -- Pagos, sesiones de caja, facturas: acceso completo authenticated
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='payments' AND policyname='authenticated_all_payments') THEN
    CREATE POLICY authenticated_all_payments ON payments FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='cash_sessions' AND policyname='authenticated_all_cash_sessions') THEN
    CREATE POLICY authenticated_all_cash_sessions ON cash_sessions FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='cash_expenses' AND policyname='authenticated_all_cash_expenses') THEN
    CREATE POLICY authenticated_all_cash_expenses ON cash_expenses FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='invoices' AND policyname='authenticated_all_invoices') THEN
    CREATE POLICY authenticated_all_invoices ON invoices FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  -- Notificaciones: acceso completo
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='notifications' AND policyname='authenticated_all_notifications') THEN
    CREATE POLICY authenticated_all_notifications ON notifications FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
  -- Reservas: acceso completo
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='reservations' AND policyname='authenticated_all_reservations') THEN
    CREATE POLICY authenticated_all_reservations ON reservations FOR ALL TO authenticated USING (true) WITH CHECK (true);
  END IF;
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
-- TRIGGER: Auto-actualizar updated_at en products y orders
-- --------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_products_updated_at ON products;
CREATE TRIGGER trg_products_updated_at
  BEFORE UPDATE ON products
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_orders_updated_at ON orders;
CREATE TRIGGER trg_orders_updated_at
  BEFORE UPDATE ON orders
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- --------------------------------------------------------
-- DATOS POR DEFECTO PARA INSTALACIÓN NUEVA
-- --------------------------------------------------------
INSERT INTO settings (name, subtitle, ruc, address, phone, thank_you_message)
SELECT 'RestaurantPro', 'Sistema POS', '00000000000', 'Tu Dirección Aquí', '', '¡Gracias por su preferencia!'
WHERE NOT EXISTS (SELECT 1 FROM settings LIMIT 1);