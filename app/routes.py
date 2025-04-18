import os
import textwrap

from datetime import timedelta
from starlette.config import Config
from openai import OpenAI
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import EmailRequest, EmailResponse, EmailLogCreate, EmailLogRead, UserRead, UserCreate, UserCreateInternal
from .database import get_session
from .crud import crud_email_logs, crud_users
from .helper import create_access_token, get_current_user, Token, get_password_hash, verify_password

current_file_dir = os.path.dirname(os.path.realpath(__file__))
env_path = os.path.join(current_file_dir, ".env")

config = Config(env_path)

OPENAI_API_KEY = config("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Email routes
email_router = APIRouter()


@email_router.post("/", response_model=EmailResponse)
async def generate_email(
    request: EmailRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    try:
        prompt = textwrap.dedent(f"""
        Write an email based on the following input:
        - User Input: {request.user_input}
        - Reply To: {request.reply_to if request.reply_to else "N/A"}
        - Context: {request.context if request.context else "N/A"}
        - Length: {request.length if request.length else "N/A"} characters
        - Tone: {request.tone if request.tone else "N/A"}
        """)

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful email assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=request.length,
        )
        generated_email = response.choices[0].message.content

        if generated_email is None:
            raise HTTPException(status_code=500, detail="Failure from OpenAI")
        

        log_entry = EmailLogCreate(
            user_id=current_user["id"],
            user_input=request.user_input,
            reply_to=request.reply_to,
            context=request.context,
            length=request.length,
            tone=request.tone,
            generated_email=generated_email,
        )
        await crud_email_logs.create(db, log_entry)

        return EmailResponse(generated_email=generated_email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Email log routes
log_router = APIRouter()


@log_router.get("/")
async def read_logs(
    db: AsyncSession = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    logs = await crud_email_logs.get_multi(db, user_id=current_user["id"])
    return logs


@log_router.get("/{log_id}", response_model=EmailLogRead)
async def read_log(
    log_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    log = await crud_email_logs.get(db, id=log_id, user_id=current_user["id"])
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


# User routes
user_router = APIRouter()


@user_router.post("/register", response_model=UserRead)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_session)):
    hashed_password = get_password_hash(user.password)
    user_data = user.model_dump()
    user_data["hashed_password"] = hashed_password
    del user_data["password"]

    new_user = await crud_users.create(db, object=UserCreateInternal(**user_data))
    return new_user


@user_router.post("/login", response_model=Token)
async def login_user(user: UserCreate, db: AsyncSession = Depends(get_session)):
    db_user = await crud_users.get(db, email=user.email)
    password_verified = await verify_password(user.password, db_user.hashed_password)
    if not db_user or not password_verified:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=30)
    access_token = await create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
