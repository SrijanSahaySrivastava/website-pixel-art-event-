from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
import redis
import time
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Connect to Redis
redis_client = redis.StrictRedis(host="ec2-13-233-190-109.ap-south-1.compute.amazonaws.com", port=6379, decode_responses=True)

# Define board dimensions and cooldown period (e.g., 5 seconds)
BOARD_WIDTH = 100
BOARD_HEIGHT = 100
COOLDOWN_SECONDS = 5

# Initialize board in Redis if not already set
def initialize_board():
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            redis_client.hset("board", f"{x},{y}", "white")  # Default color for each pixel

initialize_board()

class PixelUpdate(BaseModel):
    x: int
    y: int
    color: str
    user_id: str
    username: str

class UserCreate(BaseModel):
    username: str
    password: str

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Manage connected WebSocket clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep the connection open
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Authentication setup
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.username,
        full_name=user.username,
        hashed_password=hashed_password,
        disabled=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

@app.post("/update_pixel")
async def update_pixel(update: PixelUpdate, current_user: User = Depends(get_current_active_user)):
    print(f"Received update: {update}")  # Log the received payload

    # Validate coordinates
    if not (0 <= update.x < BOARD_WIDTH and 0 <= update.y < BOARD_HEIGHT):
        print(f"Invalid coordinates: x={update.x}, y={update.y}")
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    # Cooldown check
    last_update_time = redis_client.get(f"cooldown:{update.user_id}")
    current_time = time.time()

    if last_update_time and current_time - float(last_update_time) < COOLDOWN_SECONDS:
        remaining_time = COOLDOWN_SECONDS - (current_time - float(last_update_time))
        print(f"Cooldown active for user_id={update.user_id}, remaining_time={remaining_time:.1f} seconds")
        raise HTTPException(
            status_code=429, detail=f"Cooldown active. Please wait {remaining_time:.1f} seconds."
        )

    # Update the pixel color and save the username
    redis_client.hset("board", f"{update.x},{update.y}", f"{update.color},{update.username}")
    redis_client.setex(f"cooldown:{update.user_id}", COOLDOWN_SECONDS, current_time)

    # Broadcast the update to all clients
    update_message = {
        "x": update.x,
        "y": update.y,
        "color": update.color,
        "username": update.username
    }
    await manager.broadcast(update_message)

    return {"message": "Pixel updated successfully"}

@app.post("/update_pixel_no_cooldown")
async def update_pixel_no_cooldown(update: PixelUpdate, current_user: User = Depends(get_current_active_user)):
    print(f"Received update without cooldown: {update}")  # Log the received payload

    # Validate coordinates
    if not (0 <= update.x < BOARD_WIDTH and 0 <= update.y < BOARD_HEIGHT):
        print(f"Invalid coordinates: x={update.x}, y={update.y}")
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    # Update the pixel color and save the username
    redis_client.hset("board", f"{update.x},{update.y}", f"{update.color},{update.username}")

    # Broadcast the update to all clients
    update_message = {
        "x": update.x,
        "y": update.y,
        "color": update.color,
        "username": update.username
    }
    await manager.broadcast(update_message)

    return {"message": "Pixel updated successfully without cooldown"}

@app.get("/board")
def get_board(current_user: User = Depends(get_current_active_user)):
    board = redis_client.hgetall("board")
    formatted_board = {k: v.split(',')[0] for k, v in board.items()}  # Extract only the color for display
    sorted_board = dict(sorted(formatted_board.items(), key=lambda item: (int(item[0].split(',')[0]), int(item[0].split(',')[1]))))
    return {"board": sorted_board}