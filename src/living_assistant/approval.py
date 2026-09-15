from __future__ import annotations
from dataclasses import dataclass
from rich.console import Console

console = Console()

@dataclass
class ApprovalManager:
    interactive: bool = True

    def approve(self, action: str, reason: str) -> bool:
        if not self.interactive:
            return False
        console.print(f"[yellow]Approval required[/yellow]: {action}")
        console.print(f"[dim]{reason}[/dim]")
        answer = input("Allow? [y/N]: ").strip().lower()
        return answer in {"y", "yes"}
