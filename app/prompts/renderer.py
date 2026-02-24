def render_user_prompt(template: str, user_input: str, memory_context: str = "") -> str:
    return (
        template.replace("{{user_input}}", user_input)
        .replace("{{memory_context}}", memory_context)
        .strip()
    )
