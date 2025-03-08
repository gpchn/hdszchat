from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from pathlib import Path
from colorama import init as init_color
from datetime import datetime
import logging

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

    # 创建日志目录
    log_dir = Path("log")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 生成当前时间的日志文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_dir / f"{current_time}.log"

    # 自定义日志配置
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "filename": str(log_filename),
                "level": "INFO",
                "formatter": "default",
            },
        },
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(asctime)s - %(message)s",
                "use_colors": False,  # 文件日志不需要颜色
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["file"], "level": "INFO", "propagate": False},
            "uvicorn.error": {
                "handlers": ["file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["file"],
                "level": "INFO",
                "propagate": False,
                "formatter": "default",
            },
        },
    }

    run(app, host=cfg["host"], port=cfg["port"], log_config=log_config)


if __name__ == "__main__":
    start_server()
