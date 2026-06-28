/*
 * Main chat workspace for active room conversation, typing, files, and moderation.

 * This component connects room websocket streams, loads historical messages,
 * renders message timeline and typing indicators, handles compose/send/reply
 * flows, uploads attachments, supports admin message deletion, and exposes room
 * controls like member panel toggling and leave-room actions.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { useChat } from "../context/ChatContext";
import { API_BASE } from "../config.js";
import { api, uploadFile } from "../hooks/useApi";
import { useWebSocket } from "../hooks/useWebSocket";
import MembersPanel from "./MembersPanel";
import UserProfileModal from "./UserProfileModal";
import { showToast } from "../utils/toast";
import { showConfirm } from "../utils/confirm";
import "../styles/Chat.css";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const MB_DIVISOR = 1024 * 1024;

export default function ChatArea() {
  /* Renders active-room chat UI and coordinates realtime interaction handlers. */
  const { state, dispatch } = useChat();
  const { activeRoom, messages, user, onlineUsers, typingUsers, replyingTo } = state;
  const { connect, disconnect, send } = useWebSocket();
  const messagesEndRef = useRef(null);
  const messageInputRef = useRef(null);
  const fileInputRef = useRef(null);
  const [text, setText] = useState("");
  const [showMembers, setShowMembers] = useState(false);
  const [profileUserId, setProfileUserId] = useState(null);
  const [wsTypingInDebug, setWsTypingInDebug] = useState("idle");
  const [lastTypingUser, setLastTypingUser] = useState(null);
  const typingTimerRef = useRef(null);
  const typingHeartbeatRef = useRef(0);
  const isTypingRef = useRef(false);

  // Connect WS when active room changes — user identity comes from the JWT, not a param
  useEffect(() => {
    if (activeRoom && user) {
      api(`/rooms/${activeRoom.id}/messages/?limit=100`)
        .then((msgs) => dispatch({ type: "SET_MESSAGES", payload: msgs }))
        .catch(console.error);

      connect(activeRoom.id);
      return () => disconnect();
    }
  }, [activeRoom?.id, user?.id]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Mark the open room read whenever its message list changes (open or new
  // arrival while viewing), then tell the sidebar to refresh its unread badges.
  useEffect(() => {
    if (!activeRoom || !user || messages.length === 0) return;
    api(`/rooms/${activeRoom.id}/read`, { method: "POST" })
      .then(() => window.dispatchEvent(new CustomEvent("chat-unread-refresh")))
      .catch(() => {});
  }, [activeRoom?.id, user?.id, messages.length]);

  useEffect(() => {
    const onWsDebug = (event) => {
      const d = event.detail || {};
      if (!d.type || (d.type !== "typing" && d.type !== "stop_typing")) return;
      const when = new Date(d.at || Date.now()).toLocaleTimeString();
      const who = d.user ? ` (${d.user})` : "";
      const rs = d.readyState != null ? ` rs=${d.readyState}` : "";
      const line = `${d.direction}:${d.type}${who}${rs} @ ${when}`;
      if (d.direction === "in") {
        if (d.user) setLastTypingUser(d.user);
        setWsTypingInDebug(line);
      }
    };
    window.addEventListener("chat-ws-debug", onWsDebug);
    return () => window.removeEventListener("chat-ws-debug", onWsDebug);
  }, []);

  // Typing events
  const selfName = user?.name || user?.id || "You";

  const handleInputChange = (e) => {
    /* Updates draft text and emits throttled typing/start-stop typing events. */
    setText(e.target.value);
    const now = Date.now();
    if (!isTypingRef.current || now - typingHeartbeatRef.current > 900) {
      isTypingRef.current = true;
      typingHeartbeatRef.current = now;
      send({ type: "typing" });
      dispatch({ type: "ADD_TYPING", payload: selfName });
    }
    clearTimeout(typingTimerRef.current);
    typingTimerRef.current = setTimeout(() => {
      isTypingRef.current = false;
      typingHeartbeatRef.current = 0;
      send({ type: "stop_typing" });
      dispatch({ type: "REMOVE_TYPING", payload: selfName });
    }, 10000);
  };

  const handleSend = () => {
    /* Sends a text message payload (with optional reply reference) to websocket. */
    if (!text.trim()) return;
    const payload = { type: "message", content: text.trim() };
    if (replyingTo) {
      payload.reply_to = replyingTo.id;
    }
    const sent = send(payload);
    if (!sent) {
      showToast("Message not sent. Reconnecting to chat...");
      return;
    }
    setText("");
    dispatch({ type: "CLEAR_REPLYING_TO" });
    if (isTypingRef.current) {
      isTypingRef.current = false;
      typingHeartbeatRef.current = 0;
      clearTimeout(typingTimerRef.current);
      send({ type: "stop_typing" });
      dispatch({ type: "REMOVE_TYPING", payload: selfName });
    }
  };

  const handleInputBlur = () => {
    /* Stops typing state when message input loses focus. */
    if (isTypingRef.current) {
      isTypingRef.current = false;
      typingHeartbeatRef.current = 0;
      clearTimeout(typingTimerRef.current);
      send({ type: "stop_typing" });
      dispatch({ type: "REMOVE_TYPING", payload: selfName });
    }
  };

  const handleKeyDown = (e) => {
    /* Submits the draft on Enter and preserves multiline on Shift+Enter. */
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileUpload = async (e) => {
    /* Uploads a selected file, shows it locally, and notifies the room via websocket. */
    const file = e.target.files[0];
    if (!file || !activeRoom) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      const selectedSizeMb = (file.size / MB_DIVISOR).toFixed(1);
      const limitMb = (MAX_UPLOAD_BYTES / MB_DIVISOR).toFixed(0);
      showToast(`File size ${selectedSizeMb}MB is larger than ${limitMb}MB. Cannot send.`);
      e.target.value = "";
      return;
    }
    try {
      // userId is no longer sent — the backend reads it from the JWT
      const data = await uploadFile(activeRoom.id, file);

      // Optimistic local update — show the message immediately
      dispatch({
        type: "ADD_MESSAGE",
        payload: {
          id: data.message_id,
          sender_id: user.id,
          sender_name: user.name,
          type: "file",
          content: data.file_url,
          filename: data.filename,
          created_at: new Date().toISOString(),
        },
      });

      // Notify others in the room via websocket
      send({
        type: "file",
        message_id: data.message_id,
        file_url: data.file_url,
        filename: data.filename,
      });
    } catch (err) {
      showToast("Upload failed: " + err.message);
    }
    e.target.value = "";
  };

  const handleDeleteMessage = useCallback(
    async (messageId) => {
      /* Confirms and deletes a message for all room participants (admin only). */
      if (!activeRoom || !user) return;
      if (!await showConfirm("Delete this message for everyone in the room?")) return;
      try {
        // admin_id is no longer sent — the backend reads it from the JWT
        await api(
          `/rooms/${activeRoom.id}/messages/${messageId}`,
          { method: "DELETE" }
        );
        dispatch({ type: "REMOVE_MESSAGE", payload: messageId });
      } catch (err) {
        showToast(err.message);
      }
    },
    [activeRoom?.id, user, dispatch]
  );

  const handleReply = useCallback(
    (msg) => {
      /* Stores reply target metadata and focuses the message input field. */
      dispatch({
        type: "SET_REPLYING_TO",
        payload: {
          id: msg.id,
          sender_name: msg.sender_name || `User ${msg.sender_id}`,
          content: msg.type === "file" ? (msg.filename || "Attachment") : msg.content,
        },
      });
      messageInputRef.current?.focus();
    },
    [dispatch]
  );

  const scrollToMessage = useCallback((messageId) => {
    /* Scrolls to and briefly highlights a referenced message in the timeline. */
    const el = document.getElementById(`msg-${messageId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("msg-highlight");
      setTimeout(() => el.classList.remove("msg-highlight"), 1500);
      return;
    }
    showToast("Message not found");
  }, []);

  const handleLeaveRoom = useCallback(async () => {
    /* Leaves the active room, clears chat state, and requests room list refresh. */
    if (!activeRoom || !user) return;
    if (!await showConfirm(`Leave "${activeRoom.name}"?`)) return;

    try {
      // user_id is no longer sent — the backend reads it from the JWT
      await api(
        `/rooms/${activeRoom.id}/leave`,
        { method: "POST" }
      );
      dispatch({ type: "SET_ACTIVE_ROOM", payload: null });
      dispatch({ type: "SET_MESSAGES", payload: [] });
      window.dispatchEvent(new CustomEvent("chat-refresh-rooms"));
    } catch (err) {
      showToast(err.message);
    }
  }, [activeRoom?.id, user?.id, dispatch]);

  if (!activeRoom) {
    return (
      <main className="chat-area">
        <div className="empty-state">
          <p>Select a room to start chatting</p>
        </div>
      </main>
    );
  }

  const canWrite = activeRoom.role === "write" || activeRoom.role === "admin";
  const isAdmin = activeRoom.role === "admin";
  const isDirect = activeRoom.room_type === "direct";
  const typingNames = Object.keys(typingUsers);
  const typingLabel =
    typingNames.length === 1
      ? `${typingNames[0]} is typing...`
      : typingNames.length === 2
      ? `${typingNames[0]} and ${typingNames[1]} are typing...`
      : typingNames.length > 2
      ? `${typingNames.length} people are typing...`
      : null;

  return (
    <main className="chat-area">
      <div className="chat-view">
        {/* Header */}
        <div className="chat-header">
          <button
            type="button"
            className="chat-back-btn"
            title="Back to rooms"
            aria-label="Back to rooms"
            onClick={() => dispatch({ type: "SET_ACTIVE_ROOM", payload: null })}
          >
            ←
          </button>
          <h2>{activeRoom.name}</h2>
          <div className="chat-header-right">
            {/* Role/members/leave are group concepts — direct chats omit them. */}
            {!isDirect && (
              <span className={`badge badge-${activeRoom.role}`}>{activeRoom.role}</span>
            )}
            <span className="online-count">{onlineUsers.length} online</span>
            {!isDirect && (
              <button
                className="members-btn"
                onClick={() => setShowMembers((v) => !v)}
              >
                Members
              </button>
            )}
            {!isDirect && (
              <button
                className="leave-btn"
                onClick={handleLeaveRoom}
                title="Leave this room"
                aria-label="Leave room"
              >
                Leave
              </button>
            )}
          </div>
        </div>

        {/* Typing bar */}
        <div className="typing-bar">
          {typingLabel ? (
            <>
              <span className="typing-dots">
                <span /><span /><span />
              </span>
              {typingLabel}
            </>
          ) : null}
        </div>

        {/* Messages */}
        <div className="messages-container">
          {messages.map((msg, i) => (
            <MessageBubble
              key={msg.id || `sys-${i}`}
              msg={msg}
              userId={user.id}
              isAdmin={isAdmin}
              canWrite={canWrite}
              onDelete={handleDeleteMessage}
              onReply={handleReply}
              onClickReply={scrollToMessage}
              onClickSender={setProfileUserId}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Compose or read-only */}
        {canWrite ? (
          <div className="compose-section">
            {/* Reply preview banner */}
            {replyingTo && (
              <div className="reply-banner">
                <div className="reply-banner-content">
                  <span className="reply-banner-name">{replyingTo.sender_name}</span>
                  <span className="reply-banner-text">{replyingTo.content}</span>
                </div>
                <button
                  type="button"
                  className="reply-banner-close"
                  onClick={() => dispatch({ type: "CLEAR_REPLYING_TO" })}
                >
                  ×
                </button>
              </div>
            )}
            <div className="compose-bar">
              <label className="file-label" title="Attach file">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
                </svg>
                <input
                  ref={fileInputRef}
                  type="file"
                  hidden
                  accept="image/*,audio/*,video/*,.pdf,.txt,.doc,.docx,.csv,.zip"
                  onChange={handleFileUpload}
                />
              </label>
              <textarea
                ref={messageInputRef}
                className="message-input"
                placeholder={replyingTo ? "Type your reply..." : "Type a message..."}
                value={text}
                onChange={handleInputChange}
                onBlur={handleInputBlur}
                onKeyDown={handleKeyDown}
                rows={1}
              />
              <button className="send-btn" onClick={handleSend}>
                Send
              </button>
            </div>
          </div>
        ) : (
          <div className="readonly-banner">
            You have read-only access to this room
          </div>
        )}
      </div>

      {showMembers && (
        <MembersPanel onClose={() => setShowMembers(false)} />
      )}

      {profileUserId != null && (
        <UserProfileModal
          userId={profileUserId}
          onClose={() => setProfileUserId(null)}
        />
      )}
    </main>
  );
}

/* ── Single message bubble ── */
function MessageBubble({ msg, userId, isAdmin, canWrite, onDelete, onReply, onClickReply, onClickSender }) {
  /* Renders one chat message row, including reply quote and action buttons. */
  const [expanded, setExpanded] = useState(false);

  // Build an authenticated media URL by embedding the JWT as a query param.
  // <img src> and <audio src> cannot send Authorization headers, so ?token= is the fallback.
  function mediaUrl(path) {
    const token = localStorage.getItem("chat_token") || "";
    return `${API_BASE}${path}?token=${encodeURIComponent(token)}`;
  }

  if (msg.type === "system") {
    return <div className="msg-system">{msg.content}</div>;
  }

  const isMe = msg.sender_id === userId;
  const time = msg.created_at
    ? new Date(msg.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div id={`msg-${msg.id}`} className={`msg ${isMe ? "msg-out" : "msg-in"}`}>
      <div className="msg-body-row">
        <div className="msg-main">
          {!isMe && (
            <div
              className="sender sender-clickable"
              role="button"
              tabIndex={0}
              title="View profile"
              onClick={() => onClickSender?.(msg.sender_id)}
              onKeyDown={(e) => e.key === "Enter" && onClickSender?.(msg.sender_id)}
            >
              {msg.sender_name || `User ${msg.sender_id}`}
            </div>
          )}

          {/* Quoted reply block */}
          {msg.reply_snippet && (
            <div
              className="msg-reply-quote"
              onClick={() => onClickReply(msg.reply_snippet.id)}
            >
              <span className="reply-quote-name">{msg.reply_snippet.sender_name}</span>
              {msg.reply_snippet.is_image && msg.reply_snippet.file_url ? (
                <img
                  className="reply-quote-image"
                  src={mediaUrl(msg.reply_snippet.file_url)}
                  alt={msg.reply_snippet.filename || "Replied image"}
                  loading="lazy"
                />
              ) : null}
              <span className="reply-quote-text">{msg.reply_snippet.content}</span>
            </div>
          )}

          {msg.type === "file" ? (
            (() => {
              const url = mediaUrl(msg.content);
              const name = (msg.filename || "").toLowerCase();
              const ext = name.slice(name.lastIndexOf("."));
              const imageExts = [".png", ".jpg", ".jpeg", ".gif"];
              const audioExts = [".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"];
              const videoExts = [".mp4", ".webm", ".mov", ".avi", ".mkv"];

              if (imageExts.includes(ext)) {
                return (
                  <div className="file-attachment">
                    <img
                      className="file-preview-img"
                      src={url}
                      alt={msg.filename}
                      loading="lazy"
                      onClick={() => setExpanded(true)}
                    />
                    <div className="file-attachment-actions">
                      <button
                        type="button"
                        className="file-action-btn"
                        title="Expand"
                        onClick={() => setExpanded(true)}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                        Expand
                      </button>
                      <a className="file-action-btn" href={url} download={msg.filename} title="Download">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Download
                      </a>
                    </div>
                    {expanded && (
                      <div className="file-expand-overlay" onClick={() => setExpanded(false)}>
                        <img src={url} alt={msg.filename} className="file-expand-img" />
                      </div>
                    )}
                  </div>
                );
              }

              if (audioExts.includes(ext)) {
                return (
                  <div className="file-attachment">
                    <div className="file-attachment-name">{msg.filename}</div>
                    <audio controls preload="none" src={url} style={{ width: "100%" }} />
                    <div className="file-attachment-actions">
                      <a className="file-action-btn" href={url} download={msg.filename} title="Download">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Download
                      </a>
                    </div>
                  </div>
                );
              }

              if (videoExts.includes(ext)) {
                return (
                  <div className="file-attachment">
                    <div className="file-attachment-name">{msg.filename}</div>
                    <video controls preload="none" src={url} className="file-preview-video" />
                    <div className="file-attachment-actions">
                      <a className="file-action-btn" href={url} download={msg.filename} title="Download">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Download
                      </a>
                    </div>
                  </div>
                );
              }

              return (
                <div className="file-attachment">
                  <div className="file-attachment-name">{msg.filename || "Attachment"}</div>
                  <div className="file-attachment-actions">
                    <a
                      className="file-action-btn"
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      title="Open"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                      Open
                    </a>
                    <a className="file-action-btn" href={url} download={msg.filename} title="Download">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                      Download
                    </a>
                  </div>
                </div>
              );
            })()
          ) : (
            <div className="text">{msg.content}</div>
          )}
          <div className="meta">{time}</div>
        </div>

        {/* Action icons */}
        {msg.id != null && (
          <div className="msg-actions">
            {canWrite && (
              <button
                type="button"
                className="msg-action-btn"
                title="Reply"
                aria-label="Reply"
                onClick={() => onReply(msg)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="9 17 4 12 9 7" />
                  <path d="M20 18v-2a4 4 0 00-4-4H4" />
                </svg>
              </button>
            )}
            {(isAdmin || isMe) && (
              <button
                type="button"
                className="msg-action-btn msg-action-delete"
                title="Delete message"
                aria-label="Delete message"
                onClick={() => onDelete(msg.id)}
              >
                ×
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
