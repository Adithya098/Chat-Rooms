/*
 * Modal dialog for viewing and editing a user's profile.
 *
 * Opening your own profile shows editable name/mobile fields saved via
 * PATCH /users/me. Opening someone else's shows a read-only view plus a
 * "Message" button that finds-or-creates a 1:1 direct room and opens it.
 */
import { useEffect, useState } from "react";
import { useChat } from "../context/ChatContext";
import { api } from "../hooks/useApi";
import { showToast } from "../utils/toast";
import "../styles/Modal.css";

export default function UserProfileModal({ userId, onClose }) {
  /* Renders an editable self-profile or a read-only profile with a Message action. */
  const { state, dispatch } = useChat();
  const isSelf = Number(userId) === Number(state.user?.id);

  const [profile, setProfile] = useState(isSelf ? state.user : null);
  const [name, setName] = useState(isSelf ? state.user?.name || "" : "");
  const [email, setEmail] = useState(isSelf ? state.user?.email || "" : "");
  const [mobile, setMobile] = useState(isSelf ? state.user?.mobile || "" : "");
  const [loading, setLoading] = useState(!isSelf);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    /* Loads another user's profile; self data already lives in context. */
    if (isSelf) return;
    let active = true;
    api(`/users/${userId}`)
      .then((u) => {
        if (active) setProfile(u);
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [userId, isSelf]);

  const handleSave = async (e) => {
    /* Persists edited name/mobile and refreshes the stored session user. */
    e.preventDefault();
    if (!name.trim()) {
      setError("Name cannot be empty");
      return;
    }
    if (!email.trim()) {
      setError("Email cannot be empty");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const updated = await api("/users/me", {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          mobile: mobile.trim(),
        }),
      });
      // SET_USER also re-persists user + token to localStorage; token is unchanged.
      dispatch({ type: "SET_USER", payload: { user: updated, token: state.token } });
      showToast("Profile updated");
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleMessage = async () => {
    /* Finds or creates the 1:1 room with this user and opens it in the chat area. */
    setBusy(true);
    try {
      const room = await api("/rooms/direct", {
        method: "POST",
        body: JSON.stringify({ user_id: Number(userId) }),
      });
      // Direct rooms store no name — show the other participant's name in the header.
      dispatch({
        type: "SET_ACTIVE_ROOM",
        payload: {
          id: room.id,
          name: profile?.name || `User ${userId}`,
          role: "write",
          room_type: room.room_type || "direct",
        },
      });
      window.dispatchEvent(new CustomEvent("chat-refresh-rooms"));
      onClose();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>{isSelf ? "Your Profile" : "Profile"}</h3>

        {loading ? (
          <p>Loading…</p>
        ) : isSelf ? (
          <form onSubmit={handleSave}>
            <label className="profile-field">
              <span className="profile-label">Name</span>
              <input
                type="text"
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </label>
            <label className="profile-field">
              <span className="profile-label">Email</span>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="profile-field">
              <span className="profile-label">Mobile</span>
              <input
                type="text"
                placeholder="Mobile number"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
              />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" className="cancel-btn" onClick={onClose}>
              Cancel
            </button>
          </form>
        ) : (
          <>
            <div className="profile-field">
              <span className="profile-label">Name</span>
              <span className="profile-value">{profile?.name || `User ${userId}`}</span>
            </div>
            <div className="profile-field">
              <span className="profile-label">Mobile</span>
              <span className="profile-value">{profile?.mobile || "—"}</span>
            </div>
            <div className="profile-field">
              <span className="profile-label">Email</span>
              <span className="profile-value">{profile?.email || "—"}</span>
            </div>
            <button type="button" onClick={handleMessage} disabled={busy}>
              {busy ? "Opening…" : "Message"}
            </button>
            <button type="button" className="cancel-btn" onClick={onClose}>
              Close
            </button>
          </>
        )}

        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
