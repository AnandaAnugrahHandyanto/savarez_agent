import re

def clean_response(text: str) -> str:
    """
    Standardized response cleaning for all Hermes delivery paths.
    - Strips <thought> blocks
    - Normalizes common LaTeX symbols to Unicode
    - Cleans up remaining LaTeX delimiters
    """
    if not text:
        return ""

    # 1. Strip <thought>...</thought> tags (case-insensitive, multi-line)
    text = re.sub(r'(?i)<thought>.*?</thought>', '', text, flags=re.DOTALL)

    # 2. Strip common internal meta-leaks (Memory, System, Prompt, Context)
    # Matches lines starting with these keys and everything until the next double-newline or end of string.
    meta_patterns = [
        r'(?i)^Memory:.*?(?=\n\n|$)',
        r'(?i)^System:.*?(?=\n\n|$)',
        r'(?i)^Prompt:.*?(?=\n\n|$)',
        r'(?i)^Context:.*?(?=\n\n|$)',
        r'(?i)^Internal Memory:.*?(?=\n\n|$)',
    ]
    for pattern in meta_patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE | re.DOTALL)

    # 3. Normalize common LaTeX symbols to Unicode
    replacements = {
        r"$\to$": "→", r"$\Rightarrow$": "⇒", r"$\approx$": "≈", r"$\neq$": "≠",
        r"$\in$": "∈", r"$\notin$": "∉", r"$\pm$": "±", r"$\le$": "≤",
        r"$\ge$": "≥", r"$\infty$": "∞", r"$\forall$": "∀", r"$\exists$": "∃",
        r"$\Delta$": "Δ", r"$\pi$": "π", r"$\alpha$": "α", r"$\beta$": "β",
        r"$\gamma$": "γ", r"$\delta$": "δ", r"$\epsilon$": "ε", r"$\theta$": "θ",
        r"$\lambda$": "λ", r"$\mu$": "μ", r"$\sigma$": "σ", r"$\omega$": "ω",
        r"$\sum$": "∑", r"$\prod$": "∏", r"$\int$": "∫", r"$\partial$": "∂",
        r"$\nabla$": "∇",
    }
    for latex, unicode_char in replacements.items():
        text = text.replace(latex, unicode_char)

    # 3. Remove remaining $...$ delimiters but keep the content
    text = re.sub(r'\$(.*?)\$', r'\1', text)

    return text.strip()
