from __future__ import annotations
import psutil, platform
from .base import Tool
from ..memory import MemoryStore

def build_personal_tools(memory: MemoryStore) -> list[Tool]:
    def remember(text: str, kind: str = "fact"):
        return {"ok":True,"id":memory.remember(text, kind)}

    def memory_search(query: str):
        return memory.search(query)

    def todo_add(title: str, due_at: str | None = None):
        return {"ok":True,"id":memory.add_todo(title,due_at)}

    def todo_list(include_done: bool = False):
        return memory.list_todos(include_done)

    def system_status():
        vm = psutil.virtual_memory()
        return {
            "os":platform.system(),
            "cpu_percent":psutil.cpu_percent(interval=0.3),
            "ram_percent":vm.percent,
            "ram_available_gb":round(vm.available/(1024**3),2),
            "disk_percent":psutil.disk_usage("/").percent,
        }

    return [
        Tool("remember", "Store a non-secret fact/preference/project note in local memory.",
             {"type":"object","properties":{"text":{"type":"string"},"kind":{"type":"string","default":"fact"}},"required":["text"]}, remember),
        Tool("memory_search", "Search local assistant memory.",
             {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, memory_search),
        Tool("todo_add", "Add a local todo/reminder. due_at should be ISO-like text if known.",
             {"type":"object","properties":{"title":{"type":"string"},"due_at":{"type":"string"}},"required":["title"]}, todo_add),
        Tool("todo_list", "List local todos/reminders.",
             {"type":"object","properties":{"include_done":{"type":"boolean","default":False}}}, todo_list),
        Tool("system_status", "Read CPU, RAM and disk status of this machine.",
             {"type":"object","properties":{}}, system_status),
    ]
