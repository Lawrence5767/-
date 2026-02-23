require("dotenv").config();
const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const cron = require("node-cron");
const fs = require("fs");
const path = require("path");

// --- Load Configuration ---
const CONFIG_PATH = path.join(__dirname, "config.json");

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    console.error("Error: config.json not found. Please create it first.");
    console.log("See config.example.json for reference.");
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
}

const config = loadConfig();

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

// --- Track scheduled jobs ---
const scheduledJobs = [];

// --- Send message to a group by name ---
async function sendToGroup(groupName, message) {
  try {
    const chats = await whatsapp.getChats();
    const group = chats.find(
      (chat) => chat.isGroup && chat.name.toLowerCase() === groupName.toLowerCase()
    );

    if (!group) {
      console.log(`  [!] Group not found: "${groupName}"`);
      return false;
    }

    await group.sendMessage(message);
    console.log(`  [OK] Sent to: "${groupName}"`);
    return true;
  } catch (error) {
    console.error(`  [ERROR] Failed to send to "${groupName}":`, error.message);
    return false;
  }
}

// --- Blast message to all target groups ---
async function blastToGroups(groups, message) {
  console.log(`\n--- Sending blast at ${new Date().toLocaleString()} ---`);
  console.log(`Message:\n${message}\n`);

  let success = 0;
  let failed = 0;

  for (const groupName of groups) {
    const result = await sendToGroup(groupName, message);
    if (result) success++;
    else failed++;

    // Small delay between messages to avoid rate limiting
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  console.log(`--- Done: ${success} sent, ${failed} failed ---\n`);
}

// --- Build reminder message for a Facebook page ---
function buildMessage(pageConfig) {
  const { pageName, pageUrl, customMessage } = pageConfig;

  if (customMessage) {
    return customMessage;
  }

  return (
    `🔔 *REMINDER* 🔔\n\n` +
    `Hi everyone! Please help support us by liking & sharing our Facebook page:\n\n` +
    `📌 *${pageName}*\n` +
    `🔗 ${pageUrl}\n\n` +
    `👍 Like the page\n` +
    `📢 Share with your friends\n\n` +
    `Thank you for your support! 🙏`
  );
}

// --- Schedule all reminders ---
function scheduleReminders() {
  // Clear any existing jobs
  scheduledJobs.forEach((job) => job.stop());
  scheduledJobs.length = 0;

  for (const reminder of config.reminders) {
    const { schedule, pages, groups } = reminder;

    const job = cron.schedule(schedule, async () => {
      for (const pageConfig of pages) {
        const message = buildMessage(pageConfig);
        await blastToGroups(groups, message);

        // Delay between different page reminders
        if (pages.length > 1) {
          await new Promise((resolve) => setTimeout(resolve, 5000));
        }
      }
    });

    scheduledJobs.push(job);
    console.log(`  Scheduled: "${schedule}" -> ${groups.length} groups, ${pages.length} pages`);
  }
}

// --- List all groups (helper command) ---
async function listGroups() {
  const chats = await whatsapp.getChats();
  const groups = chats.filter((chat) => chat.isGroup);

  console.log("\n=== Your WhatsApp Groups ===");
  groups.forEach((group, i) => {
    console.log(`  ${i + 1}. ${group.name}`);
  });
  console.log(`=== Total: ${groups.length} groups ===\n`);
}

// --- Manual blast command via terminal ---
function setupTerminalCommands() {
  const readline = require("readline");
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("\nTerminal commands:");
  console.log("  blast  - Send all reminders now");
  console.log("  groups - List all your WhatsApp groups");
  console.log("  status - Show scheduled jobs");
  console.log("  quit   - Stop the bot\n");

  rl.on("line", async (input) => {
    const cmd = input.trim().toLowerCase();

    if (cmd === "blast") {
      console.log("\nSending all reminders now...");
      for (const reminder of config.reminders) {
        for (const pageConfig of reminder.pages) {
          const message = buildMessage(pageConfig);
          await blastToGroups(reminder.groups, message);
        }
      }
    } else if (cmd === "groups") {
      await listGroups();
    } else if (cmd === "status") {
      console.log(`\nActive scheduled jobs: ${scheduledJobs.length}`);
      config.reminders.forEach((r, i) => {
        console.log(`  ${i + 1}. Schedule: "${r.schedule}" -> ${r.groups.length} groups`);
      });
      console.log();
    } else if (cmd === "quit") {
      console.log("Stopping bot...");
      scheduledJobs.forEach((job) => job.stop());
      process.exit(0);
    }
  });
}

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
  console.log("\n==========================================");
  console.log("  WhatsApp Group Reminder Bot is READY!");
  console.log("==========================================");
  console.log(`  Reminders configured: ${config.reminders.length}`);
  console.log("==========================================\n");

  // Schedule all reminders
  console.log("Setting up schedules:");
  scheduleReminders();

  // Setup terminal commands
  setupTerminalCommands();

  // List groups on startup so user can verify group names
  listGroups();
});

whatsapp.on("disconnected", (reason) => {
  console.log("WhatsApp disconnected:", reason);
});

// --- Start ---
console.log("Starting WhatsApp Group Reminder Bot...");
console.log("Connecting to WhatsApp Web...\n");
whatsapp.initialize();
