import { loadConfig } from "../lib/config.mjs";

function main() {
  const config = loadConfig();
  const url = new URL("https://trello.com/1/authorize");
  url.searchParams.set("expiration", "never");
  url.searchParams.set("scope", "read,write");
  url.searchParams.set("response_type", "token");
  url.searchParams.set("name", "Codex Trello Agent");
  url.searchParams.set("key", config.trello.apiKey);

  console.log(url.toString());
}

main();
