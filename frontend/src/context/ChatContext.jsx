/*
 * Shared React context and reducer for application-wide chat state.
 *
 * This file centralizes user session persistence, JWT token storage, room selection,
 * message timeline updates, typing indicators, reply state, and online-user presence
 * so all chat UI components can read and dispatch consistent state changes.
 */
import { createContext, useContext, useReducer } from "react";

const ChatContext = createContext(null);

function loadStoredState() {
  /* Restores the last signed-in user and JWT token from localStorage when available. */
  try {
    const raw = localStorage.getItem("chat_user");
    const token = localStorage.getItem("chat_token");
    const user = raw ? JSON.parse(raw) : null;
    return {
      user: user && typeof user === "object" ? user : null,
      token: typeof token === "string" && token ? token : null,
    };
  } catch {
    return { user: null, token: null };
  }
}

function getInitialState() {
  /* Creates the default state object used to initialize the chat reducer. */
  const { user, token } = loadStoredState();
  return {
    user,
    token,
    rooms: [],
    activeRoom: null,
    messages: [],
    onlineUsers: [],
    typingUsers: {},
    replyingTo: null,
  };
}

function reducer(state, action) {
  /* Applies chat state transitions for auth, room, message, and typing actions. */
  switch (action.type) {
    case "SET_USER":
      localStorage.setItem("chat_user", JSON.stringify(action.payload.user));
      localStorage.setItem("chat_token", action.payload.token);
      return { ...state, user: action.payload.user, token: action.payload.token };

    case "LOGOUT":
      localStorage.removeItem("chat_user");
      localStorage.removeItem("chat_token");
      return { ...getInitialState(), user: null, token: null };

    case "SET_ROOMS":
      return { ...state, rooms: action.payload };

    case "SET_ACTIVE_ROOM":
      return { ...state, activeRoom: action.payload, messages: [], onlineUsers: [], typingUsers: {}, replyingTo: null };

    case "SET_MESSAGES":
      return { ...state, messages: action.payload };

    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.payload] };

    case "REMOVE_MESSAGE":
      return {
        ...state,
        messages: state.messages.filter(
          (m) => m.id == null || Number(m.id) !== Number(action.payload)
        ),
      };

    case "UPDATE_MESSAGE":
      return {
        ...state,
        messages: state.messages.map((m) =>
          Number(m.id) === Number(action.payload.id)
            ? { ...m, content: action.payload.content, edited_at: action.payload.edited_at }
            : m
        ),
      };

    case "SET_REPLYING_TO":
      return { ...state, replyingTo: action.payload };

    case "CLEAR_REPLYING_TO":
      return { ...state, replyingTo: null };

    case "SET_ONLINE_USERS":
      return { ...state, onlineUsers: action.payload };

    case "ADD_TYPING": {
      const name = action.payload;
      return { ...state, typingUsers: { ...state.typingUsers, [name]: true } };
    }

    case "REMOVE_TYPING": {
      const { [action.payload]: _, ...rest } = state.typingUsers;
      return { ...state, typingUsers: rest };
    }

    default:
      return state;
  }
}

export function ChatProvider({ children }) {
  /* Provides reducer-driven chat state and dispatch to descendant components. */
  const [state, dispatch] = useReducer(reducer, undefined, getInitialState);
  return (
    <ChatContext.Provider value={{ state, dispatch }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  /* Returns chat context and guards against usage outside the provider tree. */
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be inside ChatProvider");
  return ctx;
}
