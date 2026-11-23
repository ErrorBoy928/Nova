const { spawn } = require("child_process");
const path = require("path");

console.log("==========================================================");
console.log("NOVA AI - UNIFIED MULTI-PLATFORM RUNNER");
console.log(" Hosting Discord Bot & WhatsApp Bot in 1 Unified Engine");
console.log(" Autonomous Cloud Multi-Platform Engine");
console.log("==========================================================");

const pythonExecutable = process.platform === "win32" ? "python" : "python3";

let waProcess = null;
let dcProcess = null;
let isTerminating = false;

// Check essential environment variables and print status
const groqKey = process.env.GROQ_API_KEY;
const discordToken = process.env.DISCORD_BOT_TOKEN;

if (!groqKey) {
    console.warn(" [WARNING] GROQ_API_KEY environment variable is NOT set! AI responses will fail until added.");
} else {
    console.log(" [CONFIG] GROQ_API_KEY detected.");
}

if (!discordToken) {
    console.warn(" [WARNING] DISCORD_BOT_TOKEN environment variable is NOT set! Discord bot cannot log in without it.");
} else {
    console.log(" [CONFIG] DISCORD_BOT_TOKEN detected.");
}

// 1. WhatsApp Engine Supervisor
let waRestartDelay = 5000;
let waStartTime = 0;

function runWhatsApp() {
    if (isTerminating) return;
    waStartTime = Date.now();
    console.log(" [LAUNCHER] Spawning WhatsApp Engine (index.js)...");
    
    waProcess = spawn("node", ["index.js"], {
        cwd: __dirname,
        stdio: "inherit",
        env: process.env
    });

    waProcess.on("error", (err) => {
        console.error(" [WHATSAPP ERROR] Failed to start node process:", err.message);
    });

    waProcess.on("exit", (code, signal) => {
        waProcess = null;
        if (isTerminating) return;

        const uptime = (Date.now() - waStartTime) / 1000;
        if (uptime > 60) {
            // Ran stably for over 60s, reset delay to 5s
            waRestartDelay = 5000;
        } else {
            // Rapid exit: backoff 5s -> 15s -> 30s -> 60s -> max 180s
            waRestartDelay = Math.min(waRestartDelay * 2, 180000);
        }

        console.warn(` [WHATSAPP] Process exited after ${uptime.toFixed(1)}s (code: ${code}, signal: ${signal}). Auto-restarting in ${(waRestartDelay / 1000).toFixed(0)}s...`);
        setTimeout(runWhatsApp, waRestartDelay);
    });
}

// 2. Discord Engine Supervisor
let dcRestartDelay = 5000;
let dcStartTime = 0;

function runDiscord() {
    if (isTerminating) return;
    dcStartTime = Date.now();
    console.log(` [LAUNCHER] Spawning Discord Engine (main.py) via ${pythonExecutable}...`);

    dcProcess = spawn(pythonExecutable, ["discord_bot.py"], {
        cwd: __dirname,
        stdio: "inherit",
        env: process.env
    });

    dcProcess.on("error", (err) => {
        console.error(` [DISCORD ERROR] Failed to start python process (${pythonExecutable}):`, err.message);
    });

    dcProcess.on("exit", (code, signal) => {
        dcProcess = null;
        if (isTerminating) return;

        const uptime = (Date.now() - dcStartTime) / 1000;
        if (uptime > 60) {
            // Ran stably for over 60s, reset delay to 5s
            dcRestartDelay = 5000;
        } else {
            // Rapid exit: backoff 5s -> 15s -> 30s -> 60s -> max 180s
            dcRestartDelay = Math.min(dcRestartDelay * 2, 180000);
        }

        console.warn(` [DISCORD] Process exited after ${uptime.toFixed(1)}s (code: ${code}, signal: ${signal}). Auto-restarting in ${(dcRestartDelay / 1000).toFixed(0)}s...`);
        setTimeout(runDiscord, dcRestartDelay);
    });
}

// 3. Optional Desktop Assistant Supervisor (Windows Local)
let desktopProcess = null;
const shouldStartDesktop = process.argv.includes("--desktop") || process.env.START_DESKTOP === "true";

function runDesktopAssistant() {
    if (isTerminating || process.platform !== "win32") return;
    const fs = require("fs");
    const desktopPath = path.join("E:", "Nova_AI", "discord_bot.py");
    if (!fs.existsSync(desktopPath)) {
        console.warn(` [DESKTOP] App file not found at ${desktopPath}, skipping desktop launch.`);
        return;
    }

    console.log(` [LAUNCHER] Spawning Nova Desktop Assistant (${desktopPath})...`);
    desktopProcess = spawn(pythonExecutable, [desktopPath], {
        cwd: path.dirname(desktopPath),
        stdio: "inherit",
        env: process.env
    });

    desktopProcess.on("error", (err) => {
        console.error(" [DESKTOP ERROR] Failed to start desktop client:", err.message);
    });

    desktopProcess.on("exit", (code) => {
        desktopProcess = null;
        console.log(` [DESKTOP] Process exited (code: ${code}).`);
    });
}

// Graceful Shutdown on termination signals
function gracefulShutdown(signal) {
    console.log(`\n [SHUTDOWN] Received ${signal}. Terminating Nova sub-processes safely...`);
    isTerminating = true;

    if (waProcess) {
        try { waProcess.kill("SIGTERM"); } catch (e) {}
    }
    if (dcProcess) {
        try { dcProcess.kill("SIGTERM"); } catch (e) {}
    }
    if (desktopProcess) {
        try { desktopProcess.kill("SIGTERM"); } catch (e) {}
    }

    setTimeout(() => {
        console.log(" [SHUTDOWN] Nova Master Engine stopped.");
        process.exit(0);
    }, 1500);
}

process.on("SIGINT", () => gracefulShutdown("SIGINT"));
process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));

// Start active engines
runWhatsApp();
runDiscord();
if (shouldStartDesktop) {
    runDesktopAssistant();
}
