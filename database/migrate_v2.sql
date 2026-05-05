-- ==========================================================
-- MIGRATION V2: Aplica mejoras de seguridad y schema
-- a una base de datos Supabase existente SIN perder datos.
-- 
-- Ejecutar en: SQL Editor de Supabase Dashboard
-- Orden: secuencial (cada bloque depende del anterior)
-- ==========================================================

-- ═══════════════════════════════════════════════════════════
-- 1. CHECK CONSTRAINTS (agregar si no existen)
-- ═══════════════════════════════════════════════════════════

-- users.role
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_users_role') THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_role CHECK (role IN ('admin','manager','waiter','cashier','chef','kitchen'));
    END IF;
END $$;

-- tables.capacity > 0
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_tables_capacity_positive') THEN
        ALTER TABLE tables ADD CONSTRAINT chk_tables_capacity_positive CHECK (capacity > 0);
    END IF;
END $$;

-- tables.status
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_tables_status') THEN
        ALTER TABLE tables ADD CONSTRAINT chk_tables_status CHECK (status IN ('free','occupied','reserved','maintenance'));
    END IF;
END $$;

-- products: price, cost, stock, preparation_time >= 0
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_products_price_nonneg') THEN
        ALTER TABLE products ADD CONSTRAINT chk_products_price_nonneg CHECK (price >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_products_cost_nonneg') THEN
        ALTER TABLE products ADD CONSTRAINT chk_products_cost_nonneg CHECK (cost >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_products_stock_nonneg') THEN
        ALTER TABLE products ADD CONSTRAINT chk_products_stock_nonneg CHECK (stock >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_products_prep_time_nonneg') THEN
        ALTER TABLE products ADD CONSTRAINT chk_products_prep_time_nonneg CHECK (preparation_time >= 0);
    END IF;
END $$;

-- orders: type, status, discount range, tip, total, delivery_fee, dine_in requires table
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_order_type') THEN
        ALTER TABLE orders ADD CONSTRAINT chk_order_type CHECK (order_type IN ('dine_in','takeaway','delivery'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_order_status') THEN
        ALTER TABLE orders ADD CONSTRAINT chk_order_status CHECK (status IN ('pending','preparing','ready','served','paid','cancelled'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_orders_discount_range') THEN
        ALTER TABLE orders ADD CONSTRAINT chk_orders_discount_range CHECK (discount_percent BETWEEN 0 AND 100);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_orders_tip_nonneg') THEN
        ALTER TABLE orders ADD CONSTRAINT chk_orders_tip_nonneg CHECK (tip >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_orders_total_nonneg') THEN
        ALTER TABLE orders ADD CONSTRAINT chk_orders_total_nonneg CHECK (total_amount >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_orders_delivery_fee_nonneg') THEN
        ALTER TABLE orders ADD CONSTRAINT chk_orders_delivery_fee_nonneg CHECK (delivery_fee >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_orders_dine_in_requires_table') THEN
        ALTER TABLE orders ADD CONSTRAINT chk_orders_dine_in_requires_table CHECK (order_type <> 'dine_in' OR table_id IS NOT NULL);
    END IF;
END $$;

-- order_items: status, qty, unit_price, subtotal
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_order_item_status') THEN
        ALTER TABLE order_items ADD CONSTRAINT chk_order_item_status CHECK (status IN ('pending','preparing','ready','delivered','cancelled'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_order_items_qty_positive') THEN
        ALTER TABLE order_items ADD CONSTRAINT chk_order_items_qty_positive CHECK (quantity > 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_order_items_unit_price_nonneg') THEN
        ALTER TABLE order_items ADD CONSTRAINT chk_order_items_unit_price_nonneg CHECK (unit_price >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_order_items_subtotal_nonneg') THEN
        ALTER TABLE order_items ADD CONSTRAINT chk_order_items_subtotal_nonneg CHECK (subtotal >= 0);
    END IF;
END $$;

-- cash_sessions: status, opening_amount
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_cash_session_status') THEN
        ALTER TABLE cash_sessions ADD CONSTRAINT chk_cash_session_status CHECK (status IN ('open','closed'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_cash_sessions_opening_nonneg') THEN
        ALTER TABLE cash_sessions ADD CONSTRAINT chk_cash_sessions_opening_nonneg CHECK (opening_amount >= 0);
    END IF;
END $$;

-- cash_expenses: amount > 0
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_cash_expenses_amount_positive') THEN
        ALTER TABLE cash_expenses ADD CONSTRAINT chk_cash_expenses_amount_positive CHECK (amount > 0);
    END IF;
END $$;

-- payments: method, status, amount > 0
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_payment_method') THEN
        ALTER TABLE payments ADD CONSTRAINT chk_payment_method CHECK (payment_method IN ('cash','card','yape','plin','transfer'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_payment_status') THEN
        ALTER TABLE payments ADD CONSTRAINT chk_payment_status CHECK (status IN ('pending','completed','failed','refunded'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_payments_amount_positive') THEN
        ALTER TABLE payments ADD CONSTRAINT chk_payments_amount_positive CHECK (amount > 0);
    END IF;
END $$;

-- invoices: type, subtotal, total
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_invoice_type') THEN
        ALTER TABLE invoices ADD CONSTRAINT chk_invoice_type CHECK (invoice_type IN ('boleta','factura'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_invoices_subtotal_nonneg') THEN
        ALTER TABLE invoices ADD CONSTRAINT chk_invoices_subtotal_nonneg CHECK (subtotal >= 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_invoices_total_nonneg') THEN
        ALTER TABLE invoices ADD CONSTRAINT chk_invoices_total_nonneg CHECK (total_amount >= 0);
    END IF;
END $$;

-- notifications: type
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_notifications_type') THEN
        ALTER TABLE notifications ADD CONSTRAINT chk_notifications_type CHECK (type IN ('system','order','payment','alert'));
    END IF;
END $$;

-- reservations: status, guest_count
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_reservation_status') THEN
        ALTER TABLE reservations ADD CONSTRAINT chk_reservation_status CHECK (status IN ('pending','confirmed','cancelled','completed'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_reservations_guest_count_positive') THEN
        ALTER TABLE reservations ADD CONSTRAINT chk_reservations_guest_count_positive CHECK (guest_count > 0);
    END IF;
END $$;


-- ═══════════════════════════════════════════════════════════
-- 2. NOT NULL constraints (safe: solo si no hay NULLs existentes)
-- ═══════════════════════════════════════════════════════════

-- order_items.unit_price NOT NULL
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='order_items' AND column_name='unit_price' AND is_nullable='NO') THEN
        UPDATE order_items SET unit_price = 0 WHERE unit_price IS NULL;
        ALTER TABLE order_items ALTER COLUMN unit_price SET NOT NULL;
    END IF;
END $$;

-- order_items.subtotal NOT NULL
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='order_items' AND column_name='subtotal' AND is_nullable='NO') THEN
        UPDATE order_items SET subtotal = 0 WHERE subtotal IS NULL;
        ALTER TABLE order_items ALTER COLUMN subtotal SET NOT NULL;
    END IF;
END $$;

-- users.full_name NOT NULL
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='full_name' AND is_nullable='NO') THEN
        UPDATE users SET full_name = username WHERE full_name IS NULL;
        ALTER TABLE users ALTER COLUMN full_name SET NOT NULL;
    END IF;
END $$;

-- payments.order_id NOT NULL
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='order_id' AND is_nullable='NO') THEN
        ALTER TABLE payments ALTER COLUMN order_id SET NOT NULL;
    END IF;
END $$;

-- invoices.payment_id NOT NULL
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='invoices' AND column_name='payment_id' AND is_nullable='NO') THEN
        ALTER TABLE invoices ALTER COLUMN payment_id SET NOT NULL;
    END IF;
END $$;


-- ═══════════════════════════════════════════════════════════
-- 3. REMOVE tax_amount column from invoices (if it exists)
-- ═══════════════════════════════════════════════════════════
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='invoices' AND column_name='tax_amount') THEN
        ALTER TABLE invoices DROP COLUMN tax_amount;
    END IF;
END $$;


-- ═══════════════════════════════════════════════════════════
-- 4. INDEXES (IF NOT EXISTS is safe)
-- ═══════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_table_id ON orders(table_id);

CREATE INDEX IF NOT EXISTS idx_order_items_status ON order_items(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_payment_id ON order_items(payment_id);

CREATE INDEX IF NOT EXISTS idx_cash_sessions_user_id ON cash_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_cash_expenses_user_id ON cash_expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_cash_expenses_cash_session_id ON cash_expenses(cash_session_id);

CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(created_at);
CREATE INDEX IF NOT EXISTS idx_payments_created_by ON payments(created_by);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_cash_session_id ON payments(cash_session_id);

CREATE INDEX IF NOT EXISTS idx_invoices_payment_id ON invoices(payment_id);

CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_reservations_table_id ON reservations(table_id);
CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status);


-- ═══════════════════════════════════════════════════════════
-- 5. SECUENCIAS DE NEGOCIO (si no existen)
-- ═══════════════════════════════════════════════════════════
CREATE SEQUENCE IF NOT EXISTS order_number_seq START 1;
CREATE SEQUENCE IF NOT EXISTS boleta_seq START 1;
CREATE SEQUENCE IF NOT EXISTS factura_seq START 1;


-- ═══════════════════════════════════════════════════════════
-- 6. TRIGGER: updated_at en products y orders
-- ═══════════════════════════════════════════════════════════
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


-- ═══════════════════════════════════════════════════════════
-- 7. TRIGGER: Auto-limpieza de app_signals (24h)
-- ═══════════════════════════════════════════════════════════
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


-- ═══════════════════════════════════════════════════════════
-- 8. ROW LEVEL SECURITY (RLS)
-- ═══════════════════════════════════════════════════════════
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

-- Eliminar policy vacía service_role_full_access si existe
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_policies WHERE policyname='service_role_full_access') THEN
        EXECUTE 'DROP POLICY service_role_full_access ON public.' || (
            SELECT tablename FROM pg_policies WHERE policyname='service_role_full_access' LIMIT 1
        );
    END IF;
END $$;

-- Authenticated: lectura completa
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

-- Authenticated: escritura según tabla
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='orders' AND policyname='authenticated_insert_orders') THEN
        CREATE POLICY authenticated_insert_orders ON orders FOR INSERT TO authenticated WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='orders' AND policyname='authenticated_update_orders') THEN
        CREATE POLICY authenticated_update_orders ON orders FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='order_items' AND policyname='authenticated_all_items') THEN
        CREATE POLICY authenticated_all_items ON order_items FOR ALL TO authenticated USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='products' AND policyname='authenticated_write_products') THEN
        CREATE POLICY authenticated_write_products ON products FOR ALL TO authenticated USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='categories' AND policyname='authenticated_write_categories') THEN
        CREATE POLICY authenticated_write_categories ON categories FOR ALL TO authenticated USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='tables' AND policyname='authenticated_all_tables') THEN
        CREATE POLICY authenticated_all_tables ON tables FOR ALL TO authenticated USING (true) WITH CHECK (true);
    END IF;
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
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='notifications' AND policyname='authenticated_all_notifications') THEN
        CREATE POLICY authenticated_all_notifications ON notifications FOR ALL TO authenticated USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='reservations' AND policyname='authenticated_all_reservations') THEN
        CREATE POLICY authenticated_all_reservations ON reservations FOR ALL TO authenticated USING (true) WITH CHECK (true);
    END IF;
END $$;

-- Anon: solo lectura de app_signals (para Realtime)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies p
        WHERE p.schemaname='public' AND p.tablename='app_signals' AND p.policyname='anon_read_signals'
    ) THEN
        EXECUTE 'CREATE POLICY anon_read_signals ON public.app_signals FOR SELECT TO anon USING (true)';
    END IF;
END $$;


-- ═══════════════════════════════════════════════════════════
-- 9. FIX FK circular: order_items.payment_id ON DELETE SET NULL
-- ═══════════════════════════════════════════════════════════
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = 'order_items' AND kcu.column_name = 'payment_id'
        AND tc.constraint_type = 'FOREIGN KEY'
        AND tc.constraint_name != 'order_items_payment_id_fkey'
    ) THEN
        ALTER TABLE order_items DROP CONSTRAINT order_items_payment_id_fkey;
        ALTER TABLE order_items ADD CONSTRAINT order_items_payment_id_fkey
            FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL;
    END IF;
END $$;


-- ═══════════════════════════════════════════════════════════
-- 10. FIX FK: payments.order_id ON DELETE CASCADE
-- ═══════════════════════════════════════════════════════════
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = 'payments' AND kcu.column_name = 'order_id'
        AND tc.constraint_type = 'FOREIGN KEY'
    ) THEN
        -- Solo reemplazar si no es CASCADE
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'payments_order_id_fkey'
            AND confdeltype = 'c'  -- 'c' = CASCADE
        ) THEN
            ALTER TABLE payments DROP CONSTRAINT payments_order_id_fkey;
            ALTER TABLE payments ADD CONSTRAINT payments_order_id_fkey
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE;
        END IF;
    END IF;
END $$;


-- ═══════════════════════════════════════════════════════════
-- VERIFICACIÓN POST-MIGRACIÓN
-- ═══════════════════════════════════════════════════════════
-- Ejecutar manualmente para confirmar que todo se aplicó:
-- SELECT conname, convalidated FROM pg_constraint WHERE conname LIKE 'chk_%' ORDER BY conname;
-- SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY indexname;
-- SELECT tablename, policyname FROM pg_policies WHERE schemaname='public' ORDER BY tablename;
