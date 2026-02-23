# WhatsApp Group Reminder Bot

Auto-blast "Like & Share" reminders to your WhatsApp groups for your Facebook pages. Schedule reminders or send them manually.

## Prerequisites

- **Node.js** 18+ installed
- **WhatsApp account** on your phone

## Setup

```bash
# 1. Install dependencies
cd whatsapp-bot
npm install

# 2. Edit config.json with your Facebook pages and group names
#    (see config.example.json for reference)

# 3. Start the bot
npm start
```

On first run, a **QR code** will appear in your terminal. Scan it with WhatsApp:

1. Open WhatsApp on your phone
2. Go to **Settings > Linked Devices > Link a Device**
3. Scan the QR code in your terminal

The bot will remember the session, so you only need to scan once.

## Configuration

Edit `config.json` to set up your reminders:

```json
{
  "reminders": [
    {
      "schedule": "0 9 * * 1,3,5",
      "pages": [
        {
          "pageName": "My Page",
          "pageUrl": "https://www.facebook.com/mypage"
        }
      ],
      "groups": [
        "Group Name 1",
        "Group Name 2"
      ]
    }
  ]
}
```

### Schedule Format (Cron)

The `schedule` field uses cron format: `minute hour day month weekday`

| Schedule | Meaning |
|---|---|
| `0 9 * * *` | Every day at 9:00 AM |
| `0 9 * * 1,3,5` | Monday, Wednesday, Friday at 9:00 AM |
| `0 9,18 * * *` | Every day at 9:00 AM and 6:00 PM |
| `0 10 * * 1` | Every Monday at 10:00 AM |
| `0 9 1 * *` | 1st of every month at 9:00 AM |

### Custom Message

You can set a custom message per page instead of the default template:

```json
{
  "pageName": "My Page",
  "pageUrl": "https://facebook.com/mypage",
  "customMessage": "Hey everyone! Please like and share our page: https://facebook.com/mypage"
}
```

## Terminal Commands

While the bot is running, you can type these commands:

| Command | Description |
|---|---|
| `blast` | Send all reminders immediately |
| `groups` | List all your WhatsApp groups (use this to get exact group names for config) |
| `status` | Show scheduled jobs |
| `quit` | Stop the bot |

## How It Works

1. The bot connects to WhatsApp Web as a linked device
2. On the scheduled time, it sends reminder messages to configured groups
3. Each Facebook page gets its own "Like & Share" reminder message
4. You can also manually trigger blasts anytime by typing `blast`

## Tips

- Run `groups` command first to see the exact names of your WhatsApp groups
- Copy those exact group names into your `config.json`
- Group names are case-insensitive
- WhatsApp session data is saved locally in `.wwebjs_auth/` for persistent login
