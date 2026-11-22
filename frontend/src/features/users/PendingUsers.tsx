import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";

type Role = "annotator" | "reviewer" | "administrator";

type PendingUser = {
  id: string;
  email: string;
  full_name: string;
  role: Role | null;
  status: "pending" | "active" | "rejected";
  created_at: string;
};

export default function PendingUsers() {
  const [users, setUsers] = useState<PendingUser[]>([]);
  const [selectedRoles, setSelectedRoles] = useState<Record<string, Role>>({});
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  async function fetchPendingUsers() {
    setError("");

    const token = localStorage.getItem("access_token");

    if (!token) {
      setError("Not authenticated");
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/users/pending`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail ?? "Failed to load pending users");
        return;
      }

      setUsers(data);

      const initialRoles: Record<string, Role> = {};

      data.forEach((user: PendingUser) => {
        initialRoles[user.id] = "annotator";
      });

      setSelectedRoles(initialRoles);
    } catch {
      setError("Could not connect to the server");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchPendingUsers();
  }, []);

  async function approveUser(userId: string) {
    setError("");
    setMessage("");

    const token = localStorage.getItem("access_token");

    if (!token) {
      setError("Not authenticated");
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/users/${userId}/approve`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            role: selectedRoles[userId] ?? "annotator",
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail ?? "Failed to approve user");
        return;
      }

      setUsers((currentUsers) =>
        currentUsers.filter((user) => user.id !== userId)
      );

      setMessage(`Approved ${data.email}`);
    } catch {
      setError("Could not connect to the server");
    }
  }

  async function rejectUser(userId: string) {
    setError("");
    setMessage("");

    const token = localStorage.getItem("access_token");

    if (!token) {
      setError("Not authenticated");
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/users/${userId}/reject`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail ?? "Failed to reject user");
        return;
      }

      setUsers((currentUsers) =>
        currentUsers.filter((user) => user.id !== userId)
      );

      setMessage(`Rejected ${data.email}`);
    } catch {
      setError("Could not connect to the server");
    }
  }

  const filteredUsers = users.filter((user) =>
    user.email.toLowerCase().includes(search.toLowerCase())
  );

  if (isLoading) {
    return <p>Loading pending users...</p>;
  }

  return (
    <section>

      <input
        type="search"
        placeholder="Search by email..."
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />

      {error && <p>{error}</p>}
      {message && <p>{message}</p>}

      {users.length === 0 ? (
        <p>No pending users.</p>
      ) : filteredUsers.length === 0 ? (
        <p>No users found.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {filteredUsers.map((user) => (
              <tr key={user.id}>
                <td>{user.full_name}</td>
                <td>{user.email}</td>

                <td>
                  <select
                    value={selectedRoles[user.id] ?? "annotator"}
                    onChange={(event) =>
                      setSelectedRoles((current) => ({
                        ...current,
                        [user.id]: event.target.value as Role,
                      }))
                    }
                  >
                    <option value="annotator">Annotator</option>
                    <option value="reviewer">Reviewer</option>
                    <option value="administrator">Administrator</option>
                  </select>
                </td>

                <td>
                  <button
                    type="button"
                    onClick={() => approveUser(user.id)}
                  >
                    Approve
                  </button>

                  <button
                    type="button"
                    onClick={() => rejectUser(user.id)}
                  >
                    Reject
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
