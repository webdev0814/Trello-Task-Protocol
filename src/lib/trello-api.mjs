const API_BASE = "https://api.trello.com/1";

function buildQuery(query) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }

  return params;
}

export class TrelloClient {
  constructor({ apiKey, token }) {
    if (!apiKey) {
      throw new Error("Missing Trello API key.");
    }

    this.apiKey = apiKey;
    this.token = token;
  }

  async request(path, { method = "GET", query = {}, headers = {}, body } = {}) {
    if (!this.token) {
      throw new Error("Set TRELLO_TOKEN in .env.local before calling the Trello API.");
    }

    const url = new URL(`${API_BASE}${path}`);
    const params = buildQuery({
      ...query,
      key: this.apiKey,
      token: this.token,
    });
    url.search = params.toString();

    const response = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        ...headers,
      },
      body,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(`${method} ${url.pathname} failed: ${response.status} ${message}`);
    }

    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  getMe() {
    return this.request("/members/me", {
      query: {
        fields: "id,username,fullName",
      },
    });
  }

  getBoard(boardRef) {
    return this.request(`/boards/${boardRef}`, {
      query: {
        fields: "id,name,shortLink,url",
      },
    });
  }

  getBoardLists(boardRef) {
    return this.request(`/boards/${boardRef}/lists/open`, {
      query: {
        fields: "id,name,pos,closed",
      },
    });
  }

  getCardsForList(listId) {
    return this.request(`/lists/${listId}/cards`, {
      query: {
        fields: "id,name,desc,idList,dateLastActivity,shortLink,shortUrl,url,closed",
      },
    });
  }

  getCard(cardId) {
    return this.request(`/cards/${cardId}`, {
      query: {
        fields: "id,name,desc,idList,dateLastActivity,shortLink,shortUrl,url,closed",
      },
    });
  }

  getCardComments(cardId, limit = 100) {
    return this.request(`/cards/${cardId}/actions`, {
      query: {
        filter: "commentCard",
        limit,
      },
    });
  }

  addComment(cardId, text) {
    return this.request(`/cards/${cardId}/actions/comments`, {
      method: "POST",
      query: {
        text,
      },
    });
  }

  moveCardToList(cardId, listId) {
    return this.request(`/cards/${cardId}`, {
      method: "PUT",
      query: {
        idList: listId,
      },
    });
  }

  listTokenWebhooks() {
    return this.request(`/tokens/${this.token}/webhooks`);
  }

  createTokenWebhook({ callbackURL, idModel, description }) {
    return this.request(`/tokens/${this.token}/webhooks`, {
      method: "POST",
      query: {
        callbackURL,
        idModel,
        description,
      },
    });
  }

  deleteTokenWebhook(webhookId) {
    return this.request(`/tokens/${this.token}/webhooks/${webhookId}`, {
      method: "DELETE",
    });
  }
}
