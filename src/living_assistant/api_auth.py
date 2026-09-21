import os
import secrets
import string
from pathlib import Path
from .config import data_dir

def ensure_api_token() -> tuple[str, Path, bool]:
    """Ensure a secure random API token exists in the data directory and return it."""
    token_path = Path(data_dir()) / 'api_token'
    created = False
    
    # In-memory environment override for testing/CI or explicit user choice
    if 'ASSISTANT_API_TOKEN' in os.environ:
        return os.environ['ASSISTANT_API_TOKEN'], token_path, False
        
    if not token_path.exists():
        token_path.parent.mkdir(parents=True, exist_ok=True)
        # Generate 32 char secure random token
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(32))
        token_path.write_text(token, encoding='utf-8')
        # Secure file permissions on POSIX
        if os.name != 'nt':
            token_path.chmod(0o600)
        created = True
        
    token = token_path.read_text(encoding='utf-8').strip()
    return token, token_path, created

def get_api_token() -> str:
    token, _, _ = ensure_api_token()
    return token
