from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import MovementType, OrderStatus, UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: int
    username: str
    full_name: str | None
    role: UserRole


class CategoryOut(ORMModel):
    id: int
    name: str


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact_name: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class SupplierUpdate(SupplierCreate):
    name: str | None = None


class SupplierOut(ORMModel):
    id: int
    name: str
    contact_name: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    address: str | None
    notes: str | None
    active: bool


class ProductCreate(BaseModel):
    barcode: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=220)
    description: str | None = None
    category: str | None = None
    brand: str | None = None
    unit: str = "Unidad"
    initial_stock: Decimal = Field(default=Decimal("0"), ge=0)
    stock_min: Decimal = Field(default=Decimal("0"), ge=0)
    stock_target: Decimal = Field(default=Decimal("0"), ge=0)
    supplier_id: int | None = None
    supplier_code: str | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    location: str | None = None
    notes: str | None = None


class ProductUpdate(BaseModel):
    barcode: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=220)
    description: str | None = None
    category: str | None = None
    brand: str | None = None
    unit: str | None = None
    stock_min: Decimal | None = Field(default=None, ge=0)
    stock_target: Decimal | None = Field(default=None, ge=0)
    supplier_id: int | None = None
    supplier_code: str | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    location: str | None = None
    notes: str | None = None


class ProductOut(ORMModel):
    id: int
    barcode: str
    name: str
    description: str | None
    brand: str | None
    unit: str
    stock_current: Decimal
    stock_min: Decimal
    stock_target: Decimal
    supplier_code: str | None
    purchase_price: Decimal | None
    sale_price: Decimal | None
    location: str | None
    notes: str | None
    active: bool
    category: CategoryOut | None
    supplier: SupplierOut | None
    needs_restock: bool
    suggested_order: Decimal


class StockMoveIn(BaseModel):
    product_id: int
    movement_type: MovementType
    quantity: Decimal = Field(gt=0)
    notes: str | None = None


class StockMoveByBarcodeIn(BaseModel):
    barcode: str
    movement_type: MovementType
    quantity: Decimal = Field(gt=0)
    notes: str | None = None


class BatchItem(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    notes: str | None = None


class BatchMovementIn(BaseModel):
    movement_type: MovementType = MovementType.WITHDRAWAL
    items: list[BatchItem] = Field(min_length=1)
    notes: str | None = None


class MovementOut(ORMModel):
    id: int
    created_at: datetime
    product_id: int
    barcode_snapshot: str
    product_name_snapshot: str
    movement_type: MovementType
    quantity: Decimal
    stock_before: Decimal
    stock_after: Decimal
    user_id: int
    notes: str | None


class ReplenishmentItem(BaseModel):
    product_id: int
    barcode: str
    name: str
    unit: str
    stock_current: Decimal
    stock_min: Decimal
    stock_target: Decimal
    suggested_order: Decimal
    supplier_id: int | None
    supplier_name: str | None
    category_name: str | None


class OrderItemIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)


class OrderCreateIn(BaseModel):
    supplier_id: int
    items: list[OrderItemIn] = Field(min_length=1)
    intro: str = "Hola, ¿cómo estás?\n\nTe paso un pedido:"
    closing: str = "Cuando puedas pasame precio y disponibilidad.\n\nGracias."


class OrderOut(ORMModel):
    id: int
    supplier_id: int
    created_by_id: int
    created_at: datetime
    status: OrderStatus
    message: str
    notes: str | None


class DashboardOut(BaseModel):
    total_products: int
    low_stock: int
    out_of_stock: int
    movements_today: int
    recent_movements: list[MovementOut]


class ImportResult(BaseModel):
    created: int
    updated: int
    adjusted_stock: int
    errors: list[str]


class HealthOut(BaseModel):
    ok: Literal[True] = True

class GeneratedOrderOut(BaseModel):
    order: OrderOut
    supplier_name: str
    message: str
    whatsapp_url: str | None
