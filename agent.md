# Agent Notes

- Treat `README.md`, `ARCHITECTURE.md`, and `docs/00-navigation.md` as the authoritative entry points.
- Keep generated runtime data under `data/`; it is intentionally ignored by Git.
- When changing runtime surfaces, keep CLI, JSON mode, Claude Skill, and MCP aligned through `ode/service_commands.py`.
- Push or open PRs only when the user explicitly asks for Git publishing.
