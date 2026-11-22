import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";

type Mode = "login" | "register";

export default function LoginPage({
  onLogin,
}: {
  onLogin: (token: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("login");

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setError("");
    setMessage("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);

        setError(
          data?.detail ??
            `Login failed (${response.status})`
        );

        return;
      }

      const data = await response.json();

      localStorage.setItem("access_token", data.access_token);

      onLogin(data.access_token);
    } catch (err) {
      console.error("Login request failed:", err);
      setError("Could not reach the server.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    setError("");
    setMessage("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          full_name: fullName,
          password,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);

        setError(
          data?.detail ??
            `Registration failed (${response.status})`
        );

        return;
      }

      setMessage(
        "Registration successful. Your account is waiting for administrator approval."
      );

      setFullName("");
      setPassword("");
    } catch (err) {
      console.error("Registration request failed:", err);
      setError("Could not reach the server.");
    } finally {
      setIsLoading(false);
    }
  };

  const switchMode = () => {
    setError("");
    setMessage("");

    if (mode === "login") {
      setMode("register");
    } else {
      setMode("login");
    }
  };

  return (
    <main className="login-page">
      <div className="login-card">
        <h1>Video Annotation</h1>

        <h2>
          {mode === "login"
            ? "Sign in"
            : "Create account"}
        </h2>

        <form
          onSubmit={
            mode === "login"
              ? handleLogin
              : handleRegister
          }
        >
          {mode === "register" && (
            <div>
              <label htmlFor="full-name">
                Full name
              </label>

              <input
                id="full-name"
                type="text"
                value={fullName}
                onChange={(event) =>
                  setFullName(event.target.value)
                }
                required
              />
            </div>
          )}

          <div>
            <label htmlFor="email">
              Email
            </label>

            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              required
            />
          </div>

          <div>
            <label htmlFor="password">
              Password
            </label>

            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              minLength={12}
              required
            />
          </div>

          {error && (
            <p className="login-error">
              {error}
            </p>
          )}

          {message && (
            <p className="login-message">
              {message}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoading}
          >
            {isLoading
              ? "Please wait..."
              : mode === "login"
                ? "Sign in"
                : "Register"}
          </button>
        </form>

        <button
          type="button"
          onClick={switchMode}
          disabled={isLoading}
        >
          {mode === "login"
            ? "Don't have an account? Register"
            : "Already have an account? Sign in"}
        </button>
      </div>
    </main>
  );
}