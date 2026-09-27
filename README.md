# Stock Ferretería - MVP funcional

Aplicación web responsive para administrar productos, escanear códigos de barras, retirar/ingresar mercadería, controlar mínimos y generar pedidos por proveedor listos para WhatsApp.

## Qué incluye

- Dashboard con total de productos, stock bajo, sin stock y movimientos del día.
- Productos con código de barras único, categoría, marca, unidad, mínimos, objetivo, proveedor, precios, ubicación y observaciones.
- Escaneo con lector USB que actúa como teclado.
- Escaneo con cámara desde celular usando ZXing en el navegador.
- Retiro o ingreso simple.
- Retiro/ingreso de varios productos en una sola operación.
- Bloqueo de stock negativo.
- Registro obligatorio de cada cambio de stock.
- Reposición automática cuando `stock actual <= stock mínimo`.
- Cantidad sugerida: `stock objetivo - stock actual`.
- Pedido por proveedor, mensaje editable, copiar mensaje y abrir WhatsApp.
- Proveedores.
- Historial de movimientos para administrador.
- Importación CSV/XLSX y exportación CSV/XLSX.
- Login con roles ADMINISTRADOR y VENDEDOR.
- Base persistente SQLite por defecto, preparada para PostgreSQL.

## Puesta en marcha en Windows

1. Instalar Python 3.11 o superior.
2. Abrir una terminal dentro de la carpeta del proyecto.
3. Ejecutar:

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. En la misma PC abrir `http://127.0.0.1:8000`.
5. Desde otra PC/tablet/celular de la misma red, abrir `http://IP_DE_LA_PC:8000`.

Usuarios iniciales de prueba:

- Administrador: `admin` / `admin123`
- Vendedor: `vendedor` / `vendedor123`

Cambiar esas contraseñas/configuración antes de una puesta en producción.

## Cámara del celular

Los navegadores modernos normalmente exigen HTTPS para acceder a la cámara cuando no se está usando `localhost`. Para usar la cámara desde un celular conectado por red local, conviene publicar la aplicación bajo HTTPS. El lector USB no necesita HTTPS.

La pantalla de cámara utiliza `@zxing/browser` 0.2.1 desde un CDN. Si se necesita funcionamiento 100% offline, conviene guardar esa librería dentro de `app/static/vendor`.

## Archivo de importación

Se aceptan CSV y Excel. Las columnas reconocidas incluyen:

- Código de barras
- Nombre
- Categoría
- Marca
- Unidad
- Stock / Stock actual
- Stock mínimo
- Stock objetivo
- Proveedor
- Código proveedor
- Precio compra
- Precio venta
- Ubicación
- Descripción
- Observaciones

Para códigos que empiezan con cero, guardar la columna Código de barras como texto en Excel.

## Base de datos

Por defecto se genera `ferreteria.db` en la carpeta del proyecto. No se pierde al cerrar o reiniciar la aplicación.

Para PostgreSQL, cambiar `DATABASE_URL` en `.env`, por ejemplo:

```env
DATABASE_URL=postgresql+psycopg://usuario:clave@servidor:5432/ferreteria
```

## Seguridad y reglas

- El vendedor puede consultar productos, escanear, retirar, ingresar mercadería y ver reposición.
- El administrador además puede crear/editar/desactivar productos, administrar proveedores, importar datos, ajustar stock y consultar el historial completo.
- Los movimientos no tienen endpoint de borrado.
- Desactivar un producto no elimina sus movimientos anteriores.
- El stock se actualiza en la base con una operación atómica y tiene una restricción adicional que impide valores negativos.

## Pruebas

```bat
pytest -q
```

También se puede verificar la API desde `http://127.0.0.1:8000/docs` mientras el servidor está corriendo.

## Próximos pasos recomendados para producción

1. PostgreSQL si habrá varios puestos trabajando al mismo tiempo de forma permanente.
2. HTTPS y dominio/local DNS para habilitar cámara de forma confiable.
3. Pantalla de administración de usuarios y cambio de contraseña.
4. Backups automáticos de base de datos.
5. Luego agregar ventas/facturación/clientes sin mezclarlo con el núcleo de inventario.
