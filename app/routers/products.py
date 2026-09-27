from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Category, MovementType, Product, Supplier, User
from ..schemas import ProductCreate, ProductOut, ProductUpdate
from ..stock_service import apply_movement

router = APIRouter(prefix="/api/products", tags=["products"])


def get_or_create_category(db: Session, name: str | None) -> Category | None:
    if not name or not name.strip():
        return None
    clean = name.strip()
    category = db.scalar(select(Category).where(Category.name == clean))
    if not category:
        category = Category(name=clean)
        db.add(category)
        db.flush()
    return category


def product_query():
    return select(Product).options(selectinload(Product.category), selectinload(Product.supplier))


@router.get("", response_model=list[ProductOut])
def list_products(
    q: str | None = Query(default=None),
    supplier_id: int | None = None,
    category_id: int | None = None,
    include_inactive: bool = False,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = product_query()
    if not include_inactive:
        stmt = stmt.where(Product.active.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.outerjoin(Category).outerjoin(Supplier).where(
            or_(
                Product.name.ilike(pattern),
                Product.barcode.ilike(pattern),
                Product.brand.ilike(pattern),
                Category.name.ilike(pattern),
                Supplier.name.ilike(pattern),
            )
        )
    if supplier_id:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    stmt = stmt.order_by(Product.name).limit(limit)
    return list(db.scalars(stmt).unique().all())


@router.get("/barcode/{barcode}", response_model=ProductOut)
def by_barcode(barcode: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    product = db.scalar(product_query().where(Product.barcode == barcode, Product.active.is_(True)))
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    product = db.scalar(product_query().where(Product.id == product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if db.scalar(select(Product).where(Product.barcode == data.barcode.strip())):
        raise HTTPException(status_code=409, detail="El código de barras ya existe")
    if data.supplier_id and not db.get(Supplier, data.supplier_id):
        raise HTTPException(status_code=422, detail="Proveedor inexistente")

    category = get_or_create_category(db, data.category)
    product = Product(
        barcode=data.barcode.strip(),
        name=data.name.strip(),
        description=data.description,
        category_id=category.id if category else None,
        brand=data.brand,
        unit=data.unit,
        stock_current=Decimal("0"),
        stock_min=data.stock_min,
        stock_target=data.stock_target,
        supplier_id=data.supplier_id,
        supplier_code=data.supplier_code,
        purchase_price=data.purchase_price,
        sale_price=data.sale_price,
        location=data.location,
        notes=data.notes,
    )
    db.add(product)
    try:
        db.flush()
        if data.initial_stock > 0:
            apply_movement(
                db,
                product=product,
                movement_type=MovementType.ADJUSTMENT,
                quantity=data.initial_stock,
                user=user,
                notes="Stock inicial",
                explicit_sign=1,
                commit=False,
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear el producto. Verificá el código de barras.")
    return db.scalar(product_query().where(Product.id == product.id))


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    changes = data.model_dump(exclude_unset=True)

    if "barcode" in changes and changes["barcode"]:
        duplicate = db.scalar(select(Product).where(Product.barcode == changes["barcode"], Product.id != product_id))
        if duplicate:
            raise HTTPException(status_code=409, detail="El código de barras ya existe")
    if "supplier_id" in changes and changes["supplier_id"] is not None and not db.get(Supplier, changes["supplier_id"]):
        raise HTTPException(status_code=422, detail="Proveedor inexistente")
    if "category" in changes:
        category = get_or_create_category(db, changes.pop("category"))
        product.category_id = category.id if category else None

    for key, value in changes.items():
        setattr(product, key, value)
    db.commit()
    return db.scalar(product_query().where(Product.id == product_id))


@router.delete("/{product_id}")
def deactivate_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.active = False
    db.commit()
    return {"ok": True, "message": "Producto desactivado. El historial se conserva."}
