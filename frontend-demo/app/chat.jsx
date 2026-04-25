function md(text) {
  if (!text) return "";
  if (window.marked) {
    try {
      return window.marked.parse(text, { breaks: true, gfm: true });
    } catch (_) {
      return text;
    }
  }
  return text;
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function normalizeForSearch(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractTerms(query) {
  const stopWords = new Set([
    "find", "the", "part", "where", "about", "show", "me", "with", "that",
    "найди", "часть", "где", "про", "покажи", "место", "это", "этот", "эту",
    "and", "или", "как", "что", "which", "talked", "обсуждали",
  ]);

  return Array.from(new Set(
    normalizeForSearch(query)
      .split(" ")
      .filter((term) => term.length > 2 && !stopWords.has(term))
  ));
}

function scoreMessage(message, terms) {
  const haystack = normalizeForSearch(message.content);
  if (!haystack || !terms.length) return 0;

  let score = 0;
  terms.forEach((term) => {
    if (haystack.includes(term)) {
      score += haystack.split(term).length > 2 ? 3 : 2;
      if (message.content.toLowerCase().includes(term)) score += 1;
    }
  });
  return score;
}

function scoreText(text, terms) {
  const haystack = normalizeForSearch(text);
  if (!haystack || !terms.length) return 0;

  return terms.reduce((score, term) => {
    if (!haystack.includes(term)) return score;
    const repetitions = haystack.split(term).length - 1;
    const startsWithBoost = haystack.startsWith(term) ? 2 : 0;
    return score + 2 + Math.min(repetitions, 4) + startsWithBoost;
  }, 0);
}

function scoreSearchEntry(entry, terms) {
  const base = scoreText(entry.searchText, terms);
  if (!base) return 0;
  const typeBoost = {
    message: 4,
    chat: 3,
    file: 2,
    memory: 2,
    workspace: 2,
  };
  return base + (typeBoost[entry.type] || 0);
}

function highlightText(text, terms) {
  if (!terms.length) return escapeHtml(text);
  const escapedTerms = terms
    .filter(Boolean)
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));

  if (!escapedTerms.length) return escapeHtml(text);
  const regex = new RegExp(`(${escapedTerms.join("|")})`, "gi");
  return escapeHtml(text).replace(
    regex,
    '<mark style="background: rgba(99,102,241,.18); color: inherit; padding: 0 2px; border-radius: 4px;">$1</mark>'
  );
}

function formatSnippet(text, terms) {
  const content = String(text || "");
  if (!content) return "";
  const lower = content.toLowerCase();
  const matchIndex = terms.reduce((best, term) => {
    const idx = lower.indexOf(term.toLowerCase());
    return idx >= 0 && (best < 0 || idx < best) ? idx : best;
  }, -1);

  if (matchIndex < 0) {
    return content.slice(0, 180) + (content.length > 180 ? "..." : "");
  }

  const start = Math.max(0, matchIndex - 60);
  const end = Math.min(content.length, matchIndex + 120);
  return `${start > 0 ? "..." : ""}${content.slice(start, end)}${end < content.length ? "..." : ""}`;
}

function ChatView() {
  const { t, lang } = useLang();
  const { activeChat, activeChatId, activeMessages, chats, files, workspaces, memoryFacts, messagesByChat, loadMessages, selectChat, navigate, sendMessage, thinking, refreshChat } = useApp();
  const [input, setInput] = useState("");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [memoryMode, setMemoryMode] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState("chats");
  const [highlight, setHighlight] = useState(null);
  const [pendingJump, setPendingJump] = useState(null);
  const messagesRef = useRef(null);
  const textRef = useRef(null);

  const messages = activeMessages || [];
  const terms = extractTerms(searchQuery);
  const searchableEntries = useMemo(() => {
    const chatEntries = chats.map((chat) => ({
      type: "chat",
      id: `chat-${chat.id}`,
      title: chat.title || t("new_chat"),
      subtitle: t("chats"),
      searchText: `${chat.title || ""} ${chat.createdAt || ""} ${chat.updatedAt || ""}`,
      chatId: chat.id,
    }));

    const messageEntries = chats.flatMap((chat) =>
      (messagesByChat[chat.id] || []).map((message) => ({
        type: "message",
        id: `message-${chat.id}-${message.id}`,
        title: chat.title || t("new_chat"),
        subtitle: `${t("search_category_messages")} · ${message.role}`,
        body: message.content || "",
        searchText: `${chat.title || ""} ${message.role || ""} ${message.content || ""}`,
        chatId: chat.id,
        chatTitle: chat.title,
        message,
      }))
    );

    const fileEntries = files.map((file) => ({
      type: "file",
      id: `file-${file.id}`,
      title: file.filename || file.name || t("files"),
      subtitle: `${t("search_category_files")} · ${file.status || ""}`,
      body: [file.mime_type, file.ext, file.status, file.chunks ? `${file.chunks} ${t("chunks_label")}` : ""].filter(Boolean).join(" · "),
      searchText: `${file.filename || ""} ${file.name || ""} ${file.mime_type || ""} ${file.ext || ""} ${file.status || ""}`,
      fileId: file.id,
    }));

    const memoryEntries = memoryFacts.map((fact) => ({
      type: "memory",
      id: `memory-${fact.key}`,
      title: fact.key || t("memory_title"),
      subtitle: t("search_category_memory"),
      body: fact.value || "",
      searchText: `${fact.key || ""} ${fact.value || ""}`,
      memoryKey: fact.key,
    }));

    const workspaceEntries = workspaces.map((workspace) => ({
      type: "workspace",
      id: `workspace-${workspace.id}`,
      title: workspace.name || t("workspaces"),
      subtitle: t("search_category_workspaces"),
      body: workspace.description || "",
      searchText: `${workspace.name || ""} ${workspace.description || ""}`,
      workspaceId: workspace.id,
    }));

    return [
      ...chatEntries,
      ...messageEntries,
      ...fileEntries,
      ...memoryEntries,
      ...workspaceEntries,
    ];
  }, [chats, messagesByChat, files, memoryFacts, workspaces, t]);
  const rankedResults = useMemo(() => {
    if (!terms.length) return [];
    return searchableEntries
      .map((entry) => ({ ...entry, score: scoreSearchEntry(entry, terms) }))
      .filter((entry) => entry.score > 0)
      .sort((left, right) => right.score - left.score);
  }, [searchableEntries, searchQuery]);
  const visibleSearchResults = useMemo(() => {
    if (searchMode === "all") return rankedResults;
    return rankedResults.filter((entry) => entry.type === "chat" || entry.type === "message");
  }, [rankedResults, searchMode]);

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages.length, thinking]);

  useEffect(() => {
    if (!searchOpen || chats.length === 0) return;
    Promise.all(chats.map((chat) => loadMessages(chat.id).catch(() => []))).catch(() => {});
  }, [searchOpen, chats, loadMessages]);

  useEffect(() => {
    if (!pendingJump || activeChatId !== pendingJump.chatId) return;
    const node = document.querySelector(`[data-message-id="${pendingJump.messageId}"]`);
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
    node.animate([
      { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
      { boxShadow: "0 0 0 8px rgba(99,102,241,0.12)" },
      { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
    ], { duration: 1200, easing: "ease-out" });
    setPendingJump(null);
  }, [activeChatId, activeMessages, pendingJump]);

  const resize = () => {
    const node = textRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 200)}px`;
  };

  const jumpTo = async (result) => {
    if (!result) return;
    setSearchOpen(false);

    if (result.type === "message") {
      setHighlight({ messageId: result.message.id, terms });
      if (result.chatId !== activeChatId) {
        setPendingJump({ chatId: result.chatId, messageId: result.message.id });
        selectChat(result.chatId);
        await loadMessages(result.chatId, true).catch(() => {});
        return;
      }
      const node = document.querySelector(`[data-message-id="${result.message.id}"]`);
      if (node) {
        node.scrollIntoView({ behavior: "smooth", block: "center" });
        node.animate([
          { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
          { boxShadow: "0 0 0 8px rgba(99,102,241,0.12)" },
          { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
        ], { duration: 1200, easing: "ease-out" });
      }
      return;
    }

    if (result.type === "chat") {
      selectChat(result.chatId);
      return;
    }

    if (result.type === "file") {
      navigate("files");
      return;
    }

    if (result.type === "memory") {
      navigate("memory");
      return;
    }

    if (result.type === "workspace") {
      navigate("workspaces", { wsId: result.workspaceId });
    }
  };

  const onSubmit = async () => {
    const content = input.trim();
    if (!content || thinking) return;
    setInput("");
    setMemoryMode(false);
    if (textRef.current) textRef.current.style.height = "auto";
    await sendMessage({
      content,
      fileId: selectedFileId ? Number(selectedFileId) : null,
    });
  };

  const onKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };

  return React.createElement("div", { className: "chat-view" },
    React.createElement("div", {
      style: {
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 16,
        padding: "18px 32px 0",
      },
    },
      React.createElement("div", null,
        React.createElement("div", {
          style: {
            fontSize: 18,
            fontWeight: 800,
            color: "var(--text)",
            letterSpacing: "-.3px",
          },
        }, activeChat?.title || t("new_chat")),
        React.createElement("div", {
          style: {
            fontSize: 12,
            color: "var(--muted)",
            marginTop: 4,
          },
        }, t("universal_search_hint"))
      ),
      React.createElement("div", { style: { position: "relative" } },
        React.createElement("button", {
          className: "btn-primary",
          onClick: () => setSearchOpen((value) => !value),
          style: {
            width: "auto",
            padding: "10px 16px",
            borderRadius: 12,
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            whiteSpace: "nowrap",
          },
        },
          React.createElement(IconSearch),
          React.createElement("span", null, t("search_button"))
        ),
        searchOpen && React.createElement(ChatSearchPopover, {
          query: searchQuery,
          setQuery: setSearchQuery,
          mode: searchMode,
          setMode: setSearchMode,
          rankedResults: visibleSearchResults,
          terms,
          currentChatId: activeChatId,
          onJump: jumpTo,
        })
      )
    ),
    React.createElement("div", { className: "chat-messages", ref: messagesRef },
      messages.length === 0
        ? React.createElement(EmptyState, {
            suggestions: useLang().T.suggestions,
            onSelect: (value) => {
              setInput(value);
              setTimeout(() => {
                textRef.current?.focus();
                resize();
              }, 40);
            },
          })
        : React.createElement(React.Fragment, null,
            messages.map((message) => React.createElement(Message, {
              key: message.id,
              msg: message,
              highlighted: highlight?.messageId === message.id ? highlight.terms : [],
            })),
            thinking && React.createElement(ThinkingRow)
          )
    ),
    React.createElement("div", { className: "chat-input-area" },
      React.createElement("div", { className: "chat-input-card" },
        React.createElement("div", { className: "chat-input-top" },
          React.createElement("button", {
            type: "button",
            className: `memory-chip ${memoryMode ? "active" : ""}`,
            onClick: () => setMemoryMode((value) => !value),
            title: memoryMode
              ? (t("memory") + " on")
              : (t("memory") + " off"),
          },
            React.createElement(IconBrain),
            React.createElement("span", null, t("memory"))
          )
        ),
        React.createElement("textarea", {
          ref: textRef,
          className: "chat-ta",
          rows: 1,
          value: input,
          placeholder: t("placeholder"),
          onChange: (event) => {
            setInput(event.target.value);
            resize();
          },
          onKeyDown,
        }),
        React.createElement("div", { className: "chat-input-bottom" },
          React.createElement("div", { className: "chat-tools-left", style: { gap: 8, alignItems: "center" } },
            React.createElement("div", {
              style: {
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "0 10px",
                border: "1px solid var(--border)",
                borderRadius: 10,
                height: 34,
                background: "var(--surface2)",
              },
            },
              React.createElement(IconPaperclip),
              React.createElement("select", {
                value: selectedFileId,
                onChange: (event) => setSelectedFileId(event.target.value),
                style: {
                  border: "none",
                  background: "transparent",
                  color: "var(--text)",
                  outline: "none",
                },
              },
                React.createElement("option", { value: "" }, t("attach_file")),
                files.map((file) => React.createElement("option", { key: file.id, value: file.id }, file.filename))
              )
            ),
            React.createElement("button", {
              className: "chat-tool",
              title: t("voice_input"),
              type: "button",
            }, React.createElement(IconMic))
          ),
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8 } },
            React.createElement("button", {
              className: "msg-action",
              type: "button",
              onClick: () => activeChat?.id && refreshChat(activeChat.id),
            }, t("refresh")),
            React.createElement("button", {
              className: `chat-send ${input.trim() && !thinking ? "ready" : ""}`,
              onClick: onSubmit,
              disabled: !input.trim() || thinking,
              type: "button",
            }, thinking ? React.createElement(Spinner, { size: 15 }) : React.createElement(IconSend))
          )
        )
      )
    )
  );
}

function ChatSearchPopover({ query, setQuery, mode, setMode, rankedResults, terms, currentChatId, onJump }) {
  const { t } = useLang();
  const bestMatch = rankedResults[0] || null;
  const groups = [
    ["message", t("search_category_messages")],
    ["chat", t("search_category_chats")],
    ["file", t("search_category_files")],
    ["memory", t("search_category_memory")],
    ["workspace", t("search_category_workspaces")],
  ].map(([type, label]) => ({
    type,
    label,
    items: rankedResults.filter((entry) => entry.type === type),
  })).filter((group) => group.items.length > 0);

  return React.createElement("div", {
    style: {
      position: "absolute",
      top: 56,
      right: 0,
      width: 420,
      maxHeight: 520,
      overflow: "auto",
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 16,
      boxShadow: "var(--shadow-lg)",
      padding: 16,
      zIndex: 30,
    },
  },
    React.createElement("div", {
      style: {
        fontSize: 12,
        fontWeight: 700,
        color: "var(--muted)",
        marginBottom: 10,
        textTransform: "uppercase",
        letterSpacing: ".04em",
      },
    }, t("universal_search_hint")),
    React.createElement("input", {
      value: query,
      onChange: (event) => setQuery(event.target.value),
      placeholder: mode === "all" ? t("universal_search_placeholder") : t("search_placeholder"),
      style: {
        width: "100%",
        height: 42,
        padding: "0 14px",
        borderRadius: 12,
        border: "1px solid var(--border)",
        outline: "none",
        background: "var(--surface2)",
        color: "var(--text)",
      },
    }),
    React.createElement("div", {
      style: {
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 8,
        marginTop: 10,
      },
    },
      React.createElement("button", {
        type: "button",
        onClick: () => setMode("chats"),
        style: {
          height: 36,
          borderRadius: 10,
          border: mode === "chats" ? "1px solid var(--accent)" : "1px solid var(--border)",
          background: mode === "chats" ? "rgba(99,102,241,.12)" : "var(--surface2)",
          color: mode === "chats" ? "var(--accent)" : "var(--text2)",
          fontWeight: 800,
        },
      }, t("search_scope_chats")),
      React.createElement("button", {
        type: "button",
        onClick: () => setMode("all"),
        style: {
          height: 36,
          borderRadius: 10,
          border: mode === "all" ? "1px solid var(--accent)" : "1px solid var(--border)",
          background: mode === "all" ? "rgba(99,102,241,.12)" : "var(--surface2)",
          color: mode === "all" ? "var(--accent)" : "var(--text2)",
          fontWeight: 800,
        },
      }, t("search_scope_all"))
    ),
    bestMatch && React.createElement("div", { style: { marginTop: 14 } },
      React.createElement("div", {
        style: {
          fontSize: 12,
          fontWeight: 700,
          color: "var(--muted)",
          marginBottom: 8,
        },
      }, t("best_match")),
      React.createElement(SearchCard, { result: bestMatch, terms, currentChatId, onJump })
    ),
    groups.map((group) => React.createElement("div", { key: group.type, style: { marginTop: 14 } },
      React.createElement("div", {
        style: {
          fontSize: 12,
          fontWeight: 700,
          color: "var(--muted)",
          marginBottom: 8,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        },
      },
        React.createElement("span", null, group.label),
        React.createElement("span", null, group.items.length)
      ),
      group.items.slice(0, 5).map((entry) => React.createElement(SearchCard, {
        key: entry.id,
        result: entry,
        terms,
        currentChatId,
        onJump,
      }))
    )),
    query && !rankedResults.length && React.createElement("div", {
      style: {
        marginTop: 18,
        padding: 16,
        borderRadius: 14,
        border: "1px dashed var(--border2)",
        color: "var(--muted)",
        fontSize: 13,
        lineHeight: 1.55,
      },
    }, t("no_results"))
  );
}

function UniversalSearch({ floating = false }) {
  const { t } = useLang();
  const { activeChatId, chats, files, workspaces, memoryFacts, messagesByChat, loadMessages, selectChat, navigate } = useApp();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("chats");
  const terms = extractTerms(query);

  useEffect(() => {
    if (!open || chats.length === 0) return;
    Promise.all(chats.map((chat) => loadMessages(chat.id).catch(() => []))).catch(() => {});
  }, [open, chats, loadMessages]);

  const entries = useMemo(() => {
    const chatEntries = chats.map((chat) => ({
      type: "chat",
      id: `global-chat-${chat.id}`,
      title: chat.title || t("new_chat"),
      subtitle: t("search_category_chats"),
      searchText: `${chat.title || ""} ${chat.createdAt || ""} ${chat.updatedAt || ""}`,
      chatId: chat.id,
    }));

    const messageEntries = chats.flatMap((chat) =>
      (messagesByChat[chat.id] || []).map((message) => ({
        type: "message",
        id: `global-message-${chat.id}-${message.id}`,
        title: chat.title || t("new_chat"),
        subtitle: `${t("search_category_messages")} · ${message.role}`,
        body: message.content || "",
        searchText: `${chat.title || ""} ${message.role || ""} ${message.content || ""}`,
        chatId: chat.id,
        chatTitle: chat.title,
        message,
      }))
    );

    const fileEntries = files.map((file) => ({
      type: "file",
      id: `global-file-${file.id}`,
      title: file.filename || file.name || t("files"),
      subtitle: `${t("search_category_files")} · ${file.status || ""}`,
      body: [file.mime_type, file.ext, file.status, file.chunks ? `${file.chunks} ${t("chunks_label")}` : ""].filter(Boolean).join(" · "),
      searchText: `${file.filename || ""} ${file.name || ""} ${file.mime_type || ""} ${file.ext || ""} ${file.status || ""}`,
      fileId: file.id,
    }));

    const memoryEntries = memoryFacts.map((fact) => ({
      type: "memory",
      id: `global-memory-${fact.key}`,
      title: fact.key || t("memory_title"),
      subtitle: t("search_category_memory"),
      body: fact.value || "",
      searchText: `${fact.key || ""} ${fact.value || ""}`,
    }));

    const workspaceEntries = workspaces.map((workspace) => ({
      type: "workspace",
      id: `global-workspace-${workspace.id}`,
      title: workspace.name || t("workspaces"),
      subtitle: t("search_category_workspaces"),
      body: workspace.description || "",
      searchText: `${workspace.name || ""} ${workspace.description || ""}`,
      workspaceId: workspace.id,
    }));

    return [...chatEntries, ...messageEntries, ...fileEntries, ...memoryEntries, ...workspaceEntries];
  }, [chats, messagesByChat, files, memoryFacts, workspaces, t]);

  const results = useMemo(() => {
    if (!terms.length) return [];
    return entries
      .map((entry) => ({ ...entry, score: scoreSearchEntry(entry, terms) }))
      .filter((entry) => entry.score > 0)
      .sort((left, right) => right.score - left.score);
  }, [entries, query]);
  const visibleResults = useMemo(() => {
    if (mode === "all") return results;
    return results.filter((entry) => entry.type === "chat" || entry.type === "message");
  }, [results, mode]);

  const jump = async (result) => {
    setOpen(false);

    if (result.type === "message") {
      selectChat(result.chatId);
      await loadMessages(result.chatId, true).catch(() => {});
      setTimeout(() => {
        const node = document.querySelector(`[data-message-id="${result.message.id}"]`);
        if (!node) return;
        node.scrollIntoView({ behavior: "smooth", block: "center" });
        node.animate([
          { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
          { boxShadow: "0 0 0 8px rgba(99,102,241,0.12)" },
          { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
        ], { duration: 1200, easing: "ease-out" });
      }, 120);
      return;
    }

    if (result.type === "chat") selectChat(result.chatId);
    if (result.type === "file") navigate("files");
    if (result.type === "memory") navigate("memory");
    if (result.type === "workspace") navigate("workspaces", { wsId: result.workspaceId });
  };

  return React.createElement("div", { className: floating ? "global-search-floating" : "", style: { position: "relative" } },
    React.createElement("button", {
      className: "btn-primary",
      onClick: () => setOpen((value) => !value),
      style: {
        width: "auto",
        padding: "10px 16px",
        borderRadius: 12,
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        whiteSpace: "nowrap",
      },
    },
      React.createElement(IconSearch),
      React.createElement("span", null, t("search_button"))
    ),
    open && React.createElement(ChatSearchPopover, {
      query,
      setQuery,
      mode,
      setMode,
      rankedResults: visibleResults,
      terms,
      currentChatId: activeChatId,
      onJump: jump,
    })
  );
}

function SearchCard({ result, terms, currentChatId, onJump }) {
  const { t } = useLang();
  const body = result.type === "message" ? result.message.content : (result.body || result.searchText || "");
  const isOtherChat = result.chatId !== currentChatId;
  const typeLabels = {
    message: t("search_category_messages"),
    chat: t("search_category_chats"),
    file: t("search_category_files"),
    memory: t("search_category_memory"),
    workspace: t("search_category_workspaces"),
  };
  return React.createElement("button", {
    onClick: () => onJump(result),
    style: {
      width: "100%",
      textAlign: "left",
      padding: 12,
      marginBottom: 8,
      background: "var(--surface2)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      color: "var(--text)",
    },
  },
    React.createElement("div", {
      style: {
        display: "flex",
        justifyContent: "space-between",
        gap: 10,
        alignItems: "center",
        marginBottom: 6,
      },
    },
      React.createElement("div", {
        style: {
          fontSize: 11,
          color: "var(--muted)",
          textTransform: "uppercase",
          letterSpacing: ".04em",
        },
      }, typeLabels[result.type] || result.type),
      React.createElement("div", {
        style: {
          fontSize: 11,
          color: result.type === "message" && isOtherChat ? "var(--accent)" : "var(--muted)",
          fontWeight: result.type === "message" && isOtherChat ? 700 : 600,
          maxWidth: 190,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        },
      }, result.subtitle || result.chatTitle || "")
    ),
    React.createElement("div", {
      style: {
        fontSize: 13,
        fontWeight: 800,
        marginBottom: body ? 4 : 0,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      },
    }, result.title || ""),
    React.createElement("div", {
      style: {
        fontSize: 13,
        lineHeight: 1.55,
      },
      dangerouslySetInnerHTML: { __html: highlightText(formatSnippet(body, terms), terms) },
    })
  );
}

function EmptyState({ suggestions, onSelect }) {
  const { t } = useLang();
  return React.createElement("div", { className: "empty-state" },
    React.createElement("div", { className: "empty-helm-logo" }, "H"),
    React.createElement("h2", { className: "empty-title" }, t("empty_title")),
    React.createElement("p", { className: "empty-sub" }, t("empty_sub")),
    React.createElement("div", { className: "suggestion-grid" },
      suggestions.map((suggestion) => React.createElement("button", {
        key: suggestion,
        className: "suggestion-card",
        onClick: () => onSelect(suggestion),
      }, suggestion))
    )
  );
}

function Message({ msg, highlighted }) {
  const { t } = useLang();
  const [copied, setCopied] = useState(false);
  const isAI = msg.role === "assistant";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(msg.content || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) {
      setCopied(false);
    }
  };

  const rendered = isAI
    ? md(msg.content)
    : highlightText(msg.content, highlighted || []);

  const highlightedHtml = isAI && highlighted?.length
    ? rendered.replace(
        new RegExp(`(${highlighted.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi"),
        '<mark style="background: rgba(99,102,241,.18); color: inherit; padding: 0 2px; border-radius: 4px;">$1</mark>'
      )
    : rendered;

  return React.createElement("div", {
    className: `msg msg--${msg.role}`,
    "data-message-id": msg.id,
  },
    React.createElement("div", { className: "msg-avatar" },
      isAI
        ? React.createElement("div", { className: "msg-helm-av" }, "H")
        : React.createElement(Avatar, { name: "U", size: 32 })
    ),
    React.createElement("div", { className: "msg-body" },
      isAI && React.createElement("div", { className: "msg-meta" },
        msg.model && React.createElement(ModelBadge, { model: msg.model, taskType: msg.taskType }),
        React.createElement("span", { className: "msg-ts" }, new Date(msg.ts).toLocaleString())
      ),
      isAI
        ? React.createElement("div", {
            className: "msg-text msg-text--ai markdown-body",
            dangerouslySetInnerHTML: { __html: highlightedHtml },
          })
        : React.createElement("div", {
            className: "msg-text msg-text--user",
            dangerouslySetInnerHTML: { __html: rendered },
          }),
      isAI && msg.sources?.length > 0 && React.createElement(SourcePanel, { sources: msg.sources }),
      React.createElement("div", { className: "msg-actions" },
        React.createElement("button", { className: "msg-action", onClick: copy },
          copied ? React.createElement(IconCheck) : React.createElement(IconCopy),
          React.createElement("span", null, copied ? t("copied") : t("copy"))
        )
      )
    )
  );
}

function SourcePanel({ sources }) {
  const { t } = useLang();
  return React.createElement("div", { className: "source-panel" },
    React.createElement("div", { className: "source-panel-title" },
      React.createElement(IconFile, { width: 14, height: 14 }),
      React.createElement("span", null, t("sources")),
      React.createElement("span", { className: "source-count" }, sources.length)
    ),
    React.createElement("div", { className: "source-list" },
      sources.slice(0, 5).map((source) => React.createElement("div", {
        key: `${source.document_id || "doc"}-${source.chunk_index || source.source_id}`,
        className: "source-card",
      },
        React.createElement("div", { className: "source-card-head" },
          React.createElement("span", { className: "source-file" }, source.filename || "Document"),
          React.createElement("span", { className: "source-meta" },
            `${t("source_chunk")} ${Number.isFinite(source.chunk_index) ? source.chunk_index + 1 : source.source_id || ""}`
          )
        ),
        source.score != null && React.createElement("div", { className: "source-score" },
          `${Math.round(source.score * 100)}% ${t("source_relevance")}`
        ),
        React.createElement("div", { className: "source-snippet" }, source.snippet || "")
      ))
    )
  );
}

function ThinkingRow() {
  const { t } = useLang();
  return React.createElement("div", { className: "msg msg--assistant" },
    React.createElement("div", { className: "msg-avatar" },
      React.createElement("div", { className: "msg-helm-av" }, "H")
    ),
    React.createElement("div", { className: "msg-body" },
      React.createElement("div", { className: "thinking-row" },
        React.createElement(Spinner, { size: 13 }),
        React.createElement("span", null, t("thinking"))
      )
    )
  );
}

Object.assign(window, { ChatView, UniversalSearch });
