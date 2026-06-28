/*
 * Modal for starting a direct message by looking someone up by phone number.
 *
 * Resolves the number via GET /users/by-mobile/{number}; on a match it hands the
 * found user's id back to the parent, which opens their profile (where "Message"
 * finds-or-creates the 1:1 room). Keeps this modal focused on the lookup only.
 */
import { useState } from "react";
import { api } from "../hooks/useApi";
import "../styles/Modal.css";

export default function NewDirectMessageModal({ onClose, onFound }) {
  /* Collects a mobile number, resolves it to a user, and reports the match upward. */
  const [number, setNumber] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    /* Looks up the entered mobile number and surfaces the matching user. */
    e.preventDefault();
    if (!number.trim()) {
      setError("Enter a mobile number");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const user = await api(`/users/by-mobile/${encodeURIComponent(number.trim())}`);
      onFound(user.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>New Direct Message</h3>
        <p>Find someone by their mobile number to start a chat.</p>
        <form onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="Mobile number"
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            autoFocus
          />
          <button type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </button>
          <button type="button" className="cancel-btn" onClick={onClose}>
            Cancel
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
