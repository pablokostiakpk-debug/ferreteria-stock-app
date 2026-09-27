from datetime import datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Product, StockMovement, User
from ..schemas import DashboardOut
from ..time_utils import now_local

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    today_start = datetime.combine(now_local().date(), time.min)
    total = db.scalar(select(func.count()).select_from(Product).where(Product.active.is_(True))) or 0
    low = db.scalar(
        select(func.count()).select_from(Product).where(
            Product.active.is_(True), Product.stock_current > 0, Product.stock_current <= Product.stock_min
        )
    ) or 0
    out = db.scalar(
        select(func.count()).select_from(Product).where(Product.active.is_(True), Product.stock_current <= 0)
    ) or 0
    movements_today = db.scalar(
        select(func.count()).select_from(StockMovement).where(StockMovement.created_at >= today_start)
    ) or 0
    recent = list(db.scalars(select(StockMovement).order_by(StockMovement.created_at.desc()).limit(8)).all())
    return DashboardOut(
        total_products=total,
        low_stock=low,
        out_of_stock=out,
        movements_today=movements_today,
        recent_movements=recent,
    )
