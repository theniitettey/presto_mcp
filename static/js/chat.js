class ChatApp {
  constructor() {
    this.messagesContainer = document.getElementById("chatMessages");
    this.messageInput = document.getElementById("messageInput");
    this.sendButton = document.getElementById("sendButton");
    this.statusIndicator = document.getElementById("statusIndicator");

    this.sessionId = null;
    this.token = null;
    this.currentStatus = "NOT_AUTHENTICATED";

    this.init();
  }

  init() {
    this.sendButton.addEventListener("click", () => this.sendMessage());
    this.messageInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Show suggestion chips instead of welcome message
    this.showSuggestionChips();
    this.updateStatus("NOT_AUTHENTICATED");
  }

  async sendMessage() {
    const message = this.messageInput.value.trim();
    if (!message) return;

    // Disable input
    this.setInputState(false);

    // Add user message
    this.addUserMessage(message);
    this.messageInput.value = "";

    // Show typing indicator
    this.showTyping(true);

    try {
      const response = await this.callChatAPI(message);

      // Hide typing indicator
      this.showTyping(false);

      // Update session info
      if (response.session_id) {
        this.sessionId = response.session_id;
      }
      if (response.token) {
        this.token = response.token;
      }
      if (response.status) {
        this.updateStatus(response.status);
      }

      // Add bot response
      this.addBotMessage(response.message);
    } catch (error) {
      this.showTyping(false);
      this.showError(error.message);
    } finally {
      this.setInputState(true);
      this.messageInput.focus();
    }
  }

  async callChatAPI(message) {
    const payload = {
      message: message,
    };

    // Add session_id if exists
    if (this.sessionId) {
      payload.session_id = this.sessionId;
    }

    // Add token if exists
    if (this.token) {
      payload.token = this.token;
    }

    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to send message");
    }

    return await response.json();
  }

  addUserMessage(text) {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message user";
    messageDiv.innerHTML = `
            <div class="message-content">
                ${this.escapeHtml(text)}
                <div class="message-time">${this.getCurrentTime()}</div>
            </div>
        `;
    this.messagesContainer.appendChild(messageDiv);
    this.scrollToBottom();
  }

  addBotMessage(text) {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message bot";
    messageDiv.innerHTML = `
            <div class="message-content">
                ${this.escapeHtml(text)}
                <div class="message-time">${this.getCurrentTime()}</div>
            </div>
        `;
    this.messagesContainer.appendChild(messageDiv);
    this.scrollToBottom();
  }

  showTyping(show) {
    // Remove existing typing indicator if present
    const existingIndicator = document.getElementById("typingIndicator");
    if (existingIndicator) {
      existingIndicator.remove();
    }

    if (show) {
      // Create typing indicator as a message
      const typingDiv = document.createElement("div");
      typingDiv.className = "message bot";
      typingDiv.id = "typingIndicator";
      typingDiv.innerHTML = `
        <div class="message-content typing-content">
          <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      `;
      this.messagesContainer.appendChild(typingDiv);
      this.scrollToBottom();
    }
  }

  showError(message) {
    const errorDiv = document.createElement("div");
    errorDiv.className = "error-message";
    errorDiv.textContent = `Error: ${message}`;
    this.messagesContainer.appendChild(errorDiv);
    this.scrollToBottom();

    // Remove error after 5 seconds
    setTimeout(() => {
      errorDiv.remove();
    }, 5000);
  }

  updateStatus(status) {
    this.currentStatus = status;
    const statusText = this.formatStatus(status);
    this.statusIndicator.textContent = `Status: ${statusText}`;
  }

  formatStatus(status) {
    // Convert status to readable format
    return status
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (l) => l.toUpperCase());
  }

  setInputState(enabled) {
    this.messageInput.disabled = !enabled;
    this.sendButton.disabled = !enabled;
  }

  scrollToBottom() {
    setTimeout(() => {
      this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }, 100);
  }

  getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, "<br>");
  }

  showSuggestionChips() {
    const suggestions = [
      { text: "👤 Create new account", icon: "👤" },
      { text: "🔐 Login to existing account", icon: "🔐" },
      { text: "💰 Check balance", icon: "💰" },
      { text: "💳 Make a payment", icon: "💳" },
    ];

    const suggestionsContainer = document.createElement("div");
    suggestionsContainer.className = "suggestions-container";
    suggestionsContainer.id = "suggestionsContainer";

    suggestions.forEach((suggestion) => {
      const chip = document.createElement("button");
      chip.className = "suggestion-chip";
      chip.textContent = suggestion.text;
      chip.addEventListener("click", () => {
        this.handleSuggestionClick(suggestion.text);
      });
      suggestionsContainer.appendChild(chip);
    });

    this.messagesContainer.appendChild(suggestionsContainer);
  }

  handleSuggestionClick(text) {
    // Remove suggestion chips
    const suggestionsContainer = document.getElementById(
      "suggestionsContainer"
    );
    if (suggestionsContainer) {
      suggestionsContainer.remove();
    }

    // Set the message input and send
    this.messageInput.value = text;
    this.sendMessage();
  }
}

// Initialize chat app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  new ChatApp();
});
