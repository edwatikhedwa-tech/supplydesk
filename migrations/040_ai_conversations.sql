PRAGMA foreign_keys = ON;

-- Server-side AI chat history for the Messages screen assistant. Replaces
-- the previous localStorage-only history (frontend-v2/src/components/
-- AiChatPanel.tsx) so a chat survives refresh/close/re-login, and gives a
-- "New chat"/history list a real backing store instead of a single
-- per-thread localStorage key. Deliberately separate from ai_chat_usage
-- (migrations/036, spend tracking only) -- that table is untouched.
CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_conversations_owner
    ON ai_conversations(workspace_id, user_id, updated_at);

-- context_thread_ids is a JSON array of mail_threads.id, recorded only on
-- the user-turn row that triggered a model call -- an explicit, inspectable
-- audit trail of exactly which supplier threads fed a given AI answer (the
-- owner's diagnosability requirement), independent of what the assistant's
-- reply text says.
CREATE TABLE IF NOT EXISTS ai_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    context_thread_ids TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_messages_conversation
    ON ai_messages(conversation_id, created_at);
