/*
 * Room members side panel with admin moderation and role-management controls.
 *
 * This component loads approved and pending members, resolves user names,
 * supports admin actions (approve/reject/promote/remove), and refreshes its
 * content in response to room changes and global member refresh events.
 */
import { useState, useEffect, useRef } from "react";
import { useChat } from "../context/ChatContext";
import { api } from "../hooks/useApi";
import { showToast } from "../utils/toast";
import { showConfirm } from "../utils/confirm";
import UserProfileModal from "./UserProfileModal";
import "../styles/Members.css";

export default function MembersPanel({ onClose }) {
  /* Renders member lists and action buttons for the active room. */
  const { state } = useChat();
  const { activeRoom, user } = state;
  const [members, setMembers] = useState([]);
  const [pending, setPending] = useState([]);
  const [names, setNames] = useState({});
  const [profileUserId, setProfileUserId] = useState(null);

  const isAdmin = activeRoom?.role === "admin";

  const loadMembersRef = useRef(async () => {});

  const loadMembers = async () => {
    /* Fetches current room memberships and optional admin pending requests. */
    if (!activeRoom) return;
    const admin = activeRoom.role === "admin";
    try {
      const all = await api(`/rooms/${activeRoom.id}/members`);
      const approved = all.filter((m) => m.status === "approved");
      setMembers(approved);

      // Resolve names
      const nameMap = { ...names };
      for (const m of all) {
        if (!nameMap[m.user_id]) {
          try {
            const u = await api(`/users/${m.user_id}`);
            nameMap[u.id] = u.name;
          } catch {
            nameMap[m.user_id] = `User ${m.user_id}`;
          }
        }
      }
      setNames(nameMap);

      if (admin) {
        const pend = await api(`/rooms/${activeRoom.id}/pending`);
        setPending(pend);
      } else {
        setPending([]);
      }
    } catch (err) {
      console.error("Failed to load members", err);
    }
  };

  loadMembersRef.current = loadMembers;

  useEffect(() => {
    loadMembers();
  }, [activeRoom?.id, activeRoom?.role]);

  useEffect(() => {
    const onMembersRefresh = () => loadMembersRef.current();
    window.addEventListener("chat-refresh-members", onMembersRefresh);
    return () => window.removeEventListener("chat-refresh-members", onMembersRefresh);
  }, []);

  const handleRemoveMember = async (targetUserId) => {
    /* Removes a member from the active room after confirmation. */
    if (!activeRoom || !user) return;
    if (!await showConfirm("Remove this member from the room?")) return;
    try {
      // admin identity comes from the JWT — no admin_id param needed
      await api(
        `/rooms/${activeRoom.id}/members/${targetUserId}`,
        { method: "DELETE" }
      );
      loadMembers();
    } catch (err) {
      showToast(err.message);
    }
  };

  const handlePromoteMember = async (targetUserId) => {
    /* Promotes a non-admin member to admin after confirmation. */
    if (!activeRoom || !user) return;
    if (!await showConfirm("Promote this member to admin?")) return;
    try {
      // admin identity comes from the JWT — only target user_id in body
      await api(`/rooms/${activeRoom.id}/promote`, {
        method: "POST",
        body: JSON.stringify({ user_id: targetUserId }),
      });
      loadMembers();
    } catch (err) {
      showToast(err.message);
    }
  };

  const handleAction = async (userId, action) => {
    /* Applies admin approve/reject action for a pending join request. */
    try {
      // admin identity comes from the JWT — only target user_id in body
      await api(`/rooms/${activeRoom.id}/${action}`, {
        method: "POST",
        body: JSON.stringify({ user_id: userId }),
      });
      loadMembers();
    } catch (err) {
      showToast(err.message);
    }
  };

  return (
    <aside className="members-panel">
      <div className="panel-header">
        <h3>Members</h3>
        <button onClick={onClose}>&times;</button>
      </div>

      <div className="members-list">
        {members.map((m) => {
          // Count admins to determine if we can remove one
          const adminCount = members.filter(mem => mem.role === "admin").length;

          const canRemove =
            isAdmin &&
            Number(m.user_id) !== Number(user?.id) &&
            !(m.role === "admin" && adminCount <= 1); // Allow removal of admin if count > 1

          const canPromote =
            isAdmin &&
            Number(m.user_id) !== Number(user?.id) &&
            m.role !== "admin";
          return (
            <div key={m.id} className="member-row">
              <span
                className="name name-clickable"
                role="button"
                tabIndex={0}
                title="View profile"
                onClick={() => setProfileUserId(m.user_id)}
                onKeyDown={(e) => e.key === "Enter" && setProfileUserId(m.user_id)}
              >
                {names[m.user_id] || `User ${m.user_id}`}
              </span>
              <span className="member-row-actions">
                <span className={`badge badge-${m.role}`}>{m.role}</span>
                {canPromote && (
                  <button
                    type="button"
                    className="btn-promote"
                    title="Promote to admin"
                    onClick={() => handlePromoteMember(m.user_id)}
                  >
                    Promote
                  </button>
                )}
                {canRemove && (
                  <button
                    type="button"
                    className="btn-remove"
                    title="Remove from room"
                    onClick={() => handleRemoveMember(m.user_id)}
                  >
                    Remove
                  </button>
                )}
              </span>
            </div>
          );
        })}
      </div>

      {isAdmin && pending.length > 0 && (
        <div className="pending-section">
          <h4>Pending Requests</h4>
          {pending.map((p) => (
            <div key={p.id} className="pending-row">
              <span className="name">
                {names[p.user_id] || `User ${p.user_id}`}
                <span className={`badge badge-${p.role}`}>{p.role}</span>
              </span>
              <button
                className="btn-approve"
                onClick={() => handleAction(p.user_id, "approve")}
              >
                Approve
              </button>
              <button
                className="btn-reject"
                onClick={() => handleAction(p.user_id, "reject")}
              >
                Reject
              </button>
            </div>
          ))}
        </div>
      )}

      {profileUserId != null && (
        <UserProfileModal
          userId={profileUserId}
          onClose={() => setProfileUserId(null)}
        />
      )}
    </aside>
  );
}
