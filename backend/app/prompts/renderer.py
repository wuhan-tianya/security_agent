def render_user_prompt(template: str, user_input: str, memory_context: str = "") -> str:
    base = (
        template.replace("{{user_input}}", user_input)
        .replace("{{memory_context}}", memory_context)
        .strip()
    )
    # Keep the current user request as the last block so it has highest priority.
    return f"{base}\n\n当前用户请求（最高优先级）：\n{user_input}".strip()
