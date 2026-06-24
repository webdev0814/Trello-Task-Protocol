export const CONTRACT_MARKER = "[CODEX_PROMPT_CONTRACT_V1]";

function summarizeDescription(text, maxLength = 300) {
  const normalized = (text || "").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "No description was provided yet.";
  }

  if (normalized.length <= maxLength) {
    return normalized;
  }

  return `${normalized.slice(0, maxLength - 3)}...`;
}

export function isContractComment(action) {
  return action?.data?.text?.includes(CONTRACT_MARKER);
}

function buildQuestions(listName) {
  if (listName === "Done") {
    return [
      "What specific outcome was completed?",
      "What evidence or artifact shows this is done?",
      "Is any follow-up, cleanup, or documentation still needed?",
      "Should this remain in Done, or does it need to be reopened?",
    ];
  }

  return [
    "What is the exact deliverable or outcome?",
    "What constraints matter here? (time, budget, tools, approvals, quality bar)",
    "What inputs or dependencies are required? (links, files, accounts, people)",
    "What decisions are already made, and what is still undecided?",
    "What is the definition of done for this specific card?",
    "What should I do if I hit ambiguity or a blocker?",
    "Once the answers are clear, should I proceed automatically or pause for approval first?",
  ];
}

export function buildPromptContractComment(card, listName) {
  const questions = buildQuestions(listName)
    .map((question, index) => `${index + 1}. ${question}`)
    .join("\n");

  return [
    CONTRACT_MARKER,
    "Agent Prompt Contract",
    "",
    "Current understanding",
    `- Title: ${card.name}`,
    `- Current list: ${listName}`,
    `- Description summary: ${summarizeDescription(card.desc)}`,
    "",
    "Objective",
    "- What should exist or be true when this card is actually complete?",
    "",
    "Questions to unblock execution",
    questions,
    "",
    "Reply guidance",
    "- Please answer in comments on this card.",
    "- I will use your answers to continue the work and move the card to the list that matches its state.",
    "",
    "Card definition of done",
    "- Please describe the specific done state for this card, not just the board workflow state.",
  ].join("\n");
}

export function buildActiveCardFollowUpComment(card, listName) {
  if (listName === "In Progress") {
    return [
      `Progress check for "${card.name}": this card is still in In Progress, but there has not been a recent update I can act on.`,
      "If there is a concrete next step I should take, I will continue.",
      "If this is waiting on a person, approval, or outside dependency, I should move it to Blocked.",
    ].join("\n\n");
  }

  return [
    `Follow-up for "${card.name}": this card is still in To-Do and has not moved recently.`,
    "If I should start now, confirm the next concrete action or missing input.",
    "If this is waiting on a person, approval, or outside dependency, I should move it to Blocked.",
  ].join("\n\n");
}
