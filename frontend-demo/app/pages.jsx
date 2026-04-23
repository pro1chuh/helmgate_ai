function AuthPage() {
  const { t } = useLang();
  const { login, register } = useApp();
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        await register({ name: name.trim(), email: email.trim(), password });
      } else {
        await login({ email: email.trim(), password });
      }
    } catch (err) {
      setError(err?.detail || err?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return React.createElement("div", { className: "auth-screen" },
    React.createElement("div", { className: "auth-card" },
      React.createElement("div", { className: "auth-logo" },
        React.createElement("div", { className: "auth-logo-mark" }, "H"),
        React.createElement("span", { className: "auth-logo-text" }, t("app_name"))
      ),
      React.createElement("p", { className: "auth-tagline" }, t("auth_subtitle")),
      React.createElement("div", { className: "auth-tabs" },
        React.createElement("button", {
          className: `auth-tab ${mode === "login" ? "active" : ""}`,
          onClick: () => setMode("login"),
        }, t("sign_in")),
        React.createElement("button", {
          className: `auth-tab ${mode === "register" ? "active" : ""}`,
          onClick: () => setMode("register"),
        }, t("sign_up"))
      ),
      React.createElement("form", { onSubmit: submit },
        mode === "register" && React.createElement("div", { className: "auth-field" },
          React.createElement("label", null, t("full_name")),
          React.createElement("input", {
            className: "auth-input",
            value: name,
            onChange: (event) => setName(event.target.value),
            placeholder: "Anatoly",
            required: mode === "register",
          })
        ),
        React.createElement("div", { className: "auth-field" },
          React.createElement("label", null, t("email")),
          React.createElement("input", {
            className: "auth-input",
            type: "email",
            value: email,
            onChange: (event) => setEmail(event.target.value),
            placeholder: "you@company.com",
            required: true,
          })
        ),
        React.createElement("div", { className: "auth-field" },
          React.createElement("label", null, t("password")),
          React.createElement("input", {
            className: "auth-input",
            type: "password",
            value: password,
            onChange: (event) => setPassword(event.target.value),
            placeholder: "••••••••",
            required: true,
          })
        ),
        error && React.createElement("div", {
          style: {
            color: "#EF4444",
            fontSize: 13,
            marginBottom: 12,
            lineHeight: 1.45,
          },
        }, error),
        React.createElement("button", {
          type: "submit",
          className: "auth-submit",
          disabled: loading,
        }, loading ? React.createElement(Spinner, { size: 16 }) : t(mode === "login" ? "sign_in" : "sign_up"))
      )
    )
  );
}

function FilesPage() {
  const { t } = useLang();
  const { files, uploadFiles, deleteFile } = useApp();
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef(null);

  const onFiles = async (list) => {
    if (!list?.length) return;
    setError("");
    try {
      await uploadFiles(Array.from(list));
    } catch (err) {
      setError(err?.detail || err?.message || "Upload failed");
    }
  };

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", null,
        React.createElement("h1", { className: "page-title" }, t("knowledge_base")),
        React.createElement("p", { className: "page-sub" }, `${files.length} · RAG`)
      ),
      React.createElement("button", {
        className: "btn-primary",
        onClick: () => fileRef.current?.click(),
        style: {
          width: "auto",
          padding: "10px 18px",
          borderRadius: 12,
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
        },
      },
        React.createElement(IconUpload),
        React.createElement("span", null, t("upload_files"))
      )
    ),
    React.createElement("input", {
      ref: fileRef,
      type: "file",
      multiple: true,
      style: { display: "none" },
      onChange: (event) => {
        onFiles(event.target.files);
        event.target.value = "";
      },
    }),
    React.createElement("div", {
      className: `drop-zone ${dragging ? "dragging" : ""}`,
      style: {
        minHeight: 156,
        borderRadius: 18,
        borderStyle: "dashed",
        borderWidth: 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        background: dragging ? "var(--accent-lt)" : "var(--surface)",
        marginBottom: 24,
      },
      onDragOver: (event) => {
        event.preventDefault();
        setDragging(true);
      },
      onDragLeave: () => setDragging(false),
      onDrop: (event) => {
        event.preventDefault();
        setDragging(false);
        onFiles(event.dataTransfer.files);
      },
      onClick: () => fileRef.current?.click(),
    },
      React.createElement("div", {
        style: {
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 10,
          maxWidth: 560,
          padding: "12px 24px",
        },
      },
        React.createElement("div", {
          style: {
            width: 40,
            height: 40,
            borderRadius: 999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--muted)",
            background: "var(--surface2)",
            border: "1px solid var(--border)",
          },
        }, React.createElement(IconUpload)),
        React.createElement("div", {
          style: {
            fontSize: 14,
            color: "var(--text2)",
            lineHeight: 1.5,
            fontWeight: 500,
          },
        }, t("drop_files")),
        React.createElement("div", {
          className: "drop-hint",
          style: {
            fontSize: 13,
            color: "var(--muted)",
          },
        }, t("supported_formats"))
      )
    ),
    error && React.createElement("div", {
      style: {
        color: "#EF4444",
        marginBottom: 16,
        fontSize: 13,
      },
    }, error),
    React.createElement("div", { className: "files-list" },
      files.length > 0 && files.map((file) =>
        React.createElement("div", { key: file.id, className: "file-row" },
          React.createElement(FileTypeIcon, {
            ext: (file.filename?.split(".").pop() || "file").toLowerCase(),
          }),
          React.createElement("div", { className: "file-info" },
            React.createElement("div", { className: "file-name" }, file.filename),
            React.createElement("div", { className: "file-meta" },
              `${Math.round((file.size_bytes || 0) / 1024)} KB · ${new Date(file.created_at).toLocaleString()}`
            )
          ),
          React.createElement("div", { className: `file-status file-status--${file.indexed ? "indexed" : "indexing"}` },
            file.indexed ? t("indexed") : t("indexing")
          ),
          React.createElement("button", {
            className: "icon-btn-ghost",
            onClick: () => deleteFile(file.id),
          }, React.createElement(IconTrash))
        )
      )
    )
  );
}

function WorkspacesPage() {
  const { t } = useLang();
  const { workspaces, createWorkspace, navigate } = useApp();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  const submit = async () => {
    if (!name.trim()) return;
    setError("");
    try {
      const ws = await createWorkspace({ name: name.trim(), description: description.trim() || null });
      setCreating(false);
      setName("");
      setDescription("");
      navigate("ws-detail", { wsId: ws.id });
    } catch (err) {
      setError(err?.detail || err?.message || "Create failed");
    }
  };

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", null,
        React.createElement("h1", { className: "page-title" }, t("workspaces")),
        React.createElement("p", { className: "page-sub" }, `${workspaces.length} ${t("workspaces").toLowerCase()}`)
      ),
      React.createElement("button", {
        className: "btn-primary",
        onClick: () => setCreating((value) => !value),
      },
        React.createElement(IconPlus),
        React.createElement("span", null, t("add_workspace"))
      )
    ),
    creating && React.createElement("div", {
      className: "profile-section",
      style: { marginBottom: 20, maxWidth: 520 },
    },
      React.createElement("div", { className: "profile-section-title" }, t("create_workspace")),
      React.createElement("div", { className: "profile-field" },
        React.createElement("label", null, t("workspace_name")),
        React.createElement("input", {
          className: "profile-input",
          value: name,
          onChange: (event) => setName(event.target.value),
        })
      ),
      React.createElement("div", { className: "profile-field" },
        React.createElement("label", null, t("workspace_description")),
        React.createElement("input", {
          className: "profile-input",
          value: description,
          onChange: (event) => setDescription(event.target.value),
        })
      ),
      error && React.createElement("div", { style: { color: "#EF4444", fontSize: 13 } }, error),
      React.createElement("button", { className: "btn-primary", onClick: submit }, t("save"))
    ),
    React.createElement("div", { className: "ws-grid" },
      workspaces.length === 0 && React.createElement("div", { className: "sb-empty", style: { gridColumn: "1 / -1" } },
        React.createElement(IconFolder),
        React.createElement("p", null, t("no_workspaces"))
      ),
      workspaces.map((workspace) =>
        React.createElement("div", { key: workspace.id, className: "ws-card" },
          React.createElement("div", { className: "ws-card-top" },
            React.createElement("div", { className: "ws-icon" }, workspace.name.charAt(0).toUpperCase()),
            React.createElement("div", { className: "ws-name" }, workspace.name)
          ),
          React.createElement("div", { className: "ws-stats" },
            React.createElement("div", { className: "ws-stat" },
              React.createElement("div", { className: "ws-stat-val" }, workspace.member_count || 1),
              React.createElement("div", { className: "ws-stat-key" }, t("members_label"))
            ),
            React.createElement("div", { className: "ws-stat" },
              React.createElement("div", { className: "ws-stat-val" }, workspace.owner_id),
              React.createElement("div", { className: "ws-stat-key" }, "owner")
            )
          ),
          React.createElement("button", {
            className: "ws-open-btn",
            onClick: () => navigate("ws-detail", { wsId: workspace.id }),
          }, t("open_ws"))
        )
      )
    )
  );
}

function WorkspaceDetail() {
  const { t } = useLang();
  const { wsDetailId, workspaces, workspaceMembers, loadWorkspaceMembers, navigate } = useApp();
  const [tab, setTab] = useState("members");
  const workspace = workspaces.find((item) => item.id === wsDetailId);
  const members = workspaceMembers[wsDetailId] || [];

  useEffect(() => {
    if (wsDetailId) {
      loadWorkspaceMembers(wsDetailId).catch(() => {});
    }
  }, [wsDetailId, loadWorkspaceMembers]);

  if (!workspace) {
    return React.createElement("div", { className: "page" },
      React.createElement("p", { className: "page-sub" }, t("load_error"))
    );
  }

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 12 } },
        React.createElement("button", {
          className: "back-btn",
          onClick: () => navigate("workspaces", { wsId: null }),
        }, React.createElement(IconChevron, { dir: "left", size: 16 })),
        React.createElement("div", null,
          React.createElement("h1", { className: "page-title" }, workspace.name),
          React.createElement("p", { className: "page-sub" }, workspace.description || "No description")
        )
      )
    ),
    React.createElement("div", { className: "detail-tabs" },
      ["members", "settings"].map((value) =>
        React.createElement("button", {
          key: value,
          className: `detail-tab ${tab === value ? "active" : ""}`,
          onClick: () => setTab(value),
        }, value === "members" ? t("workspace_members") : t("workspace_settings"))
      )
    ),
    tab === "members" && React.createElement("div", { className: "members-list" },
      members.map((member) =>
        React.createElement("div", { key: `${member.user_id}-${member.joined_at}`, className: "member-row" },
          React.createElement(Avatar, { name: String(member.user_id), size: 36 }),
          React.createElement("div", { className: "member-info" },
            React.createElement("div", { className: "member-name" }, `User #${member.user_id}`),
            React.createElement("div", { className: "member-email" }, member.joined_at)
          ),
          React.createElement("span", { className: "role-badge" }, member.role)
        )
      )
    ),
    tab === "settings" && React.createElement("div", { className: "profile-wrap" },
      React.createElement("div", { className: "profile-section" },
        React.createElement("div", { className: "profile-section-title" }, t("workspace_settings")),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, t("workspace_name")),
          React.createElement("input", {
            className: "profile-input",
            value: workspace.name,
            readOnly: true,
          })
        ),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, t("workspace_description")),
          React.createElement("input", {
            className: "profile-input",
            value: workspace.description || "",
            readOnly: true,
          })
        )
      )
    )
  );
}

function AdminPage() {
  const { t } = useLang();
  const { stats } = useApp();

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", null,
        React.createElement("h1", { className: "page-title" }, t("system_status")),
        React.createElement("p", { className: "page-sub" }, t("live_backend"))
      )
    ),
    React.createElement("div", { className: "stat-grid" },
      [
        [t("total_requests"), stats.total_requests],
        [t("active_users"), stats.active_users],
        [t("tokens_used"), stats.tokens_used],
        [t("cache_hits"), stats.cache_hits],
      ].map(([label, value]) =>
        React.createElement("div", { key: label, className: "stat-card" },
          React.createElement("div", { className: "stat-label" }, label),
          React.createElement("div", { className: "stat-value" }, value)
        )
      )
    )
  );
}

function MemoryManager() {
  const { t } = useLang();
  const { memoryFacts, upsertMemoryFact, deleteMemoryFact, activeChat, activeMessages } = useApp();
  const [memoryKey, setMemoryKey] = useState("");
  const [memoryValue, setMemoryValue] = useState("");
  const [editingKey, setEditingKey] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const exampleFacts = [
    { key: "project_role", value: "product manager" },
    { key: "preferred_language", value: "русский" },
    { key: "response_style", value: "кратко и по делу" },
    { key: "current_project", value: "HelpGate AI" },
  ];

  const prettyKey = (key) => String(key || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());

  const saveMemory = async () => {
    const key = memoryKey.trim();
    const value = memoryValue.trim();
    if (!key || !value) return;

    setMessage("");
    setError("");
    try {
      await upsertMemoryFact({ key, value });
      setMessage(t("memory_saved"));
      setMemoryKey("");
      setMemoryValue("");
      setEditingKey("");
    } catch (err) {
      setError(err?.detail || err?.message || "Memory save failed");
    }
  };

  const applyExample = (fact) => {
    setMemoryKey(fact.key);
    setMemoryValue(fact.value);
    setEditingKey("");
    setMessage("");
    setError("");
  };

  const startEditMemory = (fact) => {
    setMemoryKey(fact.key);
    setMemoryValue(fact.value);
    setEditingKey(fact.key);
    setMessage("");
    setError("");
  };

  const removeMemory = async (key) => {
    setMessage("");
    setError("");
    try {
      await deleteMemoryFact(key);
      if (editingKey === key) {
        setMemoryKey("");
        setMemoryValue("");
        setEditingKey("");
      }
      setMessage(t("memory_deleted"));
    } catch (err) {
      setError(err?.detail || err?.message || "Memory delete failed");
    }
  };

  const useCurrentChat = () => {
    const lastUserMessage = [...(activeMessages || [])].reverse().find((item) => item.role === "user" && item.content?.trim());
    const sourceText = lastUserMessage?.content?.trim() || activeChat?.title?.trim() || "";
    if (!sourceText) {
      setMessage("");
      setError(t("memory_chat_empty"));
      return;
    }

    const compact = sourceText.replace(/\s+/g, " ").trim();
    setMemoryKey("current_context");
    setMemoryValue(compact.slice(0, 240));
    setEditingKey("");
    setError("");
    setMessage(t("memory_chat_saved"));
  };

  return React.createElement("div", {
    className: "profile-section",
    style: { marginBottom: 0 },
  },
    React.createElement("div", { className: "profile-section-title" }, t("memory_title")),
    React.createElement("div", {
      style: {
        fontSize: 13,
        color: "var(--muted)",
        marginBottom: 16,
        lineHeight: 1.55,
      },
    }, t("memory_subtitle")),
    React.createElement("div", {
      style: {
        padding: "12px 14px",
        borderRadius: 12,
        background: "var(--accent-lt)",
        color: "var(--text2)",
        fontSize: 13,
        lineHeight: 1.55,
        marginBottom: 14,
      },
    }, t("memory_help")),
    React.createElement("div", {
      style: {
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 12,
        marginBottom: 12,
        flexWrap: "wrap",
      },
    },
      React.createElement("div", {
        style: {
          fontSize: 12,
          fontWeight: 800,
          color: "var(--muted)",
          textTransform: "uppercase",
          letterSpacing: ".05em",
        },
      }, t("memory_examples")),
      React.createElement("button", {
        className: "msg-action",
        onClick: useCurrentChat,
      }, t("memory_use_chat"))
    ),
    React.createElement("div", {
      style: {
        display: "flex",
        gap: 8,
        flexWrap: "wrap",
        marginBottom: 16,
      },
    },
      exampleFacts.map((fact) => React.createElement("button", {
        key: `${fact.key}-${fact.value}`,
        className: "msg-action",
        onClick: () => applyExample(fact),
      }, `${prettyKey(fact.key)}: ${fact.value}`))
    ),
    React.createElement("div", { className: "profile-field" },
      React.createElement("label", null, t("memory_key")),
      React.createElement("input", {
        className: "profile-input",
        value: memoryKey,
        onChange: (event) => setMemoryKey(event.target.value),
        placeholder: "project_role",
      })
    ),
    React.createElement("div", { className: "profile-field" },
      React.createElement("label", null, t("memory_value")),
      React.createElement("input", {
        className: "profile-input",
        value: memoryValue,
        onChange: (event) => setMemoryValue(event.target.value),
        placeholder: "Product manager",
      })
    ),
    React.createElement("div", {
      style: {
        fontSize: 12,
        color: "var(--muted)",
        marginBottom: 14,
      },
    }, t("memory_form_hint")),
    React.createElement("button", { className: "btn-primary", onClick: saveMemory }, editingKey ? t("memory_save") : t("memory_add")),
    message && React.createElement("div", { style: { color: "#10B981", fontSize: 13, marginTop: 14 } }, message),
    error && React.createElement("div", { style: { color: "#EF4444", fontSize: 13, marginTop: 14 } }, error),
    React.createElement("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        gap: 10,
        marginTop: 18,
      },
    },
      memoryFacts.length === 0
        ? React.createElement("div", {
            style: {
              padding: "14px 16px",
              borderRadius: 10,
              background: "var(--surface2)",
              color: "var(--muted)",
              fontSize: 13,
            },
          }, t("memory_empty"))
        : memoryFacts.map((fact) => React.createElement("div", {
            key: fact.id || fact.key,
            style: {
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 14,
              background: "var(--surface2)",
            },
          },
            React.createElement("div", {
              style: {
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                alignItems: "flex-start",
              },
            },
              React.createElement("div", { style: { minWidth: 0, flex: 1 } },
                React.createElement("div", {
                  style: {
                    fontSize: 12,
                    fontWeight: 800,
                    color: "var(--accent)",
                    textTransform: "uppercase",
                    letterSpacing: ".04em",
                    marginBottom: 4,
                  },
                }, prettyKey(fact.key)),
                React.createElement("div", {
                  style: {
                    fontSize: 14,
                    color: "var(--text)",
                    lineHeight: 1.55,
                    wordBreak: "break-word",
                  },
                }, fact.value),
                React.createElement("div", {
                  style: {
                    fontSize: 11,
                    color: "var(--muted)",
                    marginTop: 8,
                  },
                }, `${t("memory_updated_at")}: ${new Date(fact.updated_at).toLocaleString()}`)
              ),
              React.createElement("div", { style: { display: "flex", gap: 6, flexShrink: 0 } },
                React.createElement("button", {
                  className: "msg-action",
                  onClick: () => startEditMemory(fact),
                }, t("edit")),
                React.createElement("button", {
                  className: "msg-action",
                  onClick: () => removeMemory(fact.key),
                }, t("delete"))
              )
            )
          ))
    )
  );
}

function MemoryPage() {
  const { t } = useLang();
  const { memoryFacts, activeChat, activeMessages, upsertMemoryFact, deleteMemoryFact } = useApp();
  const [memoryKey, setMemoryKey] = useState("");
  const [memoryValue, setMemoryValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const exampleFacts = [
    { key: "project_role", value: "product manager" },
    { key: "preferred_language", value: "русский" },
    { key: "response_style", value: "кратко и по делу" },
    { key: "current_project", value: "HelpGate AI" },
  ];

  const prettyKey = (key) => String(key || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());

  const saveMemory = async () => {
    const key = memoryKey.trim();
    const value = memoryValue.trim();
    if (!key || !value) return;
    setMessage("");
    setError("");
    try {
      await upsertMemoryFact({ key, value });
      setMemoryKey("");
      setMemoryValue("");
      setMessage(t("memory_saved"));
    } catch (err) {
      setError(err?.detail || err?.message || "Memory save failed");
    }
  };

  const applyExample = (fact) => {
    setMemoryKey(fact.key);
    setMemoryValue(fact.value);
    setMessage("");
    setError("");
  };

  const useCurrentChat = () => {
    const lastUserMessage = [...(activeMessages || [])].reverse().find((item) => item.role === "user" && item.content?.trim());
    const sourceText = lastUserMessage?.content?.trim() || activeChat?.title?.trim() || "";
    if (!sourceText) {
      setMessage("");
      setError(t("memory_chat_empty"));
      return;
    }
    setMemoryKey("current_context");
    setMemoryValue(sourceText.replace(/\s+/g, " ").trim().slice(0, 240));
    setError("");
    setMessage(t("memory_chat_saved"));
  };

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", null,
        React.createElement("h1", { className: "page-title" }, t("memory_title")),
        React.createElement("p", { className: "page-sub" }, t("memory_subtitle"))
      )
    ),
    React.createElement("div", { className: "profile-wrap", style: { maxWidth: 820 } },
      React.createElement("div", { className: "profile-section" },
        React.createElement("div", { className: "profile-section-title" }, t("memory_title")),
        React.createElement("div", {
          style: {
            padding: "12px 14px",
            borderRadius: 12,
            background: "var(--accent-lt)",
            color: "var(--text2)",
            fontSize: 13,
            lineHeight: 1.55,
            marginBottom: 14,
          },
        }, t("memory_help")),
        React.createElement("div", {
          style: {
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            marginBottom: 12,
            flexWrap: "wrap",
          },
        },
          React.createElement("div", {
            style: {
              fontSize: 12,
              fontWeight: 800,
              color: "var(--muted)",
              textTransform: "uppercase",
              letterSpacing: ".05em",
            },
          }, t("memory_examples")),
          React.createElement("button", { className: "msg-action", onClick: useCurrentChat }, t("memory_use_chat"))
        ),
        React.createElement("div", {
          style: {
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            marginBottom: 16,
          },
        },
          exampleFacts.map((fact) => React.createElement("button", {
            key: `${fact.key}-${fact.value}`,
            className: "msg-action",
            onClick: () => applyExample(fact),
          }, `${prettyKey(fact.key)}: ${fact.value}`))
        ),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, t("memory_key")),
          React.createElement("input", {
            className: "profile-input",
            value: memoryKey,
            onChange: (event) => setMemoryKey(event.target.value),
            placeholder: "project_role",
          })
        ),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, t("memory_value")),
          React.createElement("input", {
            className: "profile-input",
            value: memoryValue,
            onChange: (event) => setMemoryValue(event.target.value),
            placeholder: "Product manager",
          })
        ),
        React.createElement("div", {
          style: {
            fontSize: 12,
            color: "var(--muted)",
            marginBottom: 14,
          },
        }, t("memory_form_hint")),
        React.createElement("button", { className: "btn-primary", onClick: saveMemory }, t("memory_add")),
        message && React.createElement("div", { style: { color: "#10B981", fontSize: 13, marginTop: 14 } }, message),
        error && React.createElement("div", { style: { color: "#EF4444", fontSize: 13, marginTop: 14 } }, error),
        React.createElement("div", {
          style: {
            display: "flex",
            flexDirection: "column",
            gap: 10,
            marginTop: 18,
          },
        },
          memoryFacts.length === 0
            ? React.createElement("div", {
                style: {
                  padding: "14px 16px",
                  borderRadius: 10,
                  background: "var(--surface2)",
                  color: "var(--muted)",
                  fontSize: 13,
                },
              }, t("memory_empty"))
            : memoryFacts.map((fact) => React.createElement("div", {
                key: fact.id || fact.key,
                style: {
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: 14,
                  background: "var(--surface2)",
                },
              },
                React.createElement("div", {
                  style: {
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    alignItems: "flex-start",
                  },
                },
                  React.createElement("div", { style: { minWidth: 0, flex: 1 } },
                    React.createElement("div", {
                      style: {
                        fontSize: 12,
                        fontWeight: 800,
                        color: "var(--accent)",
                        textTransform: "uppercase",
                        letterSpacing: ".04em",
                        marginBottom: 4,
                      },
                    }, prettyKey(fact.key)),
                    React.createElement("div", {
                      style: {
                        fontSize: 14,
                        color: "var(--text)",
                        lineHeight: 1.55,
                        wordBreak: "break-word",
                      },
                    }, fact.value),
                    React.createElement("div", {
                      style: {
                        fontSize: 11,
                        color: "var(--muted)",
                        marginTop: 8,
                      },
                    }, `${t("memory_updated_at")}: ${new Date(fact.updated_at).toLocaleString()}`)
                  ),
                  React.createElement("button", {
                    className: "msg-action",
                    onClick: () => deleteMemoryFact(fact.key),
                  }, t("delete"))
                )
              ))
        )
      )
    )
  );
}

function ProfilePage() {
  const { t } = useLang();
  const { user, updateProfile, changePassword, logout } = useApp();
  const [name, setName] = useState(user?.name || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setName(user?.name || "");
  }, [user?.name]);

  const saveProfile = async () => {
    setMessage("");
    setError("");
    try {
      await updateProfile({ name });
      setMessage(t("profile_saved"));
    } catch (err) {
      setError(err?.detail || err?.message || "Save failed");
    }
  };

  const savePassword = async () => {
    setMessage("");
    setError("");
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setMessage(t("password_changed"));
    } catch (err) {
      setError(err?.detail || err?.message || "Password change failed");
    }
  };

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", null,
        React.createElement("h1", { className: "page-title" }, t("profile")),
        React.createElement("p", { className: "page-sub" }, user?.email || "")
      )
    ),
    React.createElement("div", { className: "profile-wrap" },
      React.createElement("div", { className: "profile-section" },
        React.createElement("div", { className: "profile-section-title" }, t("general_settings")),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, t("full_name")),
          React.createElement("input", {
            className: "profile-input",
            value: name,
            onChange: (event) => setName(event.target.value),
          })
        ),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, t("email")),
          React.createElement("input", {
            className: "profile-input",
            value: user?.email || "",
            readOnly: true,
          })
        ),
        React.createElement("button", { className: "btn-primary", onClick: saveProfile }, t("save"))
      ),
      React.createElement("div", { className: "profile-section" },
        React.createElement("div", { className: "profile-section-title" }, t("security")),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, "Current password"),
          React.createElement("input", {
            type: "password",
            className: "profile-input",
            value: currentPassword,
            onChange: (event) => setCurrentPassword(event.target.value),
          })
        ),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, "New password"),
          React.createElement("input", {
            type: "password",
            className: "profile-input",
            value: newPassword,
            onChange: (event) => setNewPassword(event.target.value),
          })
        ),
        React.createElement("button", { className: "btn-primary", onClick: savePassword }, t("change_password"))
      ),
      React.createElement("button", { className: "btn-danger", onClick: logout },
        React.createElement(IconLogout),
        React.createElement("span", null, t("logout"))
      ),
      message && React.createElement("div", { style: { color: "#10B981", fontSize: 13 } }, message),
      error && React.createElement("div", { style: { color: "#EF4444", fontSize: 13 } }, error)
    )
  );
}

function MemoryPageTest() {
  const { t } = useLang();
  const { memoryFacts } = useApp();

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", null,
        React.createElement("h1", { className: "page-title" }, t("memory_title")),
        React.createElement("p", { className: "page-sub" }, t("memory_subtitle"))
      )
    ),
    React.createElement("div", {
      style: {
        maxWidth: 860,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      },
    },
      React.createElement("div", {
        style: {
          padding: "20px",
          borderRadius: 18,
          border: "1px solid var(--border)",
          background: "var(--surface)",
          boxShadow: "var(--shadow-sm)",
        },
      },
        React.createElement("div", {
          style: {
            fontSize: 18,
            fontWeight: 800,
            color: "var(--text)",
            marginBottom: 8,
          },
        }, "Memory page works"),
        React.createElement("div", {
          style: {
            color: "var(--text2)",
            lineHeight: 1.6,
          },
        }, t("memory_help"))
      ),
      React.createElement("div", {
        style: {
          padding: "20px",
          borderRadius: 18,
          border: "1px solid var(--border)",
          background: "var(--surface)",
          boxShadow: "var(--shadow-sm)",
        },
      },
        React.createElement("div", {
          style: {
            fontSize: 14,
            fontWeight: 700,
            color: "var(--text)",
            marginBottom: 12,
          },
        }, `Facts: ${memoryFacts.length}`),
        memoryFacts.length === 0
          ? React.createElement("div", {
              style: {
                color: "var(--muted)",
                fontSize: 14,
              },
            }, t("memory_empty"))
          : React.createElement("div", {
              style: {
                display: "flex",
                flexDirection: "column",
                gap: 10,
              },
            },
            memoryFacts.map((fact) => React.createElement("div", {
              key: fact.key || fact.id,
              style: {
                padding: "12px 14px",
                borderRadius: 14,
                background: "var(--surface2)",
                border: "1px solid var(--border)",
              },
            },
              React.createElement("div", {
                style: {
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 4,
                },
              }, fact.key || "fact"),
              React.createElement("div", {
                style: {
                  color: "var(--text2)",
                  lineHeight: 1.5,
                },
              }, fact.value || "")
            ))
          )
      )
    )
  );
}

function MemoryPageV2() {
  const { t, lang } = useLang();
  const { memoryFacts, activeChat, activeMessages, upsertMemoryFact, deleteMemoryFact } = useApp();
  const isRu = lang === "ru";
  const templates = [
    {
      id: "preferred_language",
      key: "preferred_language",
      label: isRu ? "Язык общения" : "Language",
      description: isRu ? "На каком языке Helm должен отвечать вам" : "Which language Helm should use in replies",
      example: isRu ? "русский" : "English",
      placeholder: isRu ? "Например: русский" : "For example: English",
    },
    {
      id: "project_role",
      key: "project_role",
      label: isRu ? "Моя роль" : "My role",
      description: isRu ? "Кто вы в проекте или команде" : "Who you are in the project or team",
      example: "product manager",
      placeholder: isRu ? "Например: product manager" : "For example: product manager",
    },
    {
      id: "response_style",
      key: "response_style",
      label: isRu ? "Стиль ответов" : "Response style",
      description: isRu ? "Как Helm должен формулировать ответы" : "How Helm should phrase its answers",
      example: isRu ? "кратко и по делу" : "short and practical",
      placeholder: isRu ? "Например: кратко и по делу" : "For example: short and practical",
    },
    {
      id: "current_project",
      key: "current_project",
      label: isRu ? "Текущий проект" : "Current project",
      description: isRu ? "Про какой проект вы говорите чаще всего" : "What project most of your chats are about",
      example: "HelpGate AI",
      placeholder: isRu ? "Например: HelpGate AI" : "For example: HelpGate AI",
    },
    {
      id: "custom_note",
      key: "custom_note",
      label: isRu ? "Другое важное" : "Other important detail",
      description: isRu ? "Любой устойчивый факт, который стоит помнить" : "Any stable detail worth remembering",
      example: isRu ? "мне удобны ответы с примерами" : "I prefer answers with examples",
      placeholder: isRu ? "Например: мне удобны ответы с примерами" : "For example: I prefer answers with examples",
    },
  ];
  const [selectedTemplate, setSelectedTemplate] = useState(templates[0].id);
  const [memoryKey, setMemoryKey] = useState(templates[0].key);
  const [memoryValue, setMemoryValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const template = templates.find((item) => item.id === selectedTemplate) || templates[0];
  const prettyKey = (key) => String(key || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
  const steps = isRu
    ? [
        "Выберите, что именно нужно запомнить",
        "Заполните одно понятное поле обычными словами",
        "Сохраните, и Helm начнет учитывать это в следующих ответах",
      ]
    : [
        "Choose what should be remembered",
        "Fill one clear field in plain words",
        "Save it, and Helm will use it in future replies",
      ];

  const chooseTemplate = (item, fillExample = false) => {
    setSelectedTemplate(item.id);
    setMemoryKey(item.key);
    if (fillExample) {
      setMemoryValue(item.example);
    }
    setMessage("");
    setError("");
  };

  const saveMemory = async () => {
    const key = memoryKey.trim();
    const value = memoryValue.trim();
    if (!key || !value) return;
    setMessage("");
    setError("");
    try {
      await upsertMemoryFact({ key, value });
      setMemoryValue("");
      setMessage(t("memory_saved"));
    } catch (err) {
      setError(err?.detail || err?.message || "Memory save failed");
    }
  };

  const useCurrentChat = () => {
    const lastUserMessage = [...(activeMessages || [])].reverse().find((item) => item.role === "user" && item.content?.trim());
    const sourceText = lastUserMessage?.content?.trim() || activeChat?.title?.trim() || "";
    if (!sourceText) {
      setMessage("");
      setError(t("memory_chat_empty"));
      return;
    }
    setSelectedTemplate("custom_note");
    setMemoryKey("current_context");
    setMemoryValue(sourceText.replace(/\s+/g, " ").trim().slice(0, 240));
    setError("");
    setMessage(t("memory_chat_saved"));
  };

  return React.createElement("div", { className: "page" },
    React.createElement("div", { className: "page-header" },
      React.createElement("div", null,
        React.createElement("h1", { className: "page-title" }, t("memory_title")),
        React.createElement("p", { className: "page-sub" }, t("memory_subtitle"))
      )
    ),
    React.createElement("div", { className: "profile-wrap", style: { maxWidth: 900 } },
      React.createElement("div", { className: "profile-section" },
        React.createElement("div", { className: "profile-section-title" }, isRu ? "Как это работает" : "How it works"),
        React.createElement("div", {
          style: {
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 10,
            marginBottom: 16,
          },
        },
          steps.map((step, index) => React.createElement("div", {
            key: `${index}-${step}`,
            style: {
              padding: "12px 14px",
              borderRadius: 12,
              border: "1px solid var(--border)",
              background: "var(--surface2)",
            },
          },
            React.createElement("div", {
              style: {
                fontSize: 11,
                fontWeight: 800,
                color: "var(--accent)",
                textTransform: "uppercase",
                letterSpacing: ".05em",
                marginBottom: 6,
              },
            }, `${isRu ? "Шаг" : "Step"} ${index + 1}`),
            React.createElement("div", {
              style: {
                fontSize: 13,
                lineHeight: 1.5,
                color: "var(--text2)",
              },
            }, step)
          ))
        ),
        React.createElement("div", {
          style: {
            padding: "12px 14px",
            borderRadius: 12,
            background: "var(--accent-lt)",
            color: "var(--text2)",
            fontSize: 13,
            lineHeight: 1.55,
          },
        }, isRu
          ? "Сохраняйте только устойчивые вещи: язык, роль, проект, стиль ответов. Не сохраняйте случайные одноразовые фразы."
          : "Save only stable details: language, role, project, response style. Avoid one-off temporary phrases.")
      ),
      React.createElement("div", { className: "profile-section" },
        React.createElement("div", {
          style: {
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
            marginBottom: 12,
          },
        },
          React.createElement("div", { className: "profile-section-title", style: { marginBottom: 0 } }, isRu ? "Выберите тип памяти" : "Choose a memory type"),
          React.createElement("button", { className: "msg-action", onClick: useCurrentChat }, t("memory_use_chat"))
        ),
        React.createElement("div", {
          style: {
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 8,
            marginBottom: 18,
          },
        },
          templates.map((item) => React.createElement("button", {
            key: item.id,
            onClick: () => chooseTemplate(item, false),
            style: {
              textAlign: "left",
              padding: "12px 14px",
              borderRadius: 12,
              border: item.id === selectedTemplate ? "1px solid var(--accent)" : "1px solid var(--border)",
              background: item.id === selectedTemplate ? "var(--accent-lt)" : "var(--surface2)",
              boxShadow: item.id === selectedTemplate ? "0 0 0 1px var(--accent-lt2) inset" : "none",
            },
          },
            React.createElement("div", {
              style: {
                fontSize: 13,
                fontWeight: 800,
                color: item.id === selectedTemplate ? "var(--accent)" : "var(--text)",
                marginBottom: 4,
              },
            }, item.label),
            React.createElement("div", {
              style: {
                fontSize: 12,
                color: "var(--muted)",
                lineHeight: 1.45,
                marginBottom: 6,
              },
            }, item.description),
            React.createElement("div", {
              style: {
                fontSize: 12,
                color: "var(--text2)",
                lineHeight: 1.45,
              },
            }, `${isRu ? "Пример" : "Example"}: ${item.example}`)
          ))
        ),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, isRu ? "Выбранный тип памяти" : "Selected memory type"),
          React.createElement("input", {
            className: "profile-input",
            value: template.label,
            readOnly: true,
          })
        ),
        React.createElement("div", { className: "profile-field" },
          React.createElement("label", null, isRu ? "Что именно сохранить" : "What exactly to save"),
          React.createElement("div", {
            style: {
              fontSize: 12,
              color: "var(--muted)",
              marginBottom: 8,
            },
          }, template.description),
          React.createElement("input", {
            className: "profile-input",
            value: memoryValue,
            onChange: (event) => setMemoryValue(event.target.value),
            placeholder: template.placeholder,
          })
        ),
        React.createElement("div", {
          style: {
            display: "flex",
            gap: 10,
            alignItems: "center",
            flexWrap: "wrap",
            marginTop: 4,
          },
        },
          React.createElement("button", {
            className: "btn-primary",
            onClick: saveMemory,
            style: {
              width: "auto",
              paddingInline: 18,
            },
          }, isRu ? "Сохранить в память" : "Save to memory"),
          React.createElement("button", {
            className: "msg-action",
            onClick: () => chooseTemplate(template, true),
          }, isRu ? "Подставить пример" : "Use example")
        ),
        React.createElement("div", {
          style: {
            fontSize: 12,
            color: "var(--muted)",
            marginTop: 10,
          },
        }, isRu
          ? "Поле ниже должно выглядеть как обычная человеческая фраза, а не как техническая команда."
          : "The value should read like a normal human phrase, not a technical command."),
        message && React.createElement("div", { style: { color: "#10B981", fontSize: 13, marginTop: 14 } }, message),
        error && React.createElement("div", { style: { color: "#EF4444", fontSize: 13, marginTop: 14 } }, error)
      ),
      React.createElement("div", { className: "profile-section" },
        React.createElement("div", { className: "profile-section-title" }, isRu ? "Уже сохранено" : "Already saved"),
        memoryFacts.length === 0
          ? React.createElement("div", {
              style: {
                padding: "14px 16px",
                borderRadius: 10,
                background: "var(--surface2)",
                color: "var(--muted)",
                fontSize: 13,
              },
            }, isRu ? "Память пока пустая. Выберите карточку выше и сохраните первый факт." : "Memory is empty. Choose a card above and save your first fact.")
          : React.createElement("div", {
              style: {
                display: "flex",
                flexDirection: "column",
                gap: 10,
              },
            },
            memoryFacts.map((fact) => React.createElement("div", {
              key: fact.id || fact.key,
              style: {
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: 14,
                background: "var(--surface2)",
              },
            },
              React.createElement("div", {
                style: {
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  alignItems: "flex-start",
                },
              },
                React.createElement("div", { style: { minWidth: 0, flex: 1 } },
                  React.createElement("div", {
                    style: {
                      fontSize: 12,
                      fontWeight: 800,
                      color: "var(--accent)",
                      textTransform: "uppercase",
                      letterSpacing: ".04em",
                      marginBottom: 4,
                    },
                  }, prettyKey(fact.key)),
                  React.createElement("div", {
                    style: {
                      fontSize: 14,
                      color: "var(--text)",
                      lineHeight: 1.55,
                      wordBreak: "break-word",
                    },
                  }, fact.value),
                  React.createElement("div", {
                    style: {
                      fontSize: 11,
                      color: "var(--muted)",
                      marginTop: 8,
                    },
                  }, `${t("memory_updated_at")}: ${new Date(fact.updated_at).toLocaleString()}`)
                ),
                React.createElement("button", {
                  className: "msg-action",
                  onClick: () => deleteMemoryFact(fact.key),
                }, t("delete"))
              )
            ))
          )
      )
    )
  );
}

Object.assign(window, {
  AuthPage,
  FilesPage,
  WorkspacesPage,
  WorkspaceDetail,
  AdminPage,
  MemoryPageTest,
  MemoryPage,
  MemoryPageV2,
  ProfilePage,
});
