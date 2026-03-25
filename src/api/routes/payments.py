"""
API Endpoints для работы с платежной системой ЮKassa.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from decimal import Decimal
from typing import Dict, Any, Optional

from src.core.database import get_db
from src.api.models.models import User, Subscription, PaymentTransaction
from src.api.services.yookassa_service import yookassa_service

router = APIRouter(prefix="/payments", tags=["Payments"])


# Временная заглушка для зависимости авторизации
async def get_current_user(token: str = None):
    """Заглушка - реализовать реальную проверку токена"""
    # TODO: Заменить на реальную проверку JWT токена
    return User(id=1, email="demo@example.com", is_admin=False)


@router.post("/create")
async def create_payment(
    tariff_plan: str,
    return_url: str,
    save_card: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создание платежа для оплаты подписки.
    
    - **tariff_plan**: Тарифный план (BASIC, PRO, ENTERPRISE)
    - **return_url**: URL возврата после оплаты
    - **save_card**: Сохранить карту для автопродления
    """
    # Получение стоимости тарифа
    tariff_prices = {
        "BASIC": Decimal("990.00"),
        "PRO": Decimal("2990.00"),
        "ENTERPRISE": Decimal("9990.00")
    }
    
    if tariff_plan not in tariff_prices:
        raise HTTPException(status_code=400, detail="Неверный тарифный план")
    
    amount = tariff_prices[tariff_plan]
    
    try:
        payment_data = yookassa_service.create_subscription_payment(
            user=current_user,
            tariff_plan=tariff_plan,
            amount=amount,
            return_url=return_url,
            save_card=save_card
        )
        
        return {
            "payment_id": payment_data["id"],
            "confirmation_url": payment_data["confirmation"]["confirmation_url"],
            "amount": str(amount),
            "currency": "RUB",
            "tariff_plan": tariff_plan,
            "demo_mode": payment_data.get("demo_mode", False),
            "status": payment_data["status"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{payment_id}")
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получение статуса платежа."""
    try:
        payment_info = yookassa_service.get_payment_info(payment_id)
        
        # Проверка принадлежности платежа пользователю
        result = await db.execute(
            select(PaymentTransaction).where(PaymentTransaction.payment_id == payment_id)
        )
        transaction = result.scalar_one_or_none()
        
        if transaction and transaction.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        return {
            "payment_id": payment_info["id"],
            "status": payment_info["status"],
            "amount": payment_info["amount"]["value"],
            "currency": payment_info["amount"]["currency"],
            "created_at": payment_info.get("created_at"),
            "demo_mode": payment_info.get("demo_mode", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook", include_in_schema=False)
async def yookassa_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Вебхук для обработки уведомлений от ЮKassa.
    Этот endpoint не требует авторизации, вызывается ЮKassa.
    """
    try:
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature", "")
        
        # Обработка вебхука
        result = yookassa_service.handle_webhook(body.decode(), signature)
        
        if result["status"] == "success":
            # Фоновая обработка успешного платежа
            background_tasks.add_task(
                process_successful_payment,
                result,
                db
            )
        
        return JSONResponse(content={"status": "accepted"})
        
    except Exception as e:
        # Возвращаем ошибку, но не ломаем работу основного приложения
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )


async def process_successful_payment(
    result: Dict[str, Any],
    db: AsyncSession
):
    """
    Фоновая обработка успешного платежа.
    Активация подписки, отправка уведомлений и т.д.
    """
    user_id = result.get("user_id")
    plan = result.get("plan")
    
    if not user_id or not plan:
        return
    
    # Получение пользователя
    result_query = await db.execute(select(User).where(User.id == int(user_id)))
    user = result_query.scalar_one_or_none()
    
    if not user:
        return
    
    # TODO: Активация подписки
    # await subscription_service.activate_subscription(db=db, user=user, tariff_plan=plan)
    
    # TODO: Отправка email уведомления об успешной оплате
    # await email_service.send_payment_success(user.email, plan)


@router.post("/refund/{payment_id}")
async def refund_payment(
    payment_id: str,
    amount: Optional[Decimal] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Возврат средств по платежу.
    Доступно только администраторам.
    """
    # Проверка прав администратора
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="Требуется права администратора")
    
    try:
        refund_result = yookassa_service.refund_payment(payment_id, amount)
        
        return {
            "refund_id": refund_result["id"],
            "payment_id": refund_result["payment_id"],
            "status": refund_result["status"],
            "amount": refund_result["amount"]["value"],
            "currency": refund_result["amount"]["currency"],
            "demo_mode": refund_result.get("demo_mode", False)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
