/** Client REST minimal (le proxy Vite route /api vers le backend). */

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* réponse non JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function get(path, params) {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
        )
      )
    : "";
  return fetch(`/api${path}${qs}`).then(handle);
}

export function post(path, body) {
  return fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(handle);
}

export function upload(path, formData) {
  return fetch(`/api${path}`, { method: "POST", body: formData }).then(handle);
}
