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
  const { t } = useLang();
  const { activeChat, activeMessages, files, sendMessage, thinking, refreshChat } = useApp();
  const [input, setInput] = useState("");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [memoryMode, setMemoryMode] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlight, setHighlight] = useState(null);
  const messagesRef = useRef(null);
  const textRef = useRef(null);

  const messages = activeMessages || [];
  const terms = extractTerms(searchQuery);
  const rankedResults = useMemo(() => {
    if (!terms.length) return [];
    return messages
      .map((message) => ({ message, score: scoreMessage(message, terms) }))
      .filter((entry) => entry.score > 0)
      .sort((left, right) => right.score - left.score);
  }, [messages, searchQuery]);

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages.length, thinking]);

  const resize = () => {
    const node = textRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 200)}px`;
  };

  const jumpTo = (message) => {
    if (!message) return;
    setHighlight({ messageId: message.id, terms });
    setSearchOpen(false);
    const node = document.querySelector(`[data-message-id="${message.id}"]`);
    if (node) {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
      node.animate([
        { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
        { boxShadow: "0 0 0 8px rgba(99,102,241,0.12)" },
        { boxShadow: "0 0 0 0 rgba(99,102,241,0)" },
      ], { duration: 1200, easing: "ease-out" });
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
        }, t("current_chat_search"))
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
          React.createElement("span", null, t("search_chat"))
        ),
        searchOpen && React.createElement(ChatSearchPopover, {
          query: searchQuery,
          setQuery: setSearchQuery,
          rankedResults,
          terms,
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

function ChatSearchPopover({ query, setQuery, rankedResults, terms, onJump }) {
  const { t } = useLang();
  const bestMatch = rankedResults[0]?.message || null;
  const exactMatches = rankedResults.filter((entry) =>
    terms.some((term) => String(entry.message.content || "").toLowerCase().includes(term.toLowerCase()))
  );
  const contextMatches = rankedResults.filter((entry) => !exactMatches.includes(entry));

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
    }, t("search_chat_hint")),
    React.createElement("input", {
      value: query,
      onChange: (event) => setQuery(event.target.value),
      placeholder: t("search_placeholder"),
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
    bestMatch && React.createElement("div", { style: { marginTop: 14 } },
      React.createElement("div", {
        style: {
          fontSize: 12,
          fontWeight: 700,
          color: "var(--muted)",
          marginBottom: 8,
        },
      }, t("best_match")),
      React.createElement(SearchCard, { message: bestMatch, terms, onJump })
    ),
    exactMatches.length > 0 && React.createElement("div", { style: { marginTop: 14 } },
      React.createElement("div", {
        style: {
          fontSize: 12,
          fontWeight: 700,
          color: "var(--muted)",
          marginBottom: 8,
        },
      }, `${t("exact_matches")} · ${exactMatches.length}`),
      exactMatches.slice(0, 6).map((entry) => React.createElement(SearchCard, {
        key: `exact-${entry.message.id}`,
        message: entry.message,
        terms,
        onJump,
      }))
    ),
    contextMatches.length > 0 && React.createElement("div", { style: { marginTop: 14 } },
      React.createElement("div", {
        style: {
          fontSize: 12,
          fontWeight: 700,
          color: "var(--muted)",
          marginBottom: 8,
        },
      }, `${t("context_matches")} · ${contextMatches.length}`),
      contextMatches.slice(0, 6).map((entry) => React.createElement(SearchCard, {
        key: `ctx-${entry.message.id}`,
        message: entry.message,
        terms,
        onJump,
      }))
    ),
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

function SearchCard({ message, terms, onJump }) {
  return React.createElement("button", {
    onClick: () => onJump(message),
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
        fontSize: 11,
        color: "var(--muted)",
        marginBottom: 6,
        textTransform: "uppercase",
        letterSpacing: ".04em",
      },
    }, message.role),
    React.createElement("div", {
      style: {
        fontSize: 13,
        lineHeight: 1.55,
      },
      dangerouslySetInnerHTML: { __html: highlightText(formatSnippet(message.content, terms), terms) },
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
      React.createElement("div", { className: "msg-actions" },
        React.createElement("button", { className: "msg-action", onClick: copy },
          copied ? React.createElement(IconCheck) : React.createElement(IconCopy),
          React.createElement("span", null, copied ? t("copied") : t("copy"))
        )
      )
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

Object.assign(window, { ChatView });
