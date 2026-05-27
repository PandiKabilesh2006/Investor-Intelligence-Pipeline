import os

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def load_prompt(filename: str) -> str:
    """
    Safely load a prompt template from the app/prompts folder.
    """
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()
