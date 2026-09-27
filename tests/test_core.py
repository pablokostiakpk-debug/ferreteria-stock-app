import os
import tempfile

os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mktemp(suffix='.db')
os.environ['JWT_SECRET'] = 'test-secret-that-is-definitely-longer-than-thirty-two-bytes'
os.environ['INITIAL_ADMIN_USER'] = 'admin'
os.environ['INITIAL_ADMIN_PASSWORD'] = 'admin123'
os.environ['INITIAL_SELLER_USER'] = 'vendedor'
os.environ['INITIAL_SELLER_PASSWORD'] = 'vendedor123'

from fastapi.testclient import TestClient
from app.main import app


def auth_headers(client, username, password):
    r = client.post('/api/auth/token', json={'username': username, 'password': password})
    assert r.status_code == 200
    return {'Authorization': 'Bearer ' + r.json()['access_token']}


def test_stock_flow_replenishment_and_negative_guard():
    with TestClient(app) as c:
        admin = auth_headers(c, 'admin', 'admin123')
        seller = auth_headers(c, 'vendedor', 'vendedor123')

        supplier = c.post('/api/suppliers', headers=admin, json={'name': 'Proveedor Test', 'whatsapp': '5491112345678'})
        assert supplier.status_code == 201
        sid = supplier.json()['id']

        product = c.post('/api/products', headers=admin, json={
            'barcode': '7799999999001', 'name': 'Tornillo test', 'initial_stock': 10,
            'stock_min': 4, 'stock_target': 20, 'supplier_id': sid
        })
        assert product.status_code == 201
        pid = product.json()['id']

        move = c.post('/api/stock/move', headers=seller, json={
            'product_id': pid, 'movement_type': 'RETIRO', 'quantity': 7
        })
        assert move.status_code == 200
        assert float(move.json()['stock_before']) == 10
        assert float(move.json()['stock_after']) == 3

        low = c.get('/api/replenishment', headers=seller)
        assert low.status_code == 200
        assert len(low.json()) == 1
        assert float(low.json()[0]['suggested_order']) == 17

        negative = c.post('/api/stock/move', headers=seller, json={
            'product_id': pid, 'movement_type': 'RETIRO', 'quantity': 99
        })
        assert negative.status_code == 409


def test_batch_is_atomic():
    with TestClient(app) as c:
        admin = auth_headers(c, 'admin', 'admin123')
        seller = auth_headers(c, 'vendedor', 'vendedor123')

        p1 = c.post('/api/products', headers=admin, json={
            'barcode': '7799999999002', 'name': 'Tarugo test', 'initial_stock': 5,
            'stock_min': 1, 'stock_target': 10
        }).json()
        p2 = c.post('/api/products', headers=admin, json={
            'barcode': '7799999999003', 'name': 'Mecha test', 'initial_stock': 2,
            'stock_min': 1, 'stock_target': 5
        }).json()

        failed = c.post('/api/stock/batch', headers=seller, json={
            'movement_type': 'RETIRO',
            'items': [
                {'product_id': p1['id'], 'quantity': 2},
                {'product_id': p2['id'], 'quantity': 10}
            ]
        })
        assert failed.status_code == 409

        p1_after = c.get('/api/products/barcode/7799999999002', headers=seller).json()
        assert float(p1_after['stock_current']) == 5


def test_permissions_and_order_generation():
    with TestClient(app) as c:
        admin = auth_headers(c, 'admin', 'admin123')
        seller = auth_headers(c, 'vendedor', 'vendedor123')

        assert c.get('/api/stock/history', headers=seller).status_code == 403
        assert c.get('/api/stock/history', headers=admin).status_code == 200

        supplier = c.post('/api/suppliers', headers=admin, json={'name': 'Proveedor Pedido', 'whatsapp': '5491122222222'}).json()
        product = c.post('/api/products', headers=admin, json={
            'barcode': '7799999999004', 'name': 'Arandela test', 'initial_stock': 1,
            'stock_min': 5, 'stock_target': 20, 'supplier_id': supplier['id']
        }).json()

        order = c.post('/api/orders/generate', headers=seller, json={
            'supplier_id': supplier['id'],
            'items': [{'product_id': product['id'], 'quantity': 19}]
        })
        assert order.status_code == 200
        assert '19 Arandela test' in order.json()['message']
        assert order.json()['whatsapp_url'].startswith('https://wa.me/5491122222222?text=')
