from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from pathlib import Path
from colorama import init as init_color

init_color()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.users = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.users[websocket] = username
        await self.broadcast(f"[系统] {username} 进入聊天室")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            username = self.users.pop(websocket, "未知用户")
            return f"[系统] {username} 离开聊天室"

    async def broadcast(self, message: str):
        logging.info(message)  # 记录日志
        for connection in self.active_connections:
            await connection.send_text(message)


app = FastAPI()
manager = ConnectionManager()


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(websocket, username)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{username}: {data}")
    except WebSocketDisconnect:
        msg = manager.disconnect(websocket)
        await manager.broadcast(msg)


def start_server():
    from uvicorn import run
    from tomllib import loads

    cfg_path = Path("server_config.toml")
    cfg = loads(cfg_path.read_text())

    run(app, host=cfg["host"], port=cfg["port"])


if __name__ == "__main__":
    start_server()
