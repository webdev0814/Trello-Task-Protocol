import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { loadConfig } from "../lib/config.mjs";

function quoteRemotePath(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function requireValue(name, value) {
  if (!value) {
    throw new Error(`Missing required Oracle sync config: ${name}`);
  }
  return value;
}

function runChecked(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: "pipe",
    encoding: "utf8",
    ...options,
  });

  if (result.status !== 0) {
    const stderr = result.stderr?.trim();
    const stdout = result.stdout?.trim();
    throw new Error(stderr || stdout || `${command} exited with status ${result.status}`);
  }

  return result.stdout?.trim() || "";
}

async function main() {
  const config = loadConfig();
  const sshHost = requireValue("ORACLE_TRELLO_SSH_HOST", config.oracle.sshHost);
  const sshUser = requireValue("ORACLE_TRELLO_SSH_USER", config.oracle.sshUser);
  const sshKeyPath = requireValue("ORACLE_TRELLO_SSH_KEY_PATH", config.oracle.sshKeyPath);
  const remoteDir = requireValue("ORACLE_TRELLO_REMOTE_DIR", config.oracle.remoteDir);
  const sshTarget = `${sshUser}@${sshHost}`;

  const sshArgs = [
    "-i",
    sshKeyPath,
    "-o",
    "BatchMode=yes",
    "-o",
    "StrictHostKeyChecking=accept-new",
  ];

  const remoteDrain = `cd ${quoteRemotePath(remoteDir)} && node src/commands/drain-webhook-queue.mjs`;
  runChecked("ssh", [...sshArgs, sshTarget, remoteDrain]);

  fs.mkdirSync(path.dirname(config.webhook.inboxPath), { recursive: true });
  const remoteInbox = `${sshTarget}:${remoteDir}/data/trello-webhook-inbox.json`;
  runChecked("scp", [...sshArgs, remoteInbox, config.webhook.inboxPath]);

  console.log(`Synced remote webhook inbox to ${config.webhook.inboxPath}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
