# Arquitectura inicial

## Flujo principal

Producto -> Escaneo -> Movimiento de stock -> Historial -> Alerta de mínimo -> Reposición -> Pedido -> WhatsApp

## Entidades

- `users`: usuarios y roles ADMINISTRADOR / VENDEDOR.
- `categories`: categorías de artículos.
- `suppliers`: proveedores y datos de contacto.
- `products`: maestro de artículos y stock actual.
- `stock_movements`: historial inmutable de todos los cambios de stock.
- `purchase_orders`: cabecera de pedidos de reposición.
- `purchase_order_items`: detalle de artículos y cantidades pedidas.

## Reglas de stock

1. El stock nunca puede quedar negativo.
2. Todo cambio crea un `stock_movement`.
3. Los retiros/ingresos múltiples se confirman en una sola transacción.
4. La actualización de stock se realiza con una operación atómica en la base de datos para evitar que dos dispositivos se pisen.
5. Los productos se desactivan en lugar de borrar el historial.
6. Reposición necesaria: `stock_actual <= stock_minimo`.
7. Cantidad sugerida: `max(stock_objetivo - stock_actual, 0)`.

## Crecimiento

La aplicación usa SQLite por defecto para poder arrancar sin instalar un servidor de base de datos. El acceso se hace con SQLAlchemy y `DATABASE_URL`, por lo que puede migrarse a PostgreSQL para una instalación con mayor concurrencia y volumen.
