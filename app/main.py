from fastapi import FastAPI
from .database import create_db_and_tables
from .routes import email_router, log_router, user_router


async def lifespan(app):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(email_router, prefix="/generate", tags=["Email"])
app.include_router(log_router, prefix="/logs", tags=["Logs"])
app.include_router(user_router, prefix="/users", tags=["Users"])
