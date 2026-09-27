import re
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..database import get_db
from ..models import Product, PurchaseOrder, PurchaseOrderItem, Supplier, User
from ..schemas import GeneratedOrderOut, OrderCreateIn, OrderOut, ReplenishmentItem

router = APIRouter(prefix="/api", tags=["replenishment"])


@router.get("/replenishment", response_model=list[ReplenishmentItem])
def replenishment(
    supplier_id: int | None = None,
    category_id: int | None = None,
    out_of_stock: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(Product)
        .options(selectinload(Product.supplier), selectinload(Product.category))
        .where(Product.active.is_(True), Product.stock_current <= Product.stock_min)
    )
    if supplier_id:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if out_of_stock:
        stmt = stmt.where(Product.stock_current <= 0)
    products = db.scalars(stmt.order_by(Product.stock_current.asc(), Product.name)).all()
    return [
        ReplenishmentItem(
            product_id=p.id,
            barcode=p.barcode,
            name=p.name,
            unit=p.unit,
            stock_current=p.stock_current,
            stock_min=p.stock_min,
            stock_target=p.stock_target,
            suggested_order=max(Decimal(p.stock_target) - Decimal(p.stock_current), Decimal("0")),
            supplier_id=p.supplier_id,
            supplier_name=p.supplier.name if p.supplier else None,
            category_name=p.category.name if p.category else None,
        )
        for p in products
    ]


def normalize_whatsapp(number: str | None) -> str | None:
    if not number:
        return None
    digits = re.sub(r"\D", "", number)
    # wa.me requiere formato internacional, sin +, espacios ni guiones.
    return digits or None


@router.post("/orders/generate", response_model=GeneratedOrderOut)
def generate_order(data: OrderCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    supplier = db.get(Supplier, data.supplier_id)
    if not supplier or not supplier.active:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    lines: list[str] = []
    resolved: list[tuple[Product, Decimal]] = []
    for item in data.items:
        product = db.get(Product, item.product_id)
        if not product or not product.active:
            raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no encontrado")
        if product.supplier_id != supplier.id:
            raise HTTPException(status_code=422, detail=f"{product.name} no pertenece al proveedor seleccionado")
        qty = Decimal(item.quantity)
        resolved.append((product, qty))
        code = f" ({product.supplier_code})" if product.supplier_code else ""
        qty_text = f"{qty.normalize()}" if qty % 1 else str(int(qty))
        lines.append(f"- {qty_text} {product.name}{code}")

    message = f"{data.intro.strip()}\n\n" + "\n".join(lines) + f"\n\n{data.closing.strip()}"
    order = PurchaseOrder(supplier_id=supplier.id, created_by_id=user.id, message=message)
    db.add(order)
    db.flush()
    for product, qty in resolved:
        db.add(PurchaseOrderItem(order_id=order.id, product_id=product.id, quantity=qty, stock_at_order=product.stock_current))
    db.commit()
    db.refresh(order)

    whatsapp_number = normalize_whatsapp(supplier.whatsapp)
    whatsapp_url = f"https://wa.me/{whatsapp_number}?text={quote(message)}" if whatsapp_number else None
    return GeneratedOrderOut(
        order=OrderOut.model_validate(order),
        supplier_name=supplier.name,
        message=message,
        whatsapp_url=whatsapp_url,
    )
