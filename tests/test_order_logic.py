from decimal import Decimal
from app.models.order import Order, OrderItem


class TestOrderRecalculateTotal:
    def test_empty_order(self):
        o = Order()
        o.items = []
        o.discount_percent = Decimal('0')
        o.tip = Decimal('0')
        o.delivery_fee = Decimal('0')
        assert o.recalculate_total() == Decimal('0')

    def test_single_item(self):
        o = Order()
        o.items = [OrderItem(subtotal=Decimal('25.00'), status='pending')]
        o.discount_percent = Decimal('0')
        o.tip = Decimal('0')
        o.delivery_fee = Decimal('0')
        assert o.recalculate_total() == Decimal('25.00')

    def test_multiple_items(self):
        o = Order()
        o.items = [
            OrderItem(subtotal=Decimal('25.00'), status='pending'),
            OrderItem(subtotal=Decimal('30.00'), status='preparing'),
        ]
        o.discount_percent = Decimal('0')
        o.tip = Decimal('0')
        o.delivery_fee = Decimal('0')
        assert o.recalculate_total() == Decimal('55.00')

    def test_cancelled_items_excluded(self):
        o = Order()
        o.items = [
            OrderItem(subtotal=Decimal('25.00'), status='pending'),
            OrderItem(subtotal=Decimal('30.00'), status='cancelled'),
        ]
        o.discount_percent = Decimal('0')
        o.tip = Decimal('0')
        o.delivery_fee = Decimal('0')
        assert o.recalculate_total() == Decimal('25.00')

    def test_discount_percent(self):
        o = Order()
        o.items = [OrderItem(subtotal=Decimal('100.00'), status='pending')]
        o.discount_percent = Decimal('10')
        o.tip = Decimal('0')
        o.delivery_fee = Decimal('0')
        assert o.recalculate_total() == Decimal('90.00')

    def test_tip_added(self):
        o = Order()
        o.items = [OrderItem(subtotal=Decimal('100.00'), status='pending')]
        o.discount_percent = Decimal('0')
        o.tip = Decimal('15.00')
        o.delivery_fee = Decimal('0')
        assert o.recalculate_total() == Decimal('115.00')

    def test_delivery_fee_added(self):
        o = Order()
        o.items = [OrderItem(subtotal=Decimal('50.00'), status='pending')]
        o.discount_percent = Decimal('0')
        o.tip = Decimal('0')
        o.delivery_fee = Decimal('5.00')
        assert o.recalculate_total() == Decimal('55.00')

    def test_all_components(self):
        o = Order()
        o.items = [OrderItem(subtotal=Decimal('100.00'), status='pending')]
        o.discount_percent = Decimal('10')
        o.tip = Decimal('10.00')
        o.delivery_fee = Decimal('5.00')
        assert o.recalculate_total() == Decimal('105.00')


class TestOrderGetBreakdown:
    def test_read_only(self):
        o = Order()
        o.items = [OrderItem(subtotal=Decimal('100.00'), status='pending')]
        o.discount_percent = Decimal('10')
        o.tip = Decimal('5.00')
        o.delivery_fee = Decimal('3.00')
        o.total_amount = Decimal('999.99')
        bd = o.get_breakdown()
        assert bd['subtotal'] == 100.0
        assert bd['discount_amount'] == 10.0
        assert bd['tip_val'] == 5.0
        assert bd['delivery_fee_val'] == 3.0
        assert bd['grand_total'] == 98.0
        assert o.total_amount == Decimal('999.99')

    def test_zero_values(self):
        o = Order()
        o.items = []
        o.discount_percent = Decimal('0')
        o.tip = Decimal('0')
        o.delivery_fee = Decimal('0')
        bd = o.get_breakdown()
        assert bd['subtotal'] == 0.0
        assert bd['grand_total'] == 0.0


class TestCanTransitionTo:
    def test_pending_to_preparing(self):
        o = Order()
        o.status = 'pending'
        assert o.can_transition_to('preparing') is True

    def test_pending_to_cancelled(self):
        o = Order()
        o.status = 'pending'
        assert o.can_transition_to('cancelled') is True

    def test_pending_to_paid(self):
        o = Order()
        o.status = 'pending'
        assert o.can_transition_to('paid') is True

    def test_paid_to_anything(self):
        o = Order()
        o.status = 'paid'
        assert o.can_transition_to('pending') is False
        assert o.can_transition_to('cancelled') is False

    def test_cancelled_to_anything(self):
        o = Order()
        o.status = 'cancelled'
        assert o.can_transition_to('pending') is False

    def test_invalid_status(self):
        o = Order()
        o.status = 'unknown_status'
        assert o.can_transition_to('pending') is False

    def test_preparing_to_ready(self):
        o = Order()
        o.status = 'preparing'
        assert o.can_transition_to('ready') is True

    def test_served_to_paid(self):
        o = Order()
        o.status = 'served'
        assert o.can_transition_to('paid') is True


class TestSyncStatusFromItems:
    def test_all_delivered_becomes_served(self):
        o = Order()
        o.status = 'ready'
        o.items = [
            OrderItem(status='delivered', subtotal=Decimal('10')),
        ]
        result = o.sync_status_from_items()
        assert result == 'served'

    def test_all_cancelled_becomes_cancelled(self):
        o = Order()
        o.status = 'pending'
        o.items = [
            OrderItem(status='cancelled', subtotal=Decimal('10')),
        ]
        result = o.sync_status_from_items()
        assert result == 'cancelled'

    def test_paid_stays_paid(self):
        o = Order()
        o.status = 'paid'
        o.items = [
            OrderItem(status='delivered', subtotal=Decimal('10')),
        ]
        result = o.sync_status_from_items()
        assert result == 'paid'

    def test_mixed_ready_delivered(self):
        o = Order()
        o.status = 'pending'
        o.items = [
            OrderItem(status='ready', subtotal=Decimal('10')),
            OrderItem(status='delivered', subtotal=Decimal('10')),
        ]
        result = o.sync_status_from_items()
        assert result == 'preparing'

    def test_no_backward_transition(self):
        o = Order()
        o.status = 'ready'
        o.items = [
            OrderItem(status='preparing', subtotal=Decimal('10')),
        ]
        result = o.sync_status_from_items()
        assert result == 'ready'


class TestItemTransitions:
    def test_item_pending_to_preparing(self):
        assert 'preparing' in Order.VALID_ITEM_TRANSITIONS['pending']

    def test_item_preparing_to_ready(self):
        assert 'ready' in Order.VALID_ITEM_TRANSITIONS['preparing']

    def test_item_ready_to_delivered(self):
        assert 'delivered' in Order.VALID_ITEM_TRANSITIONS['ready']

    def test_item_delivered_no_transitions(self):
        assert Order.VALID_ITEM_TRANSITIONS['delivered'] == []

    def test_item_cancelled_no_transitions(self):
        assert Order.VALID_ITEM_TRANSITIONS['cancelled'] == []
