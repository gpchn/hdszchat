from PIL import Image
from typing import List
from pathlib import Path
from threading import Thread
from datetime import datetime
from pystray import MenuItem, Icon
from sys import platform as PLATFORM
from os import startfile, system, _exit
from colorama import init as init_color
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

init_color()


# 系统托盘模块
class SysTray:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.icon = None
        self._init_icon()

    def _init_icon(self):
        """初始化托盘图标"""
        # 加载图标文件
        image = Image.open("icon.ico")

        menu = (
            MenuItem("查看日志", self._open_log),
            MenuItem("退出", self._on_exit),
        )

        self.icon = Icon("HDSZchat", image, "HDSZchat", menu)

    def _open_log(self, *args):
        """打开最新日志文件"""
        latest_log = self._get_latest_log()
        if latest_log:
            if PLATFORM == "win32":
                startfile(latest_log)
            elif PLATFORM == "darwin":
                system(f"open '{latest_log}'")
            else:
                system(f"xdg-open '{latest_log}'")

    def _on_exit(self, *args):
        """退出程序"""
        self.icon.stop()
        _exit(0)

    def _get_latest_log(self):
        """获取最新的日志文件"""
        log_files = list(self.log_dir.glob("*.log"))
        if log_files:
            return max(log_files, key=lambda x: x.stat().st_ctime)
        return None

    def run(self):
        """在独立线程运行托盘图标"""
        Thread(target=self.icon.run, daemon=True).start()


# WebSocket 连接管理器
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


def configure_logging():
    """配置日志系统"""
    log_dir = Path("log")
    log_dir.mkdir(parents=True, exist_ok=True)

    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_dir / f"{current_time}.log"

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
                "use_colors": False,
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
    return log_config, log_dir


def start_server():
    from uvicorn import run
    from tomllib import loads

    # 读取配置文件
    cfg_path = Path("server_config.toml")
    cfg = loads(cfg_path.read_text())

    # 配置日志
    log_config, log_dir = configure_logging()

    # 启动系统托盘
    tray = SysTray(log_dir)
    tray.run()

    # 启动FastAPI服务
    run(
        app=app,
        host=cfg["host"],
        port=cfg["port"],
        log_config=log_config,
        # 以下参数防止uvicorn占用主线程
        reload=False,
        workers=1,
        loop="asyncio",
    )


if __name__ == "__main__":
    start_server()
