
import { useEffect, useState } from "react";

const rawBackend =
  import.meta.env.VITE_BACKEND || "http://127.0.0.1:8000";

const API = rawBackend.endsWith("/")
  ? rawBackend.slice(0, -1)
  : rawBackend;

export const getToken = () => sessionStorage.getItem("tok");
console.log("Backend API:", API, "Token present:", !!getToken());

// Cloudinary URL ko as-is use karega.
// Purane records mein sirf filename ho to local route fallback rahega.
export const evidenceUrl = (value, kind = "evidence") => {
  if (!value) return null;

  if (typeof value === "object") {
    const candidates =
      kind === "plate"
        ? [
            value.plate_url,
            value.plateUrl,
            value.plateImage,
            value.plate_image,
          ]
        : [
            value.evidence_url,
            value.evidenceUrl,
            value.evidenceImage,
            value.evidence_image,
          ];

    const found = candidates.find(
      (v) => typeof v === "string" && v.trim()
    );

    return found ? evidenceUrl(found, kind) : null;
  }

  const s = String(value).trim();
  if (!s) return null;

  // Cloudinary ya koi bhi absolute URL ho to usay change nahi karna.
  if (/^https?:\/\//i.test(s)) return s;

  // Relative API path.
  if (s.startsWith("/")) return `${API}${s}`;

  // Sirf purane local filenames ke liye.
  return `${API}/evidence/${encodeURIComponent(s)}`;
};

export const toDate = (t) =>
  new Date(/Z|\+/.test(t) ? t : t + "Z");

export async function api(path, opt = {}) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  const r = await fetch(API + cleanPath, {
    ...opt,
    headers: {
      "Content-Type": "application/json",
      ...(getToken() && {
        Authorization: "Bearer " + getToken(),
      }),
      ...opt.headers,
    },
  });

  if (r.status === 401 && getToken()) {
    sessionStorage.removeItem("tok");
    location.href = "/login";
  }

  if (!r.ok) {
    throw new Error(
      r.status === 422
        ? "Invalid input (password needs 6+ characters)"
        : r.status === 401
        ? "Wrong username or password"
        : "Request failed (" + r.status + ")"
    );
  }

  return r.json();
}

export function usePoll(path, ms = 10000) {
  const [d, setD] = useState(null);
  const [e, setE] = useState(null);

  useEffect(() => {
    let on = true;
    setD(null);

    const f = () =>
      api(path)
        .then((x) => on && (setD(x), setE(null)))
        .catch(
          (x) =>
            on &&
            setE(
              x.message === "Failed to fetch"
                ? "Backend not reachable. Is uvicorn running?"
                : x.message
            )
        );

    f();
    const t = setInterval(f, ms);

    return () => {
      on = false;
      clearInterval(t);
    };
  }, [path, ms]);

  return [d, e];
}

export async function download(path, name) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  const r = await fetch(API + cleanPath, {
    headers: {
      Authorization: "Bearer " + getToken(),
    },
  });

  if (!r.ok) throw new Error("Download failed (" + r.status + ")");

  const u = URL.createObjectURL(await r.blob());
  const l = document.createElement("a");

  l.href = u;
  l.download = name;
  l.click();

  URL.revokeObjectURL(u);
}
