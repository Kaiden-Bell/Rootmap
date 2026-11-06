import { useEffect, useState, type FormEvent } from "react";
import "./App.css";

//host row returned by the API
type Host = {
  id: number;
  hostname: string;
  ip: string;
  os: string;
};

//result of checking a users login
type LoginResponse = {
  username: string;
  must_change_password: boolean;
};

// Screens shown during sign-in and dashboard use
type Screen = "login" | "change-password" | "dashboard";

//dashboard section selected in the sidebar
type Page = "dashboard" | "hosts";

//json request sent to the backend
async function apiRequest<T>(
  path: string,
  options: { method?: string; body?: object } = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: options.method ?? "GET",
    headers: { "Content-Type": "application/json" },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
  });

  // Keep failed logins from being treated as successful responses
  if (!response.ok) {
    throw new Error("Request failed.");
  }

  return (await response.json()) as T;
}

//Render login and host dashboard
function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [activePage, setActivePage] = useState<Page>("dashboard");
  const [username, setUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [hosts, setHosts] = useState<Host[]>([]);

  // Load saved hosts when dashboard opens
  useEffect(() => {
    if (screen !== "dashboard") return;

    apiRequest<Host[]>("/hosts").then(setHosts);
  }, [screen]);

  // Check the login and show next screen
  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const loginUsername = String(form.get("username") ?? "");
    const password = String(form.get("password") ?? "");

    const result = await apiRequest<LoginResponse>("/login", {
      method: "POST",
      body: { username: loginUsername, password },
    });

    setUsername(result.username);

    if (result.must_change_password) {
      setCurrentPassword(password);
      setScreen("change-password");
    } else {
      setScreen("dashboard");
    }
  }

  //Save users new password
  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const newPassword = String(form.get("new-password") ?? "");

    await apiRequest("/change-password", {
      method: "POST",
      body: {
        username,
        current_password: currentPassword,
        new_password: newPassword,
      },
    });

    setCurrentPassword("");
    setScreen("dashboard");
  }

  // Save host and add to the table
  async function handleAddHost(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    const createdHost = await apiRequest<Host>("/hosts", {
      method: "POST",
      body: {
        hostname: String(form.get("hostname") ?? "").trim(),
        ip: String(form.get("ip") ?? "").trim(),
        os: String(form.get("os") ?? "").trim(),
      },
    });

    setHosts((currentHosts) => [createdHost, ...currentHosts]);
    formElement.reset();
  }

  if (screen === "login") {
    return (
      <main className="auth-page">
        <h1>RootMap</h1>
        <section className="panel auth-panel">
          <h2>Sign in</h2>
          <form onSubmit={handleLogin}>
            <label>
              Username
              <input name="username" required />
            </label>
            <label>
              Password
              <input name="password" type="password" required />
            </label>
            <button type="submit">Sign in</button>
          </form>
        </section>
      </main>
    );
  }

  if (screen === "change-password") {
    return (
      <main className="auth-page">
        <h1>RootMap</h1>
        <section className="panel auth-panel">
          <h2>Change your password</h2>
          <form onSubmit={handlePasswordChange}>
            <label>
              New password
              <input
                name="new-password"
                type="password"
                minLength={8}
                required
              />
            </label>
            <button type="submit">Save password</button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <div className="layout">
      <nav className="sidebar" aria-label="Main navigation">
        <button
          className={activePage === "dashboard" ? "selected" : ""}
          onClick={() => setActivePage("dashboard")}
        >
          Dashboard
        </button>
        <button
          className={activePage === "hosts" ? "selected" : ""}
          onClick={() => setActivePage("hosts")}
        >
          Hosts
        </button>
        <button
          className="sign-out"
          onClick={() => {
            setScreen("login");
          }}
        >
          Sign out
        </button>
      </nav>

      <main className="content">
        {activePage === "dashboard" ? (
          <>
            <h1>Dashboard</h1>
            <section className="panel summary-panel">
              <h2>Registered hosts</h2>
              <p className="host-count">{hosts.length}</p>
            </section>
          </>
        ) : (
          <>
            <h1>Hosts</h1>
            <section className="panel">
              <h2>Add host</h2>
              <form className="host-form" onSubmit={handleAddHost}>
                <label>
                  Hostname
                  <input name="hostname" required />
                </label>
                <label>
                  IP address
                  <input name="ip" required />
                </label>
                <label>
                  Operating system
                  <input name="os" required />
                </label>
                <button type="submit">Add host</button>
              </form>
            </section>
            <h2>Host table</h2>
            <HostTable hosts={hosts} />
          </>
        )}
      </main>
    </div>
  );
}

// Display saved hosts in a table
function HostTable({ hosts }: { hosts: Host[] }) {
  return (
    <div className="panel table-panel">
      <table>
        <thead>
          <tr>
            <th>Hostname</th>
            <th>IP address</th>
            <th>Operating system</th>
          </tr>
        </thead>
        <tbody>
          {hosts.map((host) => (
            <tr key={host.id}>
              <td>{host.hostname}</td>
              <td>{host.ip}</td>
              <td>{host.os}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
