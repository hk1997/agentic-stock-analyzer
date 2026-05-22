from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.database import get_db_session
from app.models import User, LinkedAccount
from app.auth import get_password_hash, verify_password, create_access_token, decode_access_token
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

router = APIRouter(prefix="/api/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class UserCreate(BaseModel):
    email: str
    password: str
    name: str | None = None

class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None

class LinkAccountRequest(BaseModel):
    target_email: str

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
        
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db_session)):
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed_password, name=user_data.name)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/login")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "name": user.name}}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

@router.post("/link-account")
async def link_account(
    req: LinkAccountRequest, 
    current_user: Annotated[User, Depends(get_current_user)], 
    db: AsyncSession = Depends(get_db_session)
):
    """Link current user's account with another user via email."""
    if req.target_email == current_user.email:
        raise HTTPException(status_code=400, detail="Cannot link account to yourself")
        
    # Find target user
    result = await db.execute(select(User).where(User.email == req.target_email))
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
        
    # Check if link already exists
    link_check = await db.execute(
        select(LinkedAccount).where(
            ((LinkedAccount.user_id == current_user.id) & (LinkedAccount.linked_user_id == target_user.id)) |
            ((LinkedAccount.user_id == target_user.id) & (LinkedAccount.linked_user_id == current_user.id))
        )
    )
    if link_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Accounts are already linked")
        
    # Create symmetrical link (or just one-way for simplicity, but symmetrical is better for unified views)
    link1 = LinkedAccount(user_id=current_user.id, linked_user_id=target_user.id)
    link2 = LinkedAccount(user_id=target_user.id, linked_user_id=current_user.id)
    db.add(link1)
    db.add(link2)
    await db.commit()
    
    return {"status": "success", "message": f"Successfully linked with {target_user.email}"}

@router.get("/linked-accounts")
async def get_linked_accounts(
    current_user: Annotated[User, Depends(get_current_user)], 
    db: AsyncSession = Depends(get_db_session)
):
    """Get a list of all users linked to the current user."""
    # Join LinkedAccount with User
    result = await db.execute(
        select(User.id, User.email, User.name)
        .join(LinkedAccount, LinkedAccount.linked_user_id == User.id)
        .where(LinkedAccount.user_id == current_user.id)
    )
    links = result.all()
    return [{"id": l.id, "email": l.email, "name": l.name} for l in links]
