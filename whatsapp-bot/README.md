# WhatsApp-Claude Bot

Chat with Claude AI directly through WhatsApp. This bot connects to your WhatsApp account via WhatsApp Web and forwards messages to Claude's API.

## Prerequisites

- **Node.js** 18+ installed
- **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com)
- **WhatsApp account** on your phone

## Setup

```bash
# 1. Install dependencies
cd whatsapp-bot
npm install

# 2. Create your .env file
cp .env.example .env

# 3. Add your Anthropic API key to .env
#    Edit .env and set ANTHROPIC_API_KEY=sk-ant-xxxxx

# 4. Start the bot
npm start
```

On first run, a **QR code** will appear in your terminal. Scan it with WhatsApp:

1. Open WhatsApp on your phone
2. Go to **Settings > Linked Devices > Link a Device**
3. Scan the QR code in your terminal

The bot will remember the session, so you only need to scan once.

## Usage

Send a message in any WhatsApp chat starting with the bot prefix (default: `!ai`):

```
!ai What is the capital of France?
!ai Explain quantum computing in simple terms
!ai Translate "hello" to Japanese
!ai reset                              ← clears conversation history
```

The bot maintains conversation history per chat, so Claude remembers context within a conversation.

## Configuration

Edit `.env` to customize:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `CLAUDE_MODEL` | `claude-sonnet-4-5` | Claude model to use |
| `BOT_PREFIX` | `!ai` | Message prefix to trigger the bot |
| `MAX_TOKENS` | `1024` | Max tokens in Claude's response |
| `MAX_HISTORY` | `20` | Messages kept in conversation memory |
| `SYSTEM_PROMPT` | *(built-in)* | Custom system prompt for Claude |

## How It Works

```
WhatsApp (phone)
    ↕ (WhatsApp Web protocol)
whatsapp-web.js (this bot)
    ↕ (HTTPS API calls)
Claude API (Anthropic)
```

1. The bot connects to WhatsApp Web as a linked device
2. When a message starts with the prefix, it's sent to Claude's API
3. Claude's response is sent back as a WhatsApp reply
4. Conversation history is maintained per chat for context

## Notes

- The bot only responds to messages starting with the configured prefix
- Conversation history is stored in memory and resets when the bot restarts
- WhatsApp session data is saved locally in `.wwebjs_auth/` for persistent login
- Long responses are automatically split into multiple messages
