from fastapi import WebSocket
from typing import Dict, List


class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, student_id: str):
        await websocket.accept()
        self.connections.setdefault(student_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, student_id: str):
        if student_id in self.connections and websocket in self.connections[student_id]:
            self.connections[student_id].remove(websocket)
            if not self.connections[student_id]:
                del self.connections[student_id]

    async def send_to_student(self, student_id: str, message: dict):
        if student_id not in self.connections:
            return
        dead = []
        for ws in self.connections[student_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, student_id)

    async def broadcast(self, message: dict):
        for student_id in list(self.connections.keys()):
            await self.send_to_student(student_id, message)


ws_manager = WebSocketManager()
