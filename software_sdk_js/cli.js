#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const configDir = path.join(os.homedir(), ".software-sdk");
const configFile = path.join(configDir, "config.json");
const command = process.argv[2] || "help";

if (command === "login") {
  const keyIndex = process.argv.indexOf("--api-key");
  const apiKey = keyIndex >= 0 ? process.argv[keyIndex + 1] : process.env.SOFTWARE_API_KEY;
  if (!apiKey) {
    console.log("No API key saved. Set SOFTWARE_API_KEY=... or run: software login --api-key YOUR_KEY");
    process.exit(0);
  }
  fs.mkdirSync(configDir, { recursive: true });
  fs.writeFileSync(configFile, `${JSON.stringify({ apiKey }, null, 2)}\n`);
  console.log(`Software SDK cloud API key saved to ${configFile}`);
  process.exit(0);
}

if (command === "status") {
  const hasKey = Boolean(process.env.SOFTWARE_API_KEY) || fs.existsSync(configFile);
  console.log(hasKey
    ? "Software SDK cloud mode is configured with an API key."
    : "Software SDK local mode is ready. Cloud mode is optional and needs SOFTWARE_API_KEY or software login.");
  process.exit(0);
}

console.log("Usage: software login --api-key YOUR_KEY | software status");
