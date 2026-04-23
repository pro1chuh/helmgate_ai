const { createContext, useContext, useState, useEffect, useMemo, useRef, useCallback } = React;

const API_ROOT = `${window.location.protocol}//${window.location.hostname}:8000/api`;
const AUTH_STORAGE_KEY = "helm_ai_auth";

const T = {
  ru: {
    app_name: "Helm AI",
    corp_ai: "AI workspace assistant",
    new_chat: "Новый чат",
    chats: "Чаты",
    files: "Файлы и знания",
    workspaces: "Воркспейсы",
    admin: "Админ",
    profile: "Профиль",
    logout: "Выйти",
    today: "Сегодня",
    yesterday: "Вчера",
    prev_week: "Предыдущие 7 дней",
    search: "Поиск...",
    no_chats: "Чатов пока нет",
    start_chatting: "Начните переписку",
    sign_in: "Войти",
    sign_up: "Регистрация",
    email: "Email",
    password: "Пароль",
    full_name: "Имя",
    have_account: "Уже есть аккаунт?",
    no_account: "Нет аккаунта?",
    auth_subtitle: "Войдите, чтобы работать с живым Helm AI backend.",
    placeholder: "Напишите сообщение...",
    attach_file: "Прикрепить файл",
    voice_input: "Голосовой ввод",
    memory: "Память",
    thinking: "Helm готовит ответ...",
    empty_title: "Чем помочь?",
    empty_sub: "Задайте вопрос или выберите быстрый сценарий",
    suggestions: [
      "Сделай краткое резюме этого диалога",
      "Помоги подготовить ответ клиенту",
      "Разбери PDF и выдели ключевые выводы",
      "Собери список следующих шагов по проекту",
    ],
    copy: "Копировать",
    copied: "Скопировано",
    knowledge_base: "База знаний",
    upload_files: "Загрузить",
    drop_files: "Перетащите файлы сюда или нажмите для выбора",
    supported_formats: "PDF, DOCX, TXT, CSV, XLSX, изображения, аудио",
    indexed: "Индексирован",
    indexing: "Индексируется...",
    chunks_label: "фрагментов",
    add_workspace: "Новый воркспейс",
    members_label: "участников",
    open_ws: "Открыть",
    users_label: "Пользователи",
    total_requests: "Запросы",
    active_users: "Активные",
    tokens_used: "Токены",
    cache_hits: "Cache hits",
    role_admin: "Администратор",
    role_user: "Пользователь",
    save: "Сохранить",
    change_password: "Сменить пароль",
    interface_lang: "Язык",
    theme_label: "Тема",
    dark: "Темная",
    light: "Светлая",
    account: "Аккаунт",
    general_settings: "Общее",
    security: "Безопасность",
    memory_title: "Персональная память",
    memory_subtitle: "Что Helm помнит о вас и использует в ответах",
    memory_empty: "Память пока пустая",
    memory_key: "Ключ",
    memory_value: "Значение",
    memory_add: "Добавить факт",
    memory_save: "Сохранить факт",
    memory_saved: "Факт сохранен",
    memory_deleted: "Факт удален",
    memory_updated_at: "Обновлено",
    memory_examples: "Быстрые примеры",
    memory_help: "Можно сохранять роль, проект, стиль общения, предпочтительный язык, формат ответов и другие устойчивые детали.",
    memory_use_chat: "Сохранить из текущего чата",
    memory_chat_empty: "В текущем чате пока нет подходящего текста для сохранения",
    memory_chat_saved: "Черновик заполнен из текущего чата",
    memory_form_hint: "Helm использует эти факты в следующих ответах",
    edit: "Изменить",
    delete: "Удалить",
    search_chat: "Поиск по чату",
    search_chat_hint: "Найдите момент по ключевым словам или смыслу",
    search_placeholder: "Например: найди часть про нейросети",
    best_match: "Лучшее совпадение",
    exact_matches: "Точные совпадения",
    context_matches: "Контекстные совпадения",
    no_results: "Ничего не найдено",
    load_error: "Не удалось загрузить данные",
    profile_saved: "Профиль обновлен",
    password_changed: "Пароль изменен",
    send: "Отправить",
    refresh: "Обновить",
    close: "Закрыть",
    create_workspace: "Создать воркспейс",
    workspace_name: "Название воркспейса",
    workspace_description: "Описание",
    no_workspaces: "Воркспейсов пока нет",
    workspace_members: "Участники",
    workspace_files: "Файлы",
    workspace_settings: "Настройки",
    system_status: "Статус системы",
    live_backend: "Подключено к живому backend",
    current_chat_search: "Поиск идет только по текущему диалогу",
    loading: "Загрузка...",
    delete_chat: "Удалить чат",
    collapse_sidebar: "Свернуть боковую панель",
    expand_sidebar: "Развернуть боковую панель",
  },
  en: {
    app_name: "Helm AI",
    corp_ai: "AI workspace assistant",
    new_chat: "New chat",
    chats: "Chats",
    files: "Files & knowledge",
    workspaces: "Workspaces",
    admin: "Admin",
    profile: "Profile",
    logout: "Log out",
    today: "Today",
    yesterday: "Yesterday",
    prev_week: "Previous 7 days",
    search: "Search...",
    no_chats: "No chats yet",
    start_chatting: "Start chatting",
    sign_in: "Sign in",
    sign_up: "Register",
    email: "Email",
    password: "Password",
    full_name: "Name",
    have_account: "Already have an account?",
    no_account: "No account yet?",
    auth_subtitle: "Sign in to work with the live Helm AI backend.",
    placeholder: "Write a message...",
    attach_file: "Attach file",
    voice_input: "Voice input",
    memory: "Memory",
    thinking: "Helm is preparing a reply...",
    empty_title: "How can I help?",
    empty_sub: "Ask something or choose a quick prompt",
    suggestions: [
      "Summarize this conversation",
      "Help me draft a client reply",
      "Analyze a PDF and extract key points",
      "List next steps for the project",
    ],
    copy: "Copy",
    copied: "Copied",
    knowledge_base: "Knowledge base",
    upload_files: "Upload",
    drop_files: "Drop files here or click to browse",
    supported_formats: "PDF, DOCX, TXT, CSV, XLSX, images, audio",
    indexed: "Indexed",
    indexing: "Indexing...",
    chunks_label: "chunks",
    add_workspace: "New workspace",
    members_label: "members",
    open_ws: "Open",
    users_label: "Users",
    total_requests: "Requests",
    active_users: "Active users",
    tokens_used: "Tokens",
    cache_hits: "Cache hits",
    role_admin: "Administrator",
    role_user: "User",
    save: "Save",
    change_password: "Change password",
    interface_lang: "Language",
    theme_label: "Theme",
    dark: "Dark",
    light: "Light",
    account: "Account",
    general_settings: "General",
    security: "Security",
    memory_title: "Personal memory",
    memory_subtitle: "What Helm remembers about you and uses in answers",
    memory_empty: "Memory is empty",
    memory_key: "Key",
    memory_value: "Value",
    memory_add: "Add fact",
    memory_save: "Save fact",
    memory_saved: "Fact saved",
    memory_deleted: "Fact deleted",
    memory_updated_at: "Updated",
    memory_examples: "Quick examples",
    memory_help: "You can save your role, project, tone, preferred language, answer format, and other stable details.",
    memory_use_chat: "Save from current chat",
    memory_chat_empty: "There is no suitable text in the current chat yet",
    memory_chat_saved: "Draft filled from the current chat",
    memory_form_hint: "Helm uses these facts in future answers",
    edit: "Edit",
    delete: "Delete",
    search_chat: "Search chat",
    search_chat_hint: "Find a moment by keyword or context",
    search_placeholder: "Example: find the part about neural networks",
    best_match: "Best match",
    exact_matches: "Exact matches",
    context_matches: "Context matches",
    no_results: "No results found",
    load_error: "Failed to load data",
    profile_saved: "Profile updated",
    password_changed: "Password changed",
    send: "Send",
    refresh: "Refresh",
    close: "Close",
    create_workspace: "Create workspace",
    workspace_name: "Workspace name",
    workspace_description: "Description",
    no_workspaces: "No workspaces yet",
    workspace_members: "Members",
    workspace_files: "Files",
    workspace_settings: "Settings",
    system_status: "System status",
    live_backend: "Connected to the live backend",
    current_chat_search: "Search only works within the current dialog",
    loading: "Loading...",
    delete_chat: "Delete chat",
    collapse_sidebar: "Collapse sidebar",
    expand_sidebar: "Expand sidebar",
  },
};

const ThemeCtx = createContext(null);
const LangCtx = createContext(null);
const AppCtx = createContext(null);

function readStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function writeStoredAuth(payload) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(payload));
}

function clearStoredAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

function formatError(error, fallback) {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error.detail) return error.detail;
  return fallback;
}

async function apiFetch(path, options = {}, tokenOverride) {
  const stored = readStoredAuth();
  const headers = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };
  const token = tokenOverride || stored?.access_token;
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch (_) {
    payload = text;
  }

  if (!response.ok) {
    throw payload || { detail: `HTTP ${response.status}` };
  }

  return payload;
}

function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem("helm_theme") || "light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("helm_theme", theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((value) => (value === "light" ? "dark" : "light"));
  }, []);

  return React.createElement(ThemeCtx.Provider, { value: { theme, toggle, setTheme } }, children);
}

function LangProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem("helm_lang") || "ru");
  const t = useCallback((key) => T[lang][key] ?? key, [lang]);

  const switchLang = useCallback((nextLang) => {
    setLang(nextLang);
    localStorage.setItem("helm_lang", nextLang);
  }, []);

  return React.createElement(
    LangCtx.Provider,
    { value: { lang, t, switchLang, T: T[lang] } },
    children
  );
}

function ThemeStatus({ text, tone }) {
  return {
    text,
    tone,
  };
}

function AppProvider({ children }) {
  const storedAuth = readStoredAuth();
  const [auth, setAuth] = useState(storedAuth);
  const [authed, setAuthed] = useState(Boolean(storedAuth?.access_token));
  const [authLoading, setAuthLoading] = useState(Boolean(storedAuth?.access_token));
  const [page, setPage] = useState("chat");
  const [pageKey, setPageKey] = useState(0);
  const [user, setUser] = useState(null);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [messagesByChat, setMessagesByChat] = useState({});
  const [thinking, setThinking] = useState(false);
  const [files, setFiles] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [workspaceMembers, setWorkspaceMembers] = useState({});
  const [stats, setStats] = useState({
    total_requests: 0,
    active_users: 0,
    tokens_used: "0",
    cache_hits: "0%",
  });
  const [sidebarStyle, setSidebarStyle] = useState(() => localStorage.getItem("helm_sidebar") || "standard");
  const [memoryFacts, setMemoryFacts] = useState([]);
  const [wsDetailId, setWsDetailId] = useState(null);
  const [userDetailId, setUserDetailId] = useState(null);
  const [statusNotice, setStatusNotice] = useState(null);
  const chatLoadRef = useRef(new Set());

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) || null,
    [chats, activeChatId]
  );
  const activeMessages = messagesByChat[activeChatId] || [];

  const setSession = useCallback((payload) => {
    setAuth(payload);
    setAuthed(Boolean(payload?.access_token));
    if (payload?.access_token) {
      writeStoredAuth(payload);
    } else {
      clearStoredAuth();
    }
  }, []);

  const navigate = useCallback((nextPage, opts = {}) => {
    setPage(nextPage);
    setPageKey((value) => value + 1);
    if (Object.prototype.hasOwnProperty.call(opts, "wsId")) setWsDetailId(opts.wsId);
    if (Object.prototype.hasOwnProperty.call(opts, "userId")) setUserDetailId(opts.userId);
  }, []);

  const normalizeChat = useCallback((chat) => ({
    ...chat,
    createdAt: chat.created_at || chat.createdAt || new Date().toISOString(),
    updatedAt: chat.updated_at || chat.updatedAt || new Date().toISOString(),
  }), []);

  const normalizeMessage = useCallback((message) => ({
    id: message.id,
    role: message.role,
    content: message.content || "",
    model: message.model_used || message.model || null,
    taskType: message.task_type || message.taskType || "text",
    ts: message.created_at || message.ts || new Date().toISOString(),
  }), []);

  const loadProfile = useCallback(async (tokenOverride) => {
    const profile = await apiFetch("/profile", {}, tokenOverride);
    setUser(profile);
    return profile;
  }, []);

  const loadChats = useCallback(async (tokenOverride) => {
    const payload = await apiFetch("/chats?page=1&limit=50", {}, tokenOverride);
    const items = (payload?.items || []).map(normalizeChat);
    setChats(items);
    setStats((prev) => ({
      ...prev,
      total_requests: items.length,
    }));
    if (!activeChatId && items.length > 0) {
      setActiveChatId(items[0].id);
    }
    return items;
  }, [activeChatId, normalizeChat]);

  const loadFiles = useCallback(async (tokenOverride) => {
    const payload = await apiFetch("/files", {}, tokenOverride);
    setFiles(payload || []);
    return payload || [];
  }, []);

  const loadWorkspaces = useCallback(async (tokenOverride) => {
    const payload = await apiFetch("/workspaces", {}, tokenOverride);
    setWorkspaces(payload || []);
    setStats((prev) => ({
      ...prev,
      active_users: payload?.length || 0,
      cache_hits: payload?.length ? "live" : "0%",
    }));
    return payload || [];
  }, []);

  const loadMemoryFacts = useCallback(async (tokenOverride) => {
    const payload = await apiFetch("/memory", {}, tokenOverride);
    setMemoryFacts(payload || []);
    return payload || [];
  }, []);

  const bootstrap = useCallback(async (tokenOverride) => {
    setAuthLoading(true);
    try {
      await Promise.all([
        loadProfile(tokenOverride),
        loadChats(tokenOverride),
        loadFiles(tokenOverride),
        loadWorkspaces(tokenOverride),
        loadMemoryFacts(tokenOverride),
      ]);
      setStatusNotice(ThemeStatus("Connected to backend", "success"));
    } catch (error) {
      setSession(null);
      setUser(null);
      setChats([]);
      setFiles([]);
      setWorkspaces([]);
      setMessagesByChat({});
      setStatusNotice(ThemeStatus(formatError(error, "Auth session expired"), "error"));
    } finally {
      setAuthLoading(false);
    }
  }, [loadChats, loadFiles, loadProfile, loadWorkspaces, loadMemoryFacts, setSession]);

  useEffect(() => {
    if (auth?.access_token) {
      bootstrap(auth.access_token);
    }
  }, []);

  const loadMessages = useCallback(async (chatId, force = false) => {
    if (!chatId) return [];
    if (!force && chatLoadRef.current.has(chatId) && messagesByChat[chatId]) {
      return messagesByChat[chatId];
    }
    const payload = await apiFetch(`/chats/${chatId}/messages?page=1&limit=100`);
    const items = (payload?.items || []).map(normalizeMessage);
    setMessagesByChat((prev) => ({ ...prev, [chatId]: items }));
    chatLoadRef.current.add(chatId);
    return items;
  }, [messagesByChat, normalizeMessage]);

  useEffect(() => {
    if (authed && activeChatId) {
      loadMessages(activeChatId).catch(() => {});
    }
  }, [authed, activeChatId, loadMessages]);

  const login = useCallback(async ({ email, password }) => {
    const payload = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setSession(payload);
    await bootstrap(payload.access_token);
    return payload;
  }, [bootstrap, setSession]);

  const register = useCallback(async ({ name, email, password }) => {
    const payload = await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    setSession(payload);
    await bootstrap(payload.access_token);
    return payload;
  }, [bootstrap, setSession]);

  const logout = useCallback(async () => {
    try {
      if (auth?.refresh_token) {
        await apiFetch("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: auth.refresh_token }),
        });
      }
    } catch (_) {
      // Ignore logout network errors and still clear local session.
    }

    setSession(null);
    setUser(null);
    setChats([]);
    setActiveChatId(null);
    setMessagesByChat({});
    setFiles([]);
    setWorkspaces([]);
    setPage("chat");
  }, [auth, setSession]);

  const createChat = useCallback(async () => {
    const payload = await apiFetch("/chats", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const nextChat = normalizeChat(payload);
    setChats((prev) => [nextChat, ...prev]);
    setActiveChatId(nextChat.id);
    setMessagesByChat((prev) => ({ ...prev, [nextChat.id]: [] }));
    setPage("chat");
    return nextChat;
  }, [normalizeChat]);

  const newChat = useCallback(async () => {
    return createChat();
  }, [createChat]);

  const selectChat = useCallback((chatId) => {
    setActiveChatId(chatId);
    setPage("chat");
  }, []);

  const updateChatInList = useCallback((chatId, updater) => {
    setChats((prev) => prev.map((chat) => {
      if (chat.id !== chatId) return chat;
      const update = typeof updater === "function" ? updater(chat) : updater;
      return { ...chat, ...update, updatedAt: new Date().toISOString() };
    }));
  }, []);

  const appendMessage = useCallback((chatId, message) => {
    setMessagesByChat((prev) => ({
      ...prev,
      [chatId]: [...(prev[chatId] || []), normalizeMessage(message)],
    }));
  }, [normalizeMessage]);

  const patchMessage = useCallback((chatId, messageId, updater) => {
    setMessagesByChat((prev) => ({
      ...prev,
      [chatId]: (prev[chatId] || []).map((message) => {
        if (message.id !== messageId) return message;
        const next = typeof updater === "function" ? updater(message) : updater;
        return { ...message, ...next };
      }),
    }));
  }, []);

  const sendMessage = useCallback(async ({ content, fileId = null, manualModel = null }) => {
    let chatId = activeChatId;
    if (!chatId) {
      const created = await createChat();
      chatId = created.id;
    }

    const userMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    appendMessage(chatId, userMessage);
    chatLoadRef.current.add(chatId);

    updateChatInList(chatId, (chat) => ({
      title: chat.title === "Новый чат" || chat.title === "New chat"
        ? content.slice(0, 44) + (content.length > 44 ? "..." : "")
        : chat.title,
    }));

    const assistantId = `local-assistant-${Date.now()}`;
    appendMessage(chatId, {
      id: assistantId,
      role: "assistant",
      content: "",
      model: null,
      taskType: "text",
      created_at: new Date().toISOString(),
    });

    setThinking(true);

    try {
      const response = await fetch(`${API_ROOT}/chats/${chatId}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${readStoredAuth()?.access_token}`,
        },
        body: JSON.stringify({
          content,
          file_id: fileId,
          manual_model: manualModel,
        }),
      });

      if (!response.ok || !response.body) {
        const payload = await response.text();
        throw payload || { detail: `HTTP ${response.status}` };
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";

        chunks.forEach((chunk) => {
          const line = chunk
            .split("\n")
            .find((entry) => entry.startsWith("data: "));
          if (!line) return;

          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.type === "meta") {
              patchMessage(chatId, assistantId, {
                model: payload.model || null,
                taskType: payload.task_type || "text",
              });
            } else if (payload.type === "token") {
              patchMessage(chatId, assistantId, (message) => ({
                content: `${message.content}${payload.content || ""}`,
              }));
            } else if (payload.type === "image" && payload.url) {
              patchMessage(chatId, assistantId, (message) => ({
                content: `${message.content}\n\n![generated image](${payload.url})`,
              }));
            } else if (payload.type === "error") {
              patchMessage(chatId, assistantId, (message) => ({
                content: `${message.content}\n\n${payload.detail || "Unexpected error"}`,
              }));
            }
          } catch (_) {
            // Ignore malformed SSE chunks.
          }
        });
      }
    } catch (error) {
      patchMessage(chatId, assistantId, {
        content: formatError(error, "Не удалось получить ответ от модели."),
      });
    } finally {
      setThinking(false);
      updateChatInList(chatId, {});
    }
  }, [activeChatId, appendMessage, createChat, patchMessage, updateChatInList]);

  const refreshChat = useCallback(async (chatId) => {
    await loadMessages(chatId, true);
  }, [loadMessages]);

  const deleteChat = useCallback(async (chatId) => {
    await apiFetch(`/chats/${chatId}`, { method: "DELETE" });
    const remainingChats = chats.filter((chat) => chat.id !== chatId);
    setChats(remainingChats);
    setMessagesByChat((prev) => {
      const next = { ...prev };
      delete next[chatId];
      return next;
    });
    if (activeChatId === chatId) {
      setActiveChatId(remainingChats.length ? remainingChats[0].id : null);
    }
  }, [activeChatId, chats]);

  const uploadFiles = useCallback(async (selectedFiles) => {
    const uploaded = [];
    for (const file of selectedFiles) {
      const formData = new FormData();
      formData.append("file", file);
      const payload = await apiFetch("/files", {
        method: "POST",
        body: formData,
        headers: {},
      });
      uploaded.push(payload);
    }
    await loadFiles();
    return uploaded;
  }, [loadFiles]);

  const deleteFile = useCallback(async (fileId) => {
    await apiFetch(`/files/${fileId}`, { method: "DELETE" });
    setFiles((prev) => prev.filter((file) => file.id !== fileId));
  }, []);

  const createWorkspace = useCallback(async ({ name, description }) => {
    const payload = await apiFetch("/workspaces", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
    setWorkspaces((prev) => [payload, ...prev]);
    return payload;
  }, []);

  const loadWorkspaceMembers = useCallback(async (workspaceId) => {
    const payload = await apiFetch(`/workspaces/${workspaceId}/members`);
    setWorkspaceMembers((prev) => ({ ...prev, [workspaceId]: payload || [] }));
    return payload || [];
  }, []);

  const updateProfile = useCallback(async ({ name }) => {
    const payload = await apiFetch("/profile", {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    setUser(payload);
    return payload;
  }, []);

  const changePassword = useCallback(async ({ current_password, new_password }) => {
    await apiFetch("/profile/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    });
  }, []);

  const upsertMemoryFact = useCallback(async ({ key, value }) => {
    const payload = await apiFetch(`/memory/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    });
    setMemoryFacts((prev) => {
      const exists = prev.some((fact) => fact.key === payload.key);
      const next = exists
        ? prev.map((fact) => fact.key === payload.key ? payload : fact)
        : [...prev, payload];
      return next.sort((a, b) => a.key.localeCompare(b.key));
    });
    return payload;
  }, []);

  const deleteMemoryFact = useCallback(async (key) => {
    await apiFetch(`/memory/${encodeURIComponent(key)}`, { method: "DELETE" });
    setMemoryFacts((prev) => prev.filter((fact) => fact.key !== key));
  }, []);

  const changeSidebarStyle = useCallback((style) => {
    setSidebarStyle(style);
    localStorage.setItem("helm_sidebar", style);
  }, []);

  return React.createElement(
    AppCtx.Provider,
    {
      value: {
        API_ROOT,
        authed,
        authLoading,
        user,
        auth,
        login,
        register,
        logout,
        page,
        setPage,
        pageKey,
        navigate,
        chats,
        activeChatId,
        activeChat,
        activeMessages,
        messagesByChat,
        newChat,
        selectChat,
        loadMessages,
        refreshChat,
        sendMessage,
        deleteChat,
        files,
        uploadFiles,
        deleteFile,
        workspaces,
        createWorkspace,
        workspaceMembers,
        loadWorkspaceMembers,
        thinking,
        setThinking,
        sidebarStyle,
        changeSidebarStyle,
        wsDetailId,
        setWsDetailId,
        userDetailId,
        setUserDetailId,
        stats,
        userStats: [],
        updateProfile,
        changePassword,
        memoryFacts,
        loadMemoryFacts,
        upsertMemoryFact,
        deleteMemoryFact,
        statusNotice,
        setStatusNotice,
      },
    },
    children
  );
}

const useTheme = () => useContext(ThemeCtx);
const useLang = () => useContext(LangCtx);
const useApp = () => useContext(AppCtx);

Object.assign(window, {
  API_ROOT,
  T,
  ThemeCtx,
  LangCtx,
  AppCtx,
  ThemeProvider,
  LangProvider,
  AppProvider,
  useTheme,
  useLang,
  useApp,
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback,
});
