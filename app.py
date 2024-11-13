from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import time

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
redis_client = redis.StrictRedis(host="localhost", port=6379, decode_responses=True)

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

# Allowed colors for the board (can be expanded)
ALLOWED_COLORS = {"red", "blue", "green", "yellow", "black", "white"}

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

@app.post("/update_pixel")
async def update_pixel(update: PixelUpdate):
    # Check if color is valid
    if update.color not in ALLOWED_COLORS:
        raise HTTPException(status_code=400, detail="Invalid color")

    # Validate coordinates
    if not (0 <= update.x < BOARD_WIDTH and 0 <= update.y < BOARD_HEIGHT):
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    # Cooldown check
    last_update_time = redis_client.get(f"cooldown:{update.user_id}")
    current_time = time.time()

    if last_update_time and current_time - float(last_update_time) < COOLDOWN_SECONDS:
        remaining_time = COOLDOWN_SECONDS - (current_time - float(last_update_time))
        raise HTTPException(
            status_code=429, detail=f"Cooldown active. Please wait {remaining_time:.1f} seconds."
        )

    # Update the pixel color
    redis_client.hset("board", f"{update.x},{update.y}", update.color)
    redis_client.setex(f"cooldown:{update.user_id}", COOLDOWN_SECONDS, current_time)

    # Broadcast the update to all clients
    update_message = {
        "x": update.x,
        "y": update.y,
        "color": update.color
    }
    await manager.broadcast(update_message)

    return {"message": "Pixel updated successfully"}

@app.get("/board")
def get_board():
    board = redis_client.hgetall("board")
    return {"board": board}
