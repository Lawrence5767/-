# Facebook Auto-Reply Agent

An AI-powered agent that automatically replies to comments on your Facebook Page using Claude.

## How It Works

1. **Facebook sends a webhook** when someone comments on your Page's posts
2. **The agent receives the comment** and fetches the original post for context
3. **Claude generates a reply** that is polite, helpful, and matches the comment's tone
4. **The reply is posted** back to Facebook as a response to the comment

## Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
- A [Facebook Developer App](https://developers.facebook.com/apps/) with:
  - A Facebook Page connected to the app
  - A long-lived Page Access Token
  - Webhooks configured for the `feed` field

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your credentials
```

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `FACEBOOK_APP_SECRET` | Found in your Facebook App's Settings > Basic |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Long-lived Page Access Token (see below) |
| `FACEBOOK_VERIFY_TOKEN` | Any string you choose (must match webhook config) |
| `PORT` | Server port (default: 5000) |

### 3. Get a Facebook Page Access Token

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app and your Page
3. Add permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_engagement`
4. Generate the token and exchange it for a long-lived token:

```bash
curl -s "https://graph.facebook.com/v21.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id=YOUR_APP_ID&\
client_secret=YOUR_APP_SECRET&\
fb_exchange_token=YOUR_SHORT_LIVED_TOKEN"
```

### 4. Configure Facebook Webhook

1. In your Facebook App dashboard, go to **Webhooks**
2. Subscribe to the **Page** object
3. Set the callback URL to `https://your-domain.com/webhook`
4. Set the verify token to match your `FACEBOOK_VERIFY_TOKEN`
5. Subscribe to the **feed** field

> **Note:** Facebook requires HTTPS for webhooks. For local development, use a tunneling tool like [ngrok](https://ngrok.com/): `ngrok http 5000`

### 5. Run the agent

```bash
python app.py
```

For production:

```bash
gunicorn app:create_production_app --bind 0.0.0.0:5000
```

## Project Structure

```
├── app.py              # Main entry point and configuration
├── facebook_api.py     # Facebook Graph API client
├── reply_generator.py  # Claude-powered reply generation
├── webhook.py          # Flask webhook server
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── .gitignore
```

## Customization

### Adjust the reply style

Edit the `SYSTEM_PROMPT` in `reply_generator.py` to change how Claude generates replies. For example, you can:
- Make replies more formal or casual
- Add specific product knowledge
- Set rules for handling complaints or questions

### Change the AI model

Pass a different model to `ReplyGenerator`:

```python
generator = ReplyGenerator(model="claude-haiku-4-5")  # Faster, cheaper
```
