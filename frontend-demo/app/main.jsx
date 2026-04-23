function App() {
  const { t } = useLang();
  const { authed, authLoading } = useApp();

  if (authLoading) {
    return React.createElement(LoadingScreen, { label: t("loading") });
  }

  if (!authed) {
    return React.createElement(AuthPage);
  }

  return React.createElement("div", { className: "app-shell" },
    React.createElement(Sidebar),
    React.createElement(MainContent)
  );
}

function LoadingScreen({ label }) {
  return React.createElement("div", { className: "loading-screen" },
    React.createElement("div", { className: "loading-orb loading-orb--left" }),
    React.createElement("div", { className: "loading-orb loading-orb--right" }),
    React.createElement("div", { className: "loading-card" },
      React.createElement("div", { className: "loading-logo-wrap" },
        React.createElement("div", { className: "loading-logo-pulse" }),
        React.createElement("div", { className: "loading-logo" }, "H")
      ),
      React.createElement("div", { className: "loading-brand" }, "Helm AI"),
      React.createElement("div", { className: "loading-label" }, label),
      React.createElement("div", { className: "loading-dots" },
        React.createElement("span", null),
        React.createElement("span", null),
        React.createElement("span", null)
      )
    )
  );
}

function MainContent() {
  const { page, pageKey, wsDetailId } = useApp();

  return React.createElement("main", { className: "app-main" },
    React.createElement("div", { className: "page-anim", key: `${page}-${pageKey}` },
      page === "chat" && React.createElement(ChatView),
      page === "files" && React.createElement(FilesPage),
      page === "workspaces" && (wsDetailId ? React.createElement(WorkspaceDetail) : React.createElement(WorkspacesPage)),
      page === "memory" && React.createElement(MemoryPageV2),
      page === "ws-detail" && React.createElement(WorkspaceDetail),
      page === "admin" && React.createElement(AdminPage),
      page === "profile" && React.createElement(ProfilePage)
    )
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  React.createElement(ThemeProvider, null,
    React.createElement(LangProvider, null,
      React.createElement(AppProvider, null,
        React.createElement(App)
      )
    )
  )
);
