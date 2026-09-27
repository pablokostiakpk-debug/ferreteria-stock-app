from __future__ import annotations

from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
import unicodedata

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Category, MovementType, Product, Supplier, User
from ..schemas import ImportResult
from ..stock_service import apply_movement

router = APIRouter(prefix="/api", tags=["import-export"])


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.lower().strip().replace("_", " ").split())


ALIASES = {
    "barcode": {"codigo de barras", "codigo barras", "barcode", "ean", "codigo"},
    "name": {"nombre", "producto", "nombre producto"},
    "category": {"categoria"},
    "brand": {"marca"},
    "unit": {"unidad", "unidad de medida"},
    "stock": {"stock", "stock actual"},
    "stock_min": {"stock minimo", "minimo"},
    "stock_target": {"stock objetivo", "stock ideal", "objetivo"},
    "supplier": {"proveedor", "proveedor habitual"},
    "supplier_code": {"codigo proveedor", "codigo del proveedor"},
    "purchase_price": {"precio compra", "precio de compra"},
    "sale_price": {"precio venta", "precio de venta"},
    "location": {"ubicacion", "ubicacion deposito"},
    "description": {"descripcion"},
    "notes": {"observaciones", "notas"},
}


def map_columns(df: pd.DataFrame) -> dict[str, str]:
    normalized = {norm(c): c for c in df.columns}
    result = {}
    for key, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[key] = normalized[alias]
                break
    return result


def cell(row, cols, key, default=None):
    col = cols.get(key)
    if not col:
        return default
    value = row[col]
    if pd.isna(value):
        return default
    return value


def dec(value, default="0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    try:
        return Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return Decimal(default)


def get_or_create_supplier(db: Session, name: str | None) -> Supplier | None:
    if not name:
        return None
    clean = str(name).strip()
    supplier = db.scalar(select(Supplier).where(Supplier.name == clean))
    if not supplier:
        supplier = Supplier(name=clean)
        db.add(supplier)
        db.flush()
    return supplier


def get_or_create_category(db: Session, name: str | None) -> Category | None:
    if not name:
        return None
    clean = str(name).strip()
    category = db.scalar(select(Category).where(Category.name == clean))
    if not category:
        category = Category(name=clean)
        db.add(category)
        db.flush()
    return category


@router.post("/import/products", response_model=ImportResult)
async def import_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    name = (file.filename or "").lower()
    content = await file.read()
    try:
        if name.endswith(".csv"):
            try:
                df = pd.read_csv(StringIO(content.decode("utf-8-sig")))
            except UnicodeDecodeError:
                df = pd.read_csv(StringIO(content.decode("latin-1")))
        elif name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(BytesIO(content))
        else:
            raise HTTPException(status_code=422, detail="Formato no válido. Usá CSV o Excel (.xlsx)")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=422, detail=f"No se pudo leer el archivo: {exc}")

    cols = map_columns(df)
    if "barcode" not in cols or "name" not in cols:
        raise HTTPException(status_code=422, detail="El archivo debe incluir Código de barras y Nombre")

    created = updated = adjusted = 0
    errors: list[str] = []
    for idx, row in df.iterrows():
        line = idx + 2
        barcode_raw = cell(row, cols, "barcode")
        product_name = cell(row, cols, "name")
        if barcode_raw is None or product_name is None:
            errors.append(f"Fila {line}: falta código de barras o nombre")
            continue
        barcode = str(barcode_raw).strip()
        if barcode.endswith(".0") and barcode.replace(".0", "").isdigit():
            barcode = barcode[:-2]
        try:
            supplier = get_or_create_supplier(db, cell(row, cols, "supplier"))
            category = get_or_create_category(db, cell(row, cols, "category"))
            desired_stock = dec(cell(row, cols, "stock", 0))
            product = db.scalar(select(Product).where(Product.barcode == barcode))
            if not product:
                product = Product(
                    barcode=barcode,
                    name=str(product_name).strip(),
                    description=cell(row, cols, "description"),
                    category_id=category.id if category else None,
                    brand=cell(row, cols, "brand"),
                    unit=str(cell(row, cols, "unit", "Unidad")),
                    stock_current=Decimal("0"),
                    stock_min=dec(cell(row, cols, "stock_min", 0)),
                    stock_target=dec(cell(row, cols, "stock_target", 0)),
                    supplier_id=supplier.id if supplier else None,
                    supplier_code=cell(row, cols, "supplier_code"),
                    purchase_price=dec(cell(row, cols, "purchase_price"), "0") if cell(row, cols, "purchase_price") is not None else None,
                    sale_price=dec(cell(row, cols, "sale_price"), "0") if cell(row, cols, "sale_price") is not None else None,
                    location=cell(row, cols, "location"),
                    notes=cell(row, cols, "notes"),
                )
                db.add(product)
                db.flush()
                created += 1
            else:
                product.name = str(product_name).strip()
                product.category_id = category.id if category else product.category_id
                product.brand = cell(row, cols, "brand", product.brand)
                product.unit = str(cell(row, cols, "unit", product.unit))
                product.stock_min = dec(cell(row, cols, "stock_min", product.stock_min))
                product.stock_target = dec(cell(row, cols, "stock_target", product.stock_target))
                product.supplier_id = supplier.id if supplier else product.supplier_id
                product.supplier_code = cell(row, cols, "supplier_code", product.supplier_code)
                product.location = cell(row, cols, "location", product.location)
                updated += 1

            current = Decimal(product.stock_current)
            if desired_stock != current:
                sign = 1 if desired_stock > current else -1
                qty = abs(desired_stock - current)
                apply_movement(
                    db,
                    product=product,
                    movement_type=MovementType.ADJUSTMENT,
                    quantity=qty,
                    user=user,
                    notes=f"Ajuste por importación, fila {line}",
                    explicit_sign=sign,
                    commit=False,
                )
                adjusted += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            errors.append(f"Fila {line}: {getattr(exc, 'detail', str(exc))}")

    return ImportResult(created=created, updated=updated, adjusted_stock=adjusted, errors=errors[:100])


def export_dataframe(db: Session) -> pd.DataFrame:
    products = db.scalars(
        select(Product).options(selectinload(Product.category), selectinload(Product.supplier)).where(Product.active.is_(True)).order_by(Product.name)
    ).all()
    rows = []
    for p in products:
        rows.append({
            "ID": p.id,
            "Código de barras": p.barcode,
            "Nombre": p.name,
            "Descripción": p.description,
            "Categoría": p.category.name if p.category else "",
            "Marca": p.brand,
            "Unidad": p.unit,
            "Stock actual": p.stock_current,
            "Stock mínimo": p.stock_min,
            "Stock objetivo": p.stock_target,
            "Proveedor": p.supplier.name if p.supplier else "",
            "Código proveedor": p.supplier_code,
            "Precio compra": p.purchase_price,
            "Precio venta": p.sale_price,
            "Ubicación": p.location,
            "Observaciones": p.notes,
        })
    return pd.DataFrame(rows)


@router.get("/export/products.csv")
def export_csv(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    df = export_dataframe(db)
    content = df.to_csv(index=False).encode("utf-8-sig")
    return StreamingResponse(BytesIO(content), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=stock_ferreteria.csv"})


@router.get("/export/products.xlsx")
def export_xlsx(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    df = export_dataframe(db)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Stock", index=False)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=stock_ferreteria.xlsx"},
    )
