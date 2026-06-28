/*
 * Room navigation sidebar with search, membership status, and admin request cues.
 *
 * This component loads room membership context for the current user, refreshes
 * data on focus/interval/events, surfaces pending admin join requests, and
 * launches room-related modals for joining, creating, and moderation.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useChat } from "../context/ChatContext";
import { api } from "../hooks/useApi";
import { showToast } from "../utils/toast";
import JoinModal from "./JoinModal";
import CreateRoomModal from "./CreateRoomModal";
import AdminJoinRequestsModal from "./AdminJoinRequestsModal";
import NewDirectMessageModal from "./NewDirectMessageModal";
import UserProfileModal from "./UserProfileModal";
import "../styles/Sidebar.css";

/* Display label for a room: a group's name, or the other participant for a DM. */
function roomLabel(room) {
  if (room.room_type === "direct") return room.dmName || "Direct message";
  return room.name || "Untitled";
}

export default function Sidebar({ onEnterRoom, theme, onToggleTheme }) {
  /* Renders room list UI and coordinates room selection and room-level actions. */
  const { state, dispatch } = useChat();
  const { user, rooms, activeRoom } = state;
  const [search, setSearch] = useState("");
  const [joinTarget, setJoinTarget] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [adminPendingBundles, setAdminPendingBundles] = useState([]);
  const [roomPendingCount, setRoomPendingCount] = useState({});
  const [unreadCounts, setUnreadCounts] = useState({});
  const [showAdminJoinModal, setShowAdminJoinModal] = useState(false);
  const [showNewDm, setShowNewDm] = useState(false);
  const [profileUserId, setProfileUserId] = useState(null);
  const autoShownPendingIdsRef = useRef(new Set());

  const loadUnread = useCallback(async () => {
    /* Loads per-room unread message counts for the current user. */
    if (!user) return;
    try {
      const counts = await api("/rooms/unread/counts");
      setUnreadCounts(counts || {});
    } catch (err) {
      console.error("Failed to load unread counts", err);
    }
  }, [user]);

  const loadRooms = useCallback(async () => {
    /* Loads all rooms and enriches each with this user's membership details. */
    if (!user) return;
    const myId = Number(user.id);
    try {
      const allRooms = await api("/rooms/");
      const enriched = await Promise.all(
        allRooms.map(async (room) => {
          try {
            const members = await api(`/rooms/${room.id}/members`);
            const me = members.find((m) => Number(m.user_id) === myId);
            // Direct rooms have no stored name — resolve the other member's name to show.
            let dmName = null;
            let dmUserId = null;
            if (room.room_type === "direct") {
              const other = members.find((m) => Number(m.user_id) !== myId);
              if (other) {
                dmUserId = other.user_id;
                try {
                  const u = await api(`/users/${other.user_id}`);
                  dmName = u.name;
                } catch {
                  dmName = `User ${other.user_id}`;
                }
              }
            }
            return { ...room, membership: me || null, dmName, dmUserId };
          } catch {
            return { ...room, membership: null, dmName: null, dmUserId: null };
          }
        })
      );
      dispatch({ type: "SET_ROOMS", payload: enriched });
    } catch (err) {
      console.error("Failed to load rooms", err);
    }
  }, [user, dispatch]);

  useEffect(() => {
    loadRooms();
  }, [loadRooms]);

  useEffect(() => {
    const onRoomsRefresh = () => loadRooms();
    window.addEventListener("chat-refresh-rooms", onRoomsRefresh);
    return () => window.removeEventListener("chat-refresh-rooms", onRoomsRefresh);
  }, [loadRooms]);

  // Unread badges: load once, refresh when a room is read or the tab regains
  // focus, and poll so background rooms (no live socket) stay roughly current.
  useEffect(() => {
    if (!user) return undefined;
    loadUnread();
    const onUnreadRefresh = () => loadUnread();
    window.addEventListener("chat-unread-refresh", onUnreadRefresh);
    window.addEventListener("focus", onUnreadRefresh);
    const t = setInterval(loadUnread, 10000);
    return () => {
      window.removeEventListener("chat-unread-refresh", onUnreadRefresh);
      window.removeEventListener("focus", onUnreadRefresh);
      clearInterval(t);
    };
  }, [user, loadUnread]);

  // Pick up admin approvals without a full reload (DB was already updated).
  useEffect(() => {
    if (!user) return undefined;
    const refresh = () => {
      loadRooms();
    };
    window.addEventListener("focus", refresh);
    const onVis = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [user, loadRooms]);

  const hasPendingMembership = rooms.some(
    (r) => r.membership?.status === "pending"
  );

  useEffect(() => {
    if (!user || !hasPendingMembership) return undefined;
    const t = setInterval(() => {
      loadRooms();
    }, 10000);
    return () => clearInterval(t);
  }, [user, hasPendingMembership, loadRooms]);

  const fetchAdminJoinRequests = useCallback(async () => {
    /* Fetches pending join requests for rooms where current user is admin. */
    if (!user) return;
    const adminRooms = rooms.filter(
      (r) =>
        r.membership?.role === "admin" &&
        r.membership?.status === "approved"
    );
    if (adminRooms.length === 0) {
      setAdminPendingBundles([]);
      setRoomPendingCount({});
      return;
    }
    const bundles = [];
    const counts = {};
    for (const room of adminRooms) {
      try {
        const pend = await api(`/rooms/${room.id}/pending`);
        counts[room.id] = pend.length;
        if (pend.length) bundles.push({ room, pending: pend });
      } catch (e) {
        console.error(e);
        counts[room.id] = 0;
      }
    }
    setAdminPendingBundles(bundles);
    setRoomPendingCount(counts);

    if (bundles.length === 0) {
      setShowAdminJoinModal(false);
      return;
    }

    const ids = bundles.flatMap((b) => b.pending.map((p) => p.id));
    const hasNew = ids.some((id) => !autoShownPendingIdsRef.current.has(id));
    if (hasNew && ids.length > 0) {
      ids.forEach((id) => autoShownPendingIdsRef.current.add(id));
      setShowAdminJoinModal(true);
    }
  }, [rooms, user]);

  useEffect(() => {
    if (!user || rooms.length === 0) return undefined;
    fetchAdminJoinRequests();
    const t = setInterval(fetchAdminJoinRequests, 15000);
    return () => clearInterval(t);
  }, [user, rooms, fetchAdminJoinRequests]);

  const totalAdminPending = adminPendingBundles.reduce(
    (n, b) => n + b.pending.length,
    0
  );

  const matchesSearch = (r) =>
    roomLabel(r).toLowerCase().includes(search.toLowerCase());

  // Group rooms keep the discovery list (approved → pending → rejected → none).
  const groupRooms = rooms
    .filter((r) => r.room_type !== "direct" && matchesSearch(r))
    .sort((a, b) => {
      const order = (m) => {
        if (!m) return 3;
        if (m.status === "approved") return 0;
        if (m.status === "pending") return 1;
        return 2;
      };
      return order(a.membership) - order(b.membership);
    });

  // Direct rooms only ever include the caller (backend-filtered) and are all approved.
  const directRooms = rooms
    .filter((r) => r.room_type === "direct" && matchesSearch(r))
    .sort((a, b) => roomLabel(a).localeCompare(roomLabel(b)));

  const handleRoomClick = (room) => {
    /* Opens approved rooms or routes non-approved states to feedback/actions. */
    const m = room.membership;
    if (m && m.status === "approved") {
      // Pass the resolved label as the name — direct rooms have no stored name.
      onEnterRoom({ ...room, name: roomLabel(room) }, m.role);
    } else if (m && m.status === "pending") {
      showToast("Your join request is pending admin approval.", "info");
    } else if (m && m.status === "rejected") {
      showToast("Your join request was rejected.", "error");
    } else {
      setJoinTarget(room);
    }
  };

  const badgeFor = (m) => {
    /* Returns a membership status badge node for room list display. */
    if (!m) return null;
    if (m.status === "approved")
      return <span className={`badge badge-${m.role}`}>{m.role}</span>;
    if (m.status === "pending")
      return <span className="badge badge-pending">pending</span>;
    if (m.status === "rejected")
      return <span className="badge badge-rejected">rejected</span>;
    return null;
  };

  const handleLogout = () => {
    /* Clears user session state and returns app to login screen. */
    dispatch({ type: "LOGOUT" });
  };

  const renderRoom = (room) => {
    /* Renders one room/DM row with unread badge and membership cues. */
    const isDirect = room.room_type === "direct";
    return (
      <li
        key={room.id}
        className={activeRoom?.id === room.id ? "active" : ""}
        onClick={() => handleRoomClick(room)}
      >
        <span className="room-name">{roomLabel(room)}</span>
        <span className="room-meta">
          {activeRoom?.id !== room.id && (unreadCounts[room.id] || 0) > 0 && (
            <span className="room-unread-badge" title="Unread messages">
              {unreadCounts[room.id] > 99 ? "99+" : unreadCounts[room.id]}
            </span>
          )}
          {/* Pending-request pill and role badge are group-room concepts only. */}
          {!isDirect &&
            room.membership?.role === "admin" &&
            room.membership?.status === "approved" &&
            (roomPendingCount[room.id] || 0) > 0 && (
              <span className="room-pending-pill" title="Pending join requests">
                {roomPendingCount[room.id]}
              </span>
            )}
          {!isDirect && badgeFor(room.membership)}
        </span>
      </li>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-header-row">
          <div className="user-info">
            <span className="user-name">{user.name}</span>
            <button
              type="button"
              className="edit-profile-btn"
              title="Edit your profile"
              aria-label="Edit your profile"
              onClick={() => setProfileUserId(user.id)}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
              </svg>
            </button>
          </div>
          <div className="sidebar-header-actions">
            {totalAdminPending > 0 && (
              <button
                type="button"
                className="admin-requests-btn"
                onClick={() => setShowAdminJoinModal(true)}
                title="Join requests to approve"
              >
                Requests
                <span className="admin-requests-badge">{totalAdminPending}</span>
              </button>
            )}
            <button
              type="button"
              className="create-room-btn"
              onClick={() => setShowCreate(true)}
              title="Create room"
            >
              +
            </button>
            <button
              type="button"
              className="theme-toggle sidebar-theme-toggle"
              onClick={onToggleTheme}
              title="Toggle theme"
            >
              {theme === "dark" ? "Light" : "Dark"}
            </button>
          </div>
        </div>
        <button
          type="button"
          className="logout-btn sidebar-logout-wide"
          onClick={handleLogout}
          title="Sign out and log in as someone else"
        >
          Log out
        </button>
      </div>

      <div className="search-bar">
        <input
          type="text"
          placeholder="Search for rooms/users through mobile numbers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <ul className="room-list">
        <li className="room-section-header">Rooms</li>
        {groupRooms.map(renderRoom)}
        {groupRooms.length === 0 && (
          <li className="empty-rooms">No rooms found</li>
        )}

        <li className="room-section-header">
          <span>Direct Messages</span>
          <button
            type="button"
            className="dm-new-btn"
            title="New direct message"
            onClick={(e) => {
              e.stopPropagation();
              setShowNewDm(true);
            }}
          >
            +
          </button>
        </li>
        {directRooms.map(renderRoom)}
        {directRooms.length === 0 && (
          <li className="empty-rooms">No direct messages</li>
        )}
      </ul>

      {joinTarget && (
        <JoinModal
          room={joinTarget}
          onClose={() => setJoinTarget(null)}
          onJoined={() => {
            loadRooms();
          }}
        />
      )}

      {showAdminJoinModal && adminPendingBundles.length > 0 && (
        <AdminJoinRequestsModal
          bundles={adminPendingBundles}
          user={user}
          onClose={() => setShowAdminJoinModal(false)}
          onChanged={() => {
            fetchAdminJoinRequests();
            loadRooms();
          }}
        />
      )}

      {showCreate && (
        <CreateRoomModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            loadRooms();
          }}
        />
      )}

      {showNewDm && (
        <NewDirectMessageModal
          onClose={() => setShowNewDm(false)}
          onFound={(foundUserId) => {
            // Hand off to the profile modal, whose "Message" button opens the DM.
            setShowNewDm(false);
            setProfileUserId(foundUserId);
          }}
        />
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
