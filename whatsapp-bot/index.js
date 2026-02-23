require("dotenv").config();
const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const Anthropic = require("@anthropic-ai/sdk");

// --- Configuration ---
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const BOT_PREFIX = process.env.BOT_PREFIX || "!ai";
const MAX_TOKENS = parseInt(process.env.MAX_TOKENS, 10) || 1024;
const MODEL = process.env.CLAUDE_MODEL || "claude-sonnet-4-5";
const SYSTEM_PROMPT =
  process.env.SYSTEM_PROMPT ||
  "You are a helpful AI assistant on WhatsApp. Keep responses concise and well-formatted for mobile reading. Use plain text formatting (no markdown).";

if (!ANTHROPIC_API_KEY) {
  console.error("Error: ANTHROPIC_API_KEY is required. Set it in .env file.");
  process.exit(1);
}

// --- Initialize Claude client ---
const anthropic = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Conversation history (per chat, in-memory) ---
const conversations = new Map();
const MAX_HISTORY = parseInt(process.env.MAX_HISTORY, 10) || 20;

function getHistory(chatId) {
  if (!conversations.has(chatId)) {
    conversations.set(chatId, []);
  }
  return conversations.get(chatId);
}

function addToHistory(chatId, role, content) {
  const history = getHistory(chatId);
  history.push({ role, content });
  // Keep history within limits to manage token usage
  while (history.length > MAX_HISTORY) {
    history.shift();
  }
}

function clearHistory(chatId) {
  conversations.delete(chatId);
}

// --- Call Claude API ---
async function askClaude(chatId, userMessage) {
  addToHistory(chatId, "user", userMessage);

  const messages = getHistory(chatId);

  const response = await anthropic.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: SYSTEM_PROMPT,
    messages: messages,
  });

  const assistantMessage = response.content[0].text;
  addToHistory(chatId, "assistant", assistantMessage);

  return assistantMessage;
}

// --- Initialize WhatsApp client ---
const whatsapp = new Client({
  authStrategy: new LocalAuth({ dataPath: ".wwebjs_auth" }),
  puppeteer: {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
    ],
  },
});

// --- WhatsApp Events ---
whatsapp.on("qr", (qr) => {
  console.log("\nScan this QR code with WhatsApp to link your account:\n");
  qrcode.generate(qr, { small: true });
  console.log(
    "\nOpen WhatsApp > Settings > Linked Devices > Link a Device\n"
  );
});

whatsapp.on("authenticated", () => {
  console.log("WhatsApp authenticated successfully.");
});

whatsapp.on("auth_failure", (msg) => {
  console.error("WhatsApp authentication failed:", msg);
  process.exit(1);
});

whatsapp.on("ready", () => {
  console.log("\n=================================");
  console.log("  WhatsApp-Claude Bot is READY!");
  console.log("=================================");
  console.log(`  Model:  ${MODEL}`);
  console.log(`  Prefix: "${BOT_PREFIX}"`);
  console.log(`  Max tokens: ${MAX_TOKENS}`);
  console.log("=================================\n");
  console.log('Send a message starting with "' + BOT_PREFIX + '" to chat with Claude.');
  console.log('Send "' + BOT_PREFIX + ' reset" to clear conversation history.\n');
});

whatsapp.on("message", async (message) => {
  const body = message.body.trim();

  // Only respond to messages that start with the bot prefix
  if (!body.toLowerCase().startsWith(BOT_PREFIX.toLowerCase())) {
    return;
  }

  // Extract the actual message after the prefix
  const userMessage = body.slice(BOT_PREFIX.length).trim();

  if (!userMessage) {
    await message.reply(
      `Hi! I'm Claude AI on WhatsApp.\n\nUsage:\n${BOT_PREFIX} <your question>\n${BOT_PREFIX} reset - Clear conversation history`
    );
    return;
  }

  // Handle reset command
  if (userMessage.toLowerCase() === "reset") {
    clearHistory(message.from);
    await message.reply("Conversation history cleared. Starting fresh!");
    return;
  }

  // Show typing indicator
  const chat = await message.getChat();
  await chat.sendStateTyping();

  try {
    const reply = await askClaude(message.from, userMessage);

    // WhatsApp has a ~65,000 character limit per message
    // Split long responses if needed
    if (reply.length > 4000) {
      const chunks = splitMessage(reply, 4000);
      for (const chunk of chunks) {
        await message.reply(chunk);
      }
    } else {
      await message.reply(reply);
    }
  } catch (error) {
    console.error("Claude API error:", error.message);

    if (error.status === 429) {
      await message.reply(
        "I'm receiving too many requests right now. Please try again in a moment."
      );
    } else if (error.status === 401) {
      await message.reply("Bot configuration error. Please contact the admin.");
    } else {
      await message.reply(
        "Sorry, I encountered an error processing your message. Please try again."
      );
    }
  }
});

whatsapp.on("disconnected", (reason) => {
  console.log("WhatsApp disconnected:", reason);
});

// --- Utility ---
function splitMessage(text, maxLength) {
  const chunks = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= maxLength) {
      chunks.push(remaining);
      break;
    }
    // Try to split at a newline
    let splitIndex = remaining.lastIndexOf("\n", maxLength);
    if (splitIndex === -1 || splitIndex < maxLength / 2) {
      // Fall back to splitting at a space
      splitIndex = remaining.lastIndexOf(" ", maxLength);
    }
    if (splitIndex === -1 || splitIndex < maxLength / 2) {
      splitIndex = maxLength;
    }
    chunks.push(remaining.slice(0, splitIndex));
    remaining = remaining.slice(splitIndex).trimStart();
  }
  return chunks;
}

// --- Start ---
console.log("Starting WhatsApp-Claude Bot...");
console.log("Connecting to WhatsApp Web...\n");
whatsapp.initialize();
