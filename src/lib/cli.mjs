import fs from "node:fs";

export function parseArgs(argv = process.argv.slice(2)) {
  const args = {};

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      continue;
    }

    const key = token.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
      continue;
    }

    args[key] = next;
    index += 1;
  }

  return args;
}

export async function readCommentBody({ text, textFile }) {
  if (typeof text === "string" && text.length > 0) {
    return text;
  }

  if (typeof textFile === "string" && textFile.length > 0) {
    return fs.readFileSync(textFile, "utf8");
  }

  if (process.stdin.isTTY) {
    throw new Error("Provide comment text with --text, --text-file, or stdin.");
  }

  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}
