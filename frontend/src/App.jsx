/*
 * Root application layout and provider wiring for the chat frontend.
 *
 * This file composes the authenticated app shell, routes user interactions
 * between sidebar and chat area, and wraps everything in the shared chat state
 * provider so components can coordinate room, message, and user state.
 */
import { useCallback, useEffect, useState } from "react";
import { ChatProvider, useChat } from "./context/ChatContext";
import LoginScreen from "./components/LoginScreen";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import KickedBanner from "./components/KickedBanner";
import ConfirmDialog from "./components/ConfirmDialog";
import DbHealthPoller from "./components/DbHealthPoller";
import "./App.css";

function AppInner() {
  /* Selects a room and records the current user's role for chat permissions. */
  const { state, dispatch } = useChat();
  const [theme, setTheme] = useState(() => localStorage.getItem("chat-theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("chat-theme", theme);
  }, [theme]);

  const handleEnterRoom = useCallback(
    (room, role) => {
      dispatch({
        type: "SET_ACTIVE_ROOM",
        payload: { id: room.id, name: room.name, role, room_type: room.room_type },
      });
    },
    [dispatch]
  );

  if (!state.user) {
    return <LoginScreen />;
  }

  const layoutClass =
    state.activeRoom != null ? "app-layout chat-open" : "app-layout";

  return (
    <div className={layoutClass}>
      <ConfirmDialog />
      <Sidebar
        onEnterRoom={handleEnterRoom}
        theme={theme}
        onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
      />
      <ChatArea />
    </div>
  );
}

export default function App() {
  /* Provides global chat context and renders the main app content tree. */
  return (
    <ChatProvider>
      <KickedBanner />
      <DbHealthPoller />
      <AppInner />
    </ChatProvider>
  );
}
