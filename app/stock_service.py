from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import MovementType, Product, StockMovement, User


def signed_delta(movement_type: MovementType, quantity: Decimal, explicit_sign: int | None = None) -> Decimal:
    if explicit_sign is not None:
        return quantity * explicit_sign
    if movement_type == MovementType.WITHDRAWAL:
        return -quantity
    if movement_type in (MovementType.INCOME, MovementType.RETURN):
        return quantity
    return quantity


def apply_movement(
    db: Session,
    *,
    product: Product,
    movement_type: MovementType,
    quantity: Decimal,
    user: User,
    notes: str | None = None,
    explicit_sign: int | None = None,
    commit: bool = True,
) -> StockMovement:
    if quantity <= 0:
        raise HTTPException(status_code=422, detail="La cantidad debe ser mayor que cero")

    delta = signed_delta(movement_type, Decimal(quantity), explicit_sign)

    # Actualización atómica: evita pérdidas de stock si dos dispositivos operan al mismo tiempo.
    stmt = update(Product).where(Product.id == product.id, Product.active.is_(True))
    if delta < 0:
        stmt = stmt.where(Product.stock_current >= abs(delta))
    stmt = stmt.values(stock_current=Product.stock_current + delta).returning(
        Product.stock_current, Product.barcode, Product.name
    )

    try:
        row = db.execute(stmt).first()
        if not row:
            exists = db.scalar(select(Product).where(Product.id == product.id, Product.active.is_(True)))
            if not exists:
                raise HTTPException(status_code=404, detail="Producto no encontrado")
            raise HTTPException(status_code=409, detail=f"Stock insuficiente. Disponible: {exists.stock_current}")

        after = Decimal(row[0])
        before = after - delta
        movement = StockMovement(
            product_id=product.id,
            barcode_snapshot=row[1],
            product_name_snapshot=row[2],
            movement_type=movement_type,
            quantity=quantity,
            stock_before=before,
            stock_after=after,
            user_id=user.id,
            notes=notes,
        )
        db.add(movement)
        db.flush()
        if commit:
            db.commit()
            db.refresh(movement)
        return movement
    except HTTPException:
        if commit:
            db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el stock. Verificá el stock disponible.")
