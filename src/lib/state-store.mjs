import { readJson, writeJson } from "./fs-utils.mjs";

function createDefaultState() {
  return {
    version: 1,
    updatedAt: null,
    board: null,
    agent: null,
    cards: {},
    webhook: {
      registrations: [],
      lastQueueDrainAt: null,
    },
    reconciliation: {
      lastPollAt: null,
    },
  };
}

export async function loadState(statePath) {
  const state = (await readJson(statePath, createDefaultState())) || createDefaultState();
  const defaults = createDefaultState();

  return {
    ...defaults,
    ...state,
    webhook: {
      ...defaults.webhook,
      ...(state.webhook || {}),
    },
    reconciliation: {
      ...defaults.reconciliation,
      ...(state.reconciliation || {}),
    },
  };
}

export async function saveState(statePath, state) {
  state.updatedAt = new Date().toISOString();
  await writeJson(statePath, state);
}
