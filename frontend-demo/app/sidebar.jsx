function Sidebar() {
  const { theme, toggle: toggleTheme } = useTheme();
  const { lang, t, switchLang } = useLang();
  const { page, setPage, chats, activeChatId, newChat, selectChat, deleteChat, updateChatTag, updateChatArchive, sidebarStyle, changeSidebarStyle, user } = useApp();
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("all");
  const [archiveView, setArchiveView] = useState("active");

  const tagOptions = getChatTagOptions(t);

  const now = new Date();
  const isToday = (value) => new Date(value).toDateString() === now.toDateString();
  const isYesterday = (value) => {
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    return new Date(value).toDateString() === yesterday.toDateString();
  };
  const matches = (chat) => {
    const searchMatch = !search || (chat.title || "").toLowerCase().includes(search.toLowerCase());
    const tagMatch = tagFilter === "all" || (tagFilter === "none" ? !chat.tag : chat.tag === tagFilter);
    const archiveMatch = archiveView === "archived" ? chat.archived : !chat.archived;
    return searchMatch && tagMatch && archiveMatch;
  };

  const todayChats = chats.filter((chat) => isToday(chat.createdAt) && matches(chat));
  const yesterdayChats = chats.filter((chat) => isYesterday(chat.createdAt) && matches(chat));
  const olderChats = chats.filter((chat) => !isToday(chat.createdAt) && !isYesterday(chat.createdAt) && matches(chat));

  if (sidebarStyle === "rail") {
    return React.createElement(RailSidebar, {
      t,
      theme,
      toggleTheme,
      lang,
      switchLang,
      page,
      setPage,
      newChat,
      selectChat,
      deleteChat,
      updateChatTag,
      updateChatArchive,
      activeChatId,
      chats,
      user,
      changeSidebarStyle,
    });
  }

  return React.createElement("aside", { className: "sidebar" },
    React.createElement("div", { className: "sb-header" },
      React.createElement("button", {
        className: "sb-logo",
        onClick: () => window.location.reload(),
        title: "Reload",
        style: { background: "none", border: "none", textAlign: "left" },
      },
        React.createElement("div", { className: "sb-logo-mark" }, "H"),
        React.createElement("span", { className: "sb-logo-text" }, t("app_name"))
      ),
      React.createElement("button", {
        className: "sb-icon-btn",
        onClick: () => changeSidebarStyle("rail"),
        title: t("collapse_sidebar"),
      }, React.createElement(IconChevron, { dir: "left", size: 16 })),
      React.createElement("button", {
        className: "sb-icon-btn",
        onClick: () => newChat(),
        title: t("new_chat"),
      }, React.createElement(IconPlus))
    ),
    React.createElement("div", { className: "sb-search-wrap" },
      React.createElement("span", { className: "sb-search-ico" }, React.createElement(IconSearch)),
      React.createElement("input", {
        className: "sb-search",
        value: search,
        onChange: (event) => setSearch(event.target.value),
        placeholder: t("search"),
      })
    ),
    React.createElement("div", { className: "sb-tag-filter" },
      React.createElement("button", {
        className: `sb-tag-chip sb-tag-chip--archive ${archiveView === "active" ? "active" : ""}`,
        onClick: () => setArchiveView("active"),
      }, t("active_chats")),
      React.createElement("button", {
        className: `sb-tag-chip sb-tag-chip--archive ${archiveView === "archived" ? "active" : ""}`,
        onClick: () => setArchiveView("archived"),
      }, t("archived_chats")),
      React.createElement("button", {
        className: `sb-tag-chip ${tagFilter === "all" ? "active" : ""}`,
        onClick: () => setTagFilter("all"),
      }, t("all_chats")),
      tagOptions.map((tag) => React.createElement("button", {
        key: tag.id,
        className: `sb-tag-chip sb-tag-chip--${tag.id} ${tagFilter === tag.id ? "active" : ""}`,
        onClick: () => setTagFilter(tag.id),
      }, tag.label)),
      React.createElement("button", {
        className: `sb-tag-chip ${tagFilter === "none" ? "active" : ""}`,
        onClick: () => setTagFilter("none"),
      }, t("chat_tag_none"))
    ),
    React.createElement("div", { className: "sb-scroll" },
      todayChats.length > 0 && React.createElement(ChatSection, {
        label: t("today"),
        chats: todayChats,
        activeChatId,
        selectChat,
        deleteChat,
        updateChatTag,
        updateChatArchive,
        deleteTitle: t("delete_chat"),
        archiveTitle: t("archive_chat"),
        restoreTitle: t("restore_chat"),
      }),
      yesterdayChats.length > 0 && React.createElement(ChatSection, {
        label: t("yesterday"),
        chats: yesterdayChats,
        activeChatId,
        selectChat,
        deleteChat,
        updateChatTag,
        updateChatArchive,
        deleteTitle: t("delete_chat"),
        archiveTitle: t("archive_chat"),
        restoreTitle: t("restore_chat"),
      }),
      olderChats.length > 0 && React.createElement(ChatSection, {
        label: t("prev_week"),
        chats: olderChats,
        activeChatId,
        selectChat,
        deleteChat,
        updateChatTag,
        updateChatArchive,
        deleteTitle: t("delete_chat"),
        archiveTitle: t("archive_chat"),
        restoreTitle: t("restore_chat"),
      }),
      !todayChats.length && !yesterdayChats.length && !olderChats.length && React.createElement("div", {
        className: "sb-empty",
      },
        React.createElement("div", { className: "sb-empty-icon" }, React.createElement(IconChat)),
        React.createElement("p", null, t("no_chats"))
      )
    ),
    React.createElement("div", { className: "sb-bottom" },
      React.createElement("nav", { className: "sb-nav" },
        React.createElement("button", {
          className: `sb-nav-btn ${page === "chat" ? "active" : ""}`,
          onClick: () => setPage("chat"),
        }, React.createElement(IconChat), React.createElement("span", null, t("chats"))),
        React.createElement("button", {
          className: `sb-nav-btn ${page === "files" ? "active" : ""}`,
          onClick: () => setPage("files"),
        }, React.createElement(IconFile), React.createElement("span", null, t("files"))),
        React.createElement("button", {
          className: `sb-nav-btn ${page === "workspaces" ? "active" : ""}`,
          onClick: () => setPage("workspaces"),
        }, React.createElement(IconFolder), React.createElement("span", null, t("workspaces"))),
        React.createElement("button", {
          className: `sb-nav-btn ${page === "memory" ? "active" : ""}`,
          onClick: () => setPage("memory"),
        }, React.createElement(IconBrain), React.createElement("span", null, t("memory_title"))),
        user?.role === "admin" && React.createElement("button", {
          className: `sb-nav-btn ${page === "admin" ? "active" : ""}`,
          onClick: () => setPage("admin"),
        }, React.createElement(IconShield), React.createElement("span", null, t("admin")))
      ),
      React.createElement("div", { className: "sb-user-row" },
        React.createElement("button", {
          className: "sb-user-btn",
          onClick: () => setPage("profile"),
        },
          React.createElement(Avatar, { name: user?.name || "H", size: 30 }),
          React.createElement("div", { className: "sb-user-info" },
            React.createElement("div", { className: "sb-user-name" }, user?.name || t("loading")),
            React.createElement("div", { className: "sb-user-email" }, user?.email || "")
          )
        ),
        React.createElement("div", { className: "sb-actions" },
          React.createElement("button", {
            className: "sb-icon-btn",
            onClick: toggleTheme,
            title: t("theme_label"),
          }, theme === "dark" ? React.createElement(IconSun) : React.createElement(IconMoon)),
          React.createElement("button", {
            className: "sb-icon-btn sb-lang",
            onClick: () => switchLang(lang === "ru" ? "en" : "ru"),
            title: t("interface_lang"),
          }, lang === "ru" ? "EN" : "RU")
        )
      )
    )
  );
}

function getChatTagOptions(t) {
  return [
    { id: "project", label: t("chat_tag_project") },
    { id: "docs", label: t("chat_tag_docs") },
    { id: "clients", label: t("chat_tag_clients") },
    { id: "ideas", label: t("chat_tag_ideas") },
  ];
}

function nextChatTag(currentTag) {
  const order = [null, "project", "docs", "clients", "ideas"];
  const index = order.indexOf(currentTag || null);
  return order[(index + 1) % order.length];
}

function ChatSection({ label, chats, activeChatId, selectChat, deleteChat, updateChatTag, updateChatArchive, deleteTitle, archiveTitle, restoreTitle }) {
  const { t } = useLang();
  return React.createElement(React.Fragment, null,
    React.createElement("div", { className: "sb-section-label" }, label),
    chats.map((chat) => React.createElement(ChatItem, {
      key: chat.id,
      chat,
      active: chat.id === activeChatId,
      onClick: () => selectChat(chat.id),
      onDelete: () => deleteChat(chat.id),
      onCycleTag: () => updateChatTag(chat.id, nextChatTag(chat.tag)),
      onToggleArchive: () => updateChatArchive(chat.id, !chat.archived),
      tagOptions: getChatTagOptions(t),
      deleteTitle,
      archiveTitle,
      restoreTitle,
    }))
  );
}

function ChatItem({ chat, active, onClick, onDelete, onCycleTag, onToggleArchive, tagOptions, deleteTitle, archiveTitle, restoreTitle }) {
  const [hovered, setHovered] = useState(false);
  const { t } = useLang();
  const tag = tagOptions.find((item) => item.id === chat.tag);

  return React.createElement("div", {
    className: `sb-chat-item ${active ? "active" : ""}`,
    onMouseEnter: () => setHovered(true),
    onMouseLeave: () => setHovered(false),
  },
    React.createElement("button", {
      onClick,
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        flex: 1,
        minWidth: 0,
        color: "inherit",
      },
    },
      React.createElement("span", { className: "sb-chat-ico" }, React.createElement(IconChat)),
      React.createElement("span", { className: "sb-chat-title" }, chat.title)
    ),
    (hovered || active || tag) && React.createElement("div", { className: "sb-chat-actions" },
      React.createElement("button", {
        className: `sb-tag-dot ${tag ? `sb-tag-dot--${tag.id}` : ""}`,
        onClick: (event) => {
          event.stopPropagation();
          onCycleTag();
        },
        title: `${t("chat_tag_set")}: ${tag?.label || t("chat_tag_none")}`,
      }, tag ? tag.label.charAt(0).toUpperCase() : "+"),
      (hovered || active) && React.createElement("button", {
        className: "sb-icon-btn sb-chat-action-btn",
        onClick: (event) => {
          event.stopPropagation();
          onToggleArchive();
        },
        title: chat.archived ? restoreTitle : archiveTitle,
      }, React.createElement(IconArchive, { width: 13, height: 13 })),
      (hovered || active) && React.createElement("button", {
        className: "sb-icon-btn sb-chat-action-btn",
        onClick: (event) => {
          event.stopPropagation();
          onDelete();
        },
        title: deleteTitle,
      }, React.createElement(IconTrash, { width: 13, height: 13 }))
    )
  );
}

function RailSidebar({ t, theme, toggleTheme, lang, switchLang, page, setPage, newChat, selectChat, deleteChat, activeChatId, chats, user, changeSidebarStyle }) {
  const activeChats = chats.filter((chat) => !chat.archived);
  return React.createElement("aside", { className: "sidebar sidebar--rail" },
    React.createElement("div", { className: "rail-top" },
      React.createElement("button", {
        className: "sb-logo-mark",
        style: { margin: "0 auto 4px", border: "none" },
        onClick: () => window.location.reload(),
        title: "Reload",
      }, "H"),
      React.createElement("button", {
        className: "rail-btn",
        onClick: () => changeSidebarStyle("standard"),
        title: t("expand_sidebar"),
      }, React.createElement(IconChevron, { dir: "right", size: 16 })),
      React.createElement("button", { className: "rail-btn", onClick: () => newChat(), title: t("new_chat") }, React.createElement(IconPlus)),
      React.createElement("div", { className: "rail-divider" }),
      activeChats.slice(0, 6).map((chat) => React.createElement("button", {
        key: chat.id,
        className: `rail-btn ${chat.id === activeChatId && page === "chat" ? "active" : ""}`,
        onClick: () => selectChat(chat.id),
        title: chat.title,
      }, String(chat.title || "C").charAt(0).toUpperCase())),
      activeChatId && React.createElement("button", {
        className: "rail-btn",
        onClick: () => deleteChat(activeChatId),
        title: t("delete_chat"),
      }, React.createElement(IconTrash))
    ),
    React.createElement("div", { className: "rail-bottom" },
      React.createElement("button", { className: `rail-btn ${page === "files" ? "active" : ""}`, onClick: () => setPage("files"), title: t("files") }, React.createElement(IconFile)),
      React.createElement("button", { className: `rail-btn ${page === "workspaces" ? "active" : ""}`, onClick: () => setPage("workspaces"), title: t("workspaces") }, React.createElement(IconFolder)),
      React.createElement("button", { className: `rail-btn ${page === "memory" ? "active" : ""}`, onClick: () => setPage("memory"), title: t("memory_title") }, React.createElement(IconBrain)),
      user?.role === "admin" && React.createElement("button", { className: `rail-btn ${page === "admin" ? "active" : ""}`, onClick: () => setPage("admin"), title: t("admin") }, React.createElement(IconShield)),
      React.createElement("div", { className: "rail-divider" }),
      React.createElement("button", { className: "rail-btn", onClick: toggleTheme, title: t("theme_label") }, theme === "dark" ? React.createElement(IconSun) : React.createElement(IconMoon)),
      React.createElement("button", { className: "rail-btn", onClick: () => switchLang(lang === "ru" ? "en" : "ru"), title: t("interface_lang") }, lang === "ru" ? "EN" : "RU"),
      React.createElement("button", { className: "rail-btn", onClick: () => setPage("profile"), title: t("profile") }, React.createElement(Avatar, { name: user?.name || "H", size: 26 }))
    )
  );
}

Object.assign(window, { Sidebar });
