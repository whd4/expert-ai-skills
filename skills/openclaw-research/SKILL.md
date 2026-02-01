# OpenClaw / Clawdbot / Moltbot Research

## Skill Metadata
- **Name:** OpenClaw Research
- **Category:** AI Agents & LLM
- **Difficulty:** Intermediate
- **Tags:** openclaw, clawdbot, moltbot, personal-ai-assistant, self-hosted, autonomous-agent

---

## Overview

OpenClaw (formerly Clawdbot, then Moltbot) is an open-source, self-hosted personal AI assistant created by Peter Steinberger. It is one of the fastest-growing open-source projects in GitHub history, reaching 60,000+ stars within 72 hours.

## Timeline

| Date | Event |
|------|-------|
| Late 2025 | Launched as **Clawdbot** at clawd.bot |
| Jan 27, 2026 | Anthropic trademark request forces rebrand to **Moltbot** (molt.bot) |
| Jan 2026 | During rebrand, crypto scammers hijacked old GitHub org and X handle in ~10 seconds |
| Late Jan 2026 | Project settles on **OpenClaw** (openclaw.ai, github.com/openclaw/openclaw) |

## Key Features

- **Autonomous Agent**: Executes terminal commands, browses the web, manages files, controls smart home devices
- **Persistent Memory**: Remembers conversations, preferences, and context across sessions
- **Proactive Behavior**: Sends morning briefings, reminders, and alerts without being prompted
- **Multi-Platform**: WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Teams, Matrix, Zalo, WebChat, macOS, iOS/Android
- **Self-Hosted & Private**: All data stays on your device — no cloud dependency
- **Pluggable AI Backends**: Supports Claude (Anthropic), ChatGPT (OpenAI), and other model providers
- **Open Source**: Free to use; costs come only from AI model API usage

## Architecture

OpenClaw is not a web app or mobile app. It runs on your machine via command line and connects to external AI model APIs. As long as the host machine stays on, the assistant is available. Many users run it on dedicated Mac minis.

### Setup Flow
1. Install via CLI
2. Choose AI backend (Claude, ChatGPT, etc.)
3. Configure name, personality, and vibe
4. Connect messaging platforms (WhatsApp, Telegram, etc.)
5. Assistant runs continuously on your device

## Ecosystem

- **Moltbook**: An AI-agent-only social network spawned from the OpenClaw community. 37,000+ AI agents and 1M+ human observers within the first week.
- **Moltworker**: Cloudflare's self-hosted personal AI agent integration, inspired by OpenClaw.
- **Chinese Cloud Support**: Alibaba, Tencent, and ByteDance have added Moltbot/OpenClaw agent support.

## Security Considerations

When building or deploying OpenClaw-style autonomous agents, be aware of:

- **Prompt Injection**: Autonomous agents with system access are prime targets
- **Credential Storage**: Local config files may expose API keys and tokens
- **Admin Interface Exposure**: Self-hosted services may inadvertently expose control panels
- **Supply Chain Attacks**: Fake extensions (e.g., VS Code Marketplace imposters) have appeared
- **Elevated Permissions**: Agents with terminal/file access require careful sandboxing

### Recommendations
- Run in a sandboxed environment or dedicated VM
- Use environment variables or secret managers for credentials
- Restrict network access to only required endpoints
- Audit all third-party skills/plugins before installation
- Monitor agent actions with logging and alerting

## Integration Patterns

### As a Coding Assistant Skill
When integrating OpenClaw-style capabilities into AI coding workflows:

1. **Task Automation**: Delegate repetitive CLI tasks to the agent
2. **Multi-Service Orchestration**: Chain API calls across services (GitHub, Slack, calendar, etc.)
3. **Persistent Context**: Maintain project context across coding sessions
4. **Proactive Monitoring**: Set up alerts for build failures, dependency vulnerabilities, or deployment issues

## References

- Website: https://openclaw.ai/
- GitHub: https://github.com/openclaw/openclaw
- Documentation: https://docs.openclaw.ai/
- Previous URLs: clawd.bot, molt.bot
