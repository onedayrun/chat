"""
OneDay.run Platform - Component Library Service
Zarządza biblioteką reużywalnych komponentów
"""
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import asyncio


class ComponentCategory(Enum):
    AUTH = "auth"
    DATABASE = "database"
    API = "api"
    UI = "ui"
    INTEGRATION = "integration"
    UTILS = "utils"
    DEPLOYMENT = "deployment"
    TESTING = "testing"


@dataclass
class Component:
    """Reprezentuje reużywalny komponent"""
    id: str
    name: str
    description: str
    category: ComponentCategory
    tech_stack: List[str]
    files: List[Dict[str, str]]  # path -> content
    dependencies: List[str]
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    usage_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "tech_stack": self.tech_stack,
            "files": self.files,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "version": self.version
        }


class ComponentLibrary:
    """
    Biblioteka reużywalnych komponentów
    Przechowuje gotowe moduły do szybkiego wykorzystania w projektach
    """
    
    def __init__(self):
        self.components: Dict[str, Component] = {}
        self._load_default_components()
    
    def _load_default_components(self):
        """Ładuje domyślne komponenty"""
        
        # AUTH - FastAPI JWT
        self.add_component(Component(
            id="auth-fastapi-jwt",
            name="FastAPI JWT Authentication",
            description="Kompletny system autentykacji JWT dla FastAPI z refresh tokenami",
            category=ComponentCategory.AUTH,
            tech_stack=["python", "fastapi"],
            dependencies=["python-jose[cryptography]", "passlib[bcrypt]", "pydantic"],
            tags=["auth", "jwt", "security", "fastapi"],
            files=[
                {
                    "path": "src/auth/__init__.py",
                    "content": ""
                },
                {
                    "path": "src/auth/config.py",
                    "content": '''"""Auth Configuration"""
from pydantic_settings import BaseSettings

class AuthSettings(BaseSettings):
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    class Config:
        env_prefix = "AUTH_"

auth_settings = AuthSettings()
'''
                },
                {
                    "path": "src/auth/models.py",
                    "content": '''"""Auth Models"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool = True
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
'''
                },
                {
                    "path": "src/auth/security.py",
                    "content": '''"""Security utilities"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import auth_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, auth_settings.SECRET_KEY, algorithm=auth_settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, auth_settings.SECRET_KEY, algorithm=auth_settings.ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, auth_settings.SECRET_KEY, algorithms=[auth_settings.ALGORITHM])
        return payload
    except JWTError:
        return None
'''
                },
                {
                    "path": "src/auth/dependencies.py",
                    "content": '''"""Auth Dependencies for FastAPI"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .security import decode_token
from .models import TokenData

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    
    return TokenData(
        user_id=payload.get("sub"),
        email=payload.get("email")
    )

async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    # Add additional checks here (e.g., is_active from database)
    return current_user
'''
                },
                {
                    "path": "src/auth/router.py",
                    "content": '''"""Auth Router"""
from fastapi import APIRouter, Depends, HTTPException, status
from .models import UserCreate, UserResponse, Token
from .security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token

router = APIRouter(prefix="/auth", tags=["authentication"])

# In-memory user store (replace with database)
fake_users_db = {}
user_id_counter = 1

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    global user_id_counter
    
    if user.email in fake_users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    from datetime import datetime
    new_user = {
        "id": user_id_counter,
        "email": user.email,
        "username": user.username,
        "hashed_password": get_password_hash(user.password),
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    fake_users_db[user.email] = new_user
    user_id_counter += 1
    
    return UserResponse(**new_user)

@router.post("/login", response_model=Token)
async def login(email: str, password: str):
    user = fake_users_db.get(email)
    
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    token_data = {"sub": user["id"], "email": user["email"]}
    
    return Token(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data)
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    payload = decode_token(refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    token_data = {"sub": payload["sub"], "email": payload.get("email")}
    
    return Token(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data)
    )
'''
                }
            ]
        ))
        
        # DATABASE - SQLAlchemy Base
        self.add_component(Component(
            id="db-sqlalchemy-base",
            name="SQLAlchemy Base Setup",
            description="Konfiguracja SQLAlchemy z async support i base modelami",
            category=ComponentCategory.DATABASE,
            tech_stack=["python", "sqlalchemy"],
            dependencies=["sqlalchemy[asyncio]", "asyncpg", "alembic"],
            tags=["database", "orm", "sqlalchemy", "async"],
            files=[
                {
                    "path": "src/database/__init__.py",
                    "content": "from .base import Base, get_db, engine, async_session"
                },
                {
                    "path": "src/database/base.py",
                    "content": '''"""Database Configuration"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, DateTime, func
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    """Base model with common fields"""
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
'''
                },
                {
                    "path": "alembic.ini",
                    "content": '''[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
'''
                }
            ]
        ))
        
        # API - CRUD Base
        self.add_component(Component(
            id="api-crud-base",
            name="Generic CRUD Operations",
            description="Bazowa klasa CRUD dla FastAPI z paginacją i filtrowaniem",
            category=ComponentCategory.API,
            tech_stack=["python", "fastapi", "sqlalchemy"],
            dependencies=["fastapi", "sqlalchemy"],
            tags=["crud", "api", "rest", "generic"],
            files=[
                {
                    "path": "src/crud/__init__.py",
                    "content": "from .base import CRUDBase"
                },
                {
                    "path": "src/crud/base.py",
                    "content": '''"""Generic CRUD Base Class"""
from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()
    
    async def get_multi(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ModelType]:
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def get_count(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(self.model.id)))
        return result.scalar()
    
    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self, 
        db: AsyncSession, 
        *, 
        db_obj: ModelType, 
        obj_in: UpdateSchemaType
    ) -> ModelType:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj
    
    async def delete(self, db: AsyncSession, *, id: int) -> bool:
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            return True
        return False
'''
                }
            ]
        ))
        
        # INTEGRATION - Stripe Payment
        self.add_component(Component(
            id="integration-stripe",
            name="Stripe Payment Integration",
            description="Integracja płatności Stripe z webhooks",
            category=ComponentCategory.INTEGRATION,
            tech_stack=["python", "fastapi"],
            dependencies=["stripe"],
            tags=["payment", "stripe", "integration", "webhooks"],
            files=[
                {
                    "path": "src/integrations/stripe/__init__.py",
                    "content": "from .service import StripeService\nfrom .router import router as stripe_router"
                },
                {
                    "path": "src/integrations/stripe/config.py",
                    "content": '''"""Stripe Configuration"""
from pydantic_settings import BaseSettings

class StripeSettings(BaseSettings):
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CURRENCY: str = "pln"
    
    class Config:
        env_prefix = ""

stripe_settings = StripeSettings()
'''
                },
                {
                    "path": "src/integrations/stripe/service.py",
                    "content": '''"""Stripe Service"""
import stripe
from typing import Optional, Dict, Any
from .config import stripe_settings

stripe.api_key = stripe_settings.STRIPE_SECRET_KEY

class StripeService:
    @staticmethod
    async def create_checkout_session(
        amount: int,
        product_name: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        session = stripe.checkout.Session.create(
            payment_method_types=["card", "p24", "blik"],
            line_items=[{
                "price_data": {
                    "currency": stripe_settings.STRIPE_CURRENCY,
                    "product_data": {"name": product_name},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata or {}
        )
        return {"session_id": session.id, "url": session.url}
    
    @staticmethod
    async def create_customer(email: str, name: str = None) -> str:
        customer = stripe.Customer.create(email=email, name=name)
        return customer.id
    
    @staticmethod
    async def get_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return {
            "id": intent.id,
            "amount": intent.amount,
            "status": intent.status,
            "currency": intent.currency
        }
    
    @staticmethod
    def verify_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
        event = stripe.Webhook.construct_event(
            payload, signature, stripe_settings.STRIPE_WEBHOOK_SECRET
        )
        return event
'''
                },
                {
                    "path": "src/integrations/stripe/router.py",
                    "content": '''"""Stripe Router"""
from fastapi import APIRouter, Request, HTTPException
from .service import StripeService

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/create-checkout")
async def create_checkout(
    amount: int,
    product_name: str,
    success_url: str,
    cancel_url: str
):
    result = await StripeService.create_checkout_session(
        amount=amount,
        product_name=product_name,
        success_url=success_url,
        cancel_url=cancel_url
    )
    return result

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    
    try:
        event = StripeService.verify_webhook(payload, signature)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Handle events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # Process successful payment
        print(f"Payment successful: {session['id']}")
    
    return {"status": "success"}
'''
                }
            ]
        ))
        
        # UI - React Dashboard Layout
        self.add_component(Component(
            id="ui-react-dashboard",
            name="React Dashboard Layout",
            description="Responsywny layout dashboardu z sidebar i nawigacją",
            category=ComponentCategory.UI,
            tech_stack=["react", "typescript", "tailwindcss"],
            dependencies=["@headlessui/react", "lucide-react"],
            tags=["ui", "dashboard", "layout", "react", "tailwind"],
            files=[
                {
                    "path": "src/components/layout/DashboardLayout.tsx",
                    "content": '''import React, { useState } from 'react';
import { Menu, X, Home, Settings, Users, BarChart } from 'lucide-react';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Analytics', href: '/analytics', icon: BarChart },
  { name: 'Users', href: '/users', icon: Users },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-40 lg:hidden ${sidebarOpen ? '' : 'hidden'}`}>
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
        <div className="fixed inset-y-0 left-0 flex w-64 flex-col bg-white">
          <div className="flex h-16 items-center justify-between px-4">
            <span className="text-xl font-bold text-indigo-600">OneDay</span>
            <button onClick={() => setSidebarOpen(false)}>
              <X className="h-6 w-6" />
            </button>
          </div>
          <nav className="flex-1 space-y-1 px-2 py-4">
            {navigation.map((item) => (
              <a
                key={item.name}
                href={item.href}
                className="group flex items-center px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              >
                <item.icon className="mr-3 h-5 w-5" />
                {item.name}
              </a>
            ))}
          </nav>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex min-h-0 flex-1 flex-col bg-white border-r border-gray-200">
          <div className="flex h-16 items-center px-4">
            <span className="text-xl font-bold text-indigo-600">OneDay</span>
          </div>
          <nav className="flex-1 space-y-1 px-2 py-4">
            {navigation.map((item) => (
              <a
                key={item.name}
                href={item.href}
                className="group flex items-center px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              >
                <item.icon className="mr-3 h-5 w-5" />
                {item.name}
              </a>
            ))}
          </nav>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64">
        <div className="sticky top-0 z-10 flex h-16 bg-white shadow">
          <button
            className="px-4 text-gray-500 lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="flex flex-1 justify-end px-4">
            {/* Header content */}
          </div>
        </div>
        <main className="py-6 px-4 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
};
'''
                }
            ]
        ))
        
        # UTILS - Logger
        self.add_component(Component(
            id="utils-logger",
            name="Structured Logger",
            description="Strukturalny logger z JSON output i rotation",
            category=ComponentCategory.UTILS,
            tech_stack=["python"],
            dependencies=["structlog", "python-json-logger"],
            tags=["logging", "utils", "monitoring"],
            files=[
                {
                    "path": "src/utils/logger.py",
                    "content": '''"""Structured Logger Configuration"""
import logging
import sys
import structlog
from typing import Any

def setup_logging(level: str = "INFO", json_output: bool = True):
    """Configure structured logging"""
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_output:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance"""
    return structlog.get_logger(name)

# Convenience logger
logger = get_logger()
'''
                }
            ]
        ))

    def add_component(self, component: Component) -> bool:
        """Dodaje komponent do biblioteki"""
        self.components[component.id] = component
        return True

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        tech_stack: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Szuka komponentów w bibliotece
        
        Args:
            query: Tekst wyszukiwania
            category: Kategoria (auth, database, api, etc.)
            tech_stack: Stack technologiczny
            limit: Maksymalna liczba wyników
        """
        results = []
        query_lower = query.lower()
        
        for comp in self.components.values():
            score = 0
            
            # Match query against name, description, tags
            if query_lower in comp.name.lower():
                score += 10
            if query_lower in comp.description.lower():
                score += 5
            if any(query_lower in tag for tag in comp.tags):
                score += 3
            
            # Filter by category
            if category and comp.category.value != category:
                continue
            
            # Filter by tech stack
            if tech_stack and tech_stack not in comp.tech_stack:
                continue
            
            if score > 0:
                results.append({
                    "component": comp.to_dict(),
                    "score": score
                })
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "success": True,
            "query": query,
            "count": len(results[:limit]),
            "components": [r["component"] for r in results[:limit]]
        }

    def get_component(self, component_id: str) -> Optional[Component]:
        """Pobiera komponent po ID"""
        return self.components.get(component_id)

    def get_component_files(self, component_id: str) -> List[Dict[str, str]]:
        """Pobiera pliki komponentu"""
        comp = self.components.get(component_id)
        return comp.files if comp else []

    def list_categories(self) -> List[str]:
        """Lista dostępnych kategorii"""
        return [c.value for c in ComponentCategory]

    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Lista komponentów w kategorii"""
        return [
            comp.to_dict() 
            for comp in self.components.values() 
            if comp.category.value == category
        ]


# Global instance
component_library = ComponentLibrary()
