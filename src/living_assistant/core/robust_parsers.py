import traceback
import sys

def get_robust_traceback(exc: Exception, max_chars: int = 3000) -> str:
    """
    Battle-tested traceback extractor (inspired by Aider/OpenDevin).
    - Filters out internal orchestrator noise.
    - Truncates from the middle to preserve context window limits.
    - Captures SyntaxError specifics natively.
    """
    if isinstance(exc, SyntaxError):
        # Syntax errors need special handling to show the caret (^)
        lines = traceback.format_exception_only(type(exc), exc)
        tb_str = "".join(lines)
    else:
        # Extract full traceback
        tb = traceback.extract_tb(exc.__traceback__)
        
        # Filter out internal orchestrator frames to not confuse the LLM
        # (Only keep frames that actually belong to the tools/skills)
        filtered_tb = [frame for frame in tb if "living_assistant/agents/orchestrator.py" not in frame.filename]
        
        if not filtered_tb:
            filtered_tb = tb # Fallback if everything was filtered
            
        formatted_tb = traceback.format_list(filtered_tb)
        lines = formatted_tb + traceback.format_exception_only(type(exc), exc)
        tb_str = "".join(lines)

    # Smart Truncation (Keep top and bottom, remove middle)
    if len(tb_str) > max_chars:
        half = max_chars // 2 - 20
        tb_str = tb_str[:half] + "\n\n... [TRUNCATED FOR LENGTH] ...\n\n" + tb_str[-half:]
        
    return tb_str
