import asyncio
import tkinter as tk
from pathlib import Path
from threading import Thread
from websockets import connect
from tomllib import loads as toml_loads

cfg_path = Path("config.toml")
cfg = toml_loads(cfg_path.read_text())
USER_NAME = cfg.get("user").get("name")
SERVER_HOST = cfg.get("server").get("host")
SERVER_PORT = cfg.get("server").get("port")

# 全局队列用于存放发送消息
send_queue = asyncio.Queue()


class ChatClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Client")
        # 将状态检测标签放到顶端
        self.status_label = tk.Label(root, text="未连接", fg="red")
        self.status_label.pack(pady=(10, 5))
        self.text_area = tk.Text(root, state="disabled", width=50, height=20)
        self.text_area.pack(padx=10, pady=10)
        self.entry = tk.Entry(root, width=40)
        # 添加回车发送消息的绑定
        self.entry.bind("<Return>", lambda event: self.send_message())
        self.entry.pack(side=tk.LEFT, padx=(10, 0), pady=(0, 10))
        self.send_button = tk.Button(root, text="发送", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=(5, 10), pady=(0, 10))

    def append_message(self, message):
        def task():
            self.text_area.configure(state="normal")
            self.text_area.insert(tk.END, message + "\n")
            self.text_area.configure(state="disabled")
            self.text_area.see(tk.END)

        self.root.after(0, task)

    def send_message(self):
        msg = self.entry.get()
        if msg:
            asyncio.run_coroutine_threadsafe(send_queue.put(msg), loop)
            self.entry.delete(0, tk.END)

    def update_status(self, status):
        # 状态为“已连接”时变绿，否则红色提示
        color = "green" if status == "已连接" else "red"
        self.status_label.config(text=status, fg=color)


async def chat_client():
    uri = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/{USER_NAME}"
    try:
        async with connect(uri) as websocket:
            # 连接成功时更新状态栏
            gui.root.after(0, gui.update_status, "已连接")
            # 消息接收协程
            async def receive_messages():
                while True:
                    message = await websocket.recv()
                    gui.append_message(message)

            # 消息发送协程
            async def send_messages():
                while True:
                    message = await send_queue.get()
                    await websocket.send(message)

            await asyncio.gather(receive_messages(), send_messages())
    except Exception:
        # 出现异常（例如断开连接）时更新状态栏
        gui.root.after(0, gui.update_status, "断开连接")


# 在后台线程运行 asyncio 事件循环
def start_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(chat_client())


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    Thread(target=start_async_loop, args=(loop,), daemon=True).start()
    root = tk.Tk()
    gui = ChatClientGUI(root)
    root.mainloop()
