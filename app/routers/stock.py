from datetime import datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import MovementType, Product, StockMovement, User
from ..schemas import BatchMovementIn, MovementOut, StockMoveByBarcodeIn, StockMoveIn
from ..stock_service import apply_movement

router = APIRouter(prefix="/api/stock", tags=["stock"])


def _validate_regular_type(movement_type: MovementType):
    if movement_type not in (MovementType.WITHDRAWAL, MovementType.INCOME, MovementType.RETURN):
        raise HTTPException(status_code=422, detail="Para ajustes/correcciones usá el endpoint administrativo de ajuste")


@router.post("/move", response_model=MovementOut)
def move_stock(data: StockMoveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _validate_regular_type(data.movement_type)
    product = db.get(Product, data.product_id)
    if not product or not product.active:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return apply_movement(db, product=product, movement_type=data.movement_type, quantity=data.quantity, user=user, notes=data.notes)


@router.post("/move-by-barcode", response_model=MovementOut)
def move_by_barcode(data: StockMoveByBarcodeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _validate_regular_type(data.movement_type)
    product = db.scalar(select(Product).where(Product.barcode == data.barcode, Product.active.is_(True)))
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return apply_movement(db, product=product, movement_type=data.movement_type, quantity=data.quantity, user=user, notes=data.notes)


@router.post("/batch", response_model=list[MovementOut])
def batch_move(data: BatchMovementIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _validate_regular_type(data.movement_type)
    movements = []
    try:
        # Valida todo antes de confirmar para que sea una sola operación atómica.
        for item in data.items:
            product = db.get(Product, item.product_id)
            if not product or not product.active:
                raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no encontrado")
            notes = item.notes or data.notes
            movement = apply_movement(
                db,
                product=product,
                movement_type=data.movement_type,
                quantity=item.quantity,
                user=user,
                notes=notes,
                commit=False,
            )
            movements.append(movement)
        db.commit()
        for movement in movements:
            db.refresh(movement)
        return movements
    except Exception:
        db.rollback()
        raise


@router.post("/adjust/{product_id}", response_model=MovementOut)
def adjust_stock(
    product_id: int,
    new_stock: Decimal = Query(ge=0),
    notes: str = Query(min_length=3),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Vendedores pueden ingresar/retirar; ajuste directo se limita desde la UI a admin.
    if user.role.value != "ADMINISTRADOR":
        raise HTTPException(status_code=403, detail="Sólo un administrador puede ajustar stock")
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    current = Decimal(product.stock_current)
    if new_stock == current:
        raise HTTPException(status_code=422, detail="El nuevo stock es igual al actual")
    sign = 1 if new_stock > current else -1
    qty = abs(new_stock - current)
    return apply_movement(
        db,
        product=product,
        movement_type=MovementType.ADJUSTMENT,
        quantity=qty,
        user=user,
        notes=notes,
        explicit_sign=sign,
    )


@router.get("/history", response_model=list[MovementOut])
def history(
    date_from: str | None = None,
    date_to: str | None = None,
    product_id: int | None = None,
    barcode: str | None = None,
    movement_type: MovementType | None = None,
    supplier_id: int | None = None,
    limit: int = Query(default=300, ge=1, le=2000),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(StockMovement).join(Product)
    if date_from:
        start = datetime.combine(datetime.fromisoformat(date_from).date(), time.min)
        stmt = stmt.where(StockMovement.created_at >= start)
    if date_to:
        end = datetime.combine(datetime.fromisoformat(date_to).date(), time.max)
        stmt = stmt.where(StockMovement.created_at <= end)
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if barcode:
        stmt = stmt.where(StockMovement.barcode_snapshot.ilike(f"%{barcode}%"))
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    if supplier_id:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    return list(db.scalars(stmt.order_by(StockMovement.created_at.desc()).limit(limit)).all())
