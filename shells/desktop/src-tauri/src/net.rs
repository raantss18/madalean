//! HTTP calls of the shell (native client, never from the web view): hello, pair, session ticket.
//! The device token only ever travels in an `Authorization: Bearer` header over TLS or loopback.

use crate::core::{map_pair_response, Hello, ShellError};
use std::time::Duration;
use url::Url;

fn client() -> Result<reqwest::Client, ShellError> {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(5))
        .timeout(Duration::from_secs(12))
        .redirect(reqwest::redirect::Policy::none())
        .https_only(false) // http allowed only for loopback origins, enforced by core::normalise_address
        .user_agent(concat!("madalean-desktop/", env!("CARGO_PKG_VERSION")))
        .build()
        .map_err(|e| ShellError::Internal { detail: e.to_string() })
}

fn net_err(e: reqwest::Error) -> ShellError {
    let mut detail = e.to_string();
    let mut src: Option<&dyn std::error::Error> = std::error::Error::source(&e);
    while let Some(s) = src {
        detail.push_str(": ");
        detail.push_str(&s.to_string());
        src = s.source();
    }
    let lower = detail.to_lowercase();
    if lower.contains("certificate") || lower.contains("tls") || lower.contains("handshake") {
        ShellError::Tls { detail }
    } else {
        ShellError::Unreachable { detail }
    }
}

fn api(origin: &Url, path: &str) -> Url {
    origin.join(path).expect("static path")
}

/// `GET /api/hello`, with the Bearer token when we have one (then `paired` tells if it is still valid).
pub async fn hello(origin: &Url, token: Option<&str>) -> Result<Hello, ShellError> {
    let mut req = client()?.get(api(origin, "/api/hello"));
    if let Some(t) = token {
        req = req.bearer_auth(t);
    }
    let resp = req.send().await.map_err(net_err)?;
    if !resp.status().is_success() {
        return Err(ShellError::NotMadalean);
    }
    let h: Hello = resp.json().await.map_err(|_| ShellError::NotMadalean)?;
    if h.name != "madalean" {
        return Err(ShellError::NotMadalean);
    }
    Ok(h)
}

/// `POST /api/pair {code, device_name, client: "app-desktop"}` → token (apps keep a long-lived device token).
pub async fn pair(origin: &Url, code: &str, device_name: &str) -> Result<(String, Option<String>), ShellError> {
    let resp = client()?
        .post(api(origin, "/api/pair"))
        .json(&serde_json::json!({ "code": code, "device_name": device_name, "client": "app-desktop" }))
        .send()
        .await
        .map_err(net_err)?;
    let status = resp.status().as_u16();
    let ra = resp.headers().get("retry-after").and_then(|v| v.to_str().ok()).map(str::to_string);
    let body = resp.text().await.unwrap_or_default();
    map_pair_response(status, &body, ra.as_deref())
}

/// `POST /api/session/ticket` (Bearer) → one-time ticket for `GET /api/session`.
pub async fn ticket(origin: &Url, token: &str) -> Result<String, ShellError> {
    let resp = client()?
        .post(api(origin, "/api/session/ticket"))
        .bearer_auth(token)
        .send()
        .await
        .map_err(net_err)?;
    match resp.status().as_u16() {
        200 => {
            let v: serde_json::Value = resp.json().await.map_err(|_| ShellError::NotMadalean)?;
            v.get("ticket")
                .and_then(|t| t.as_str())
                .filter(|t| !t.is_empty() && t.len() < 512)
                .map(str::to_string)
                .ok_or(ShellError::NotMadalean)
        }
        401 | 403 => Err(ShellError::Revoked),
        404 => Err(ShellError::NotMadalean),
        s => Err(ShellError::Server { status: s }),
    }
}

/// Ask the server to revoke this device (best effort, contract item 8): `POST /api/devices/self/forget`,
/// or the current server's `POST /api/logout` (Bearer) when the former does not exist.
pub async fn forget(origin: &Url, token: &str) {
    if let Ok(c) = client() {
        let r = c.post(api(origin, "/api/devices/self/forget")).bearer_auth(token).send().await;
        if matches!(&r, Ok(resp) if resp.status().as_u16() == 404 || resp.status().as_u16() == 405) {
            let _ = c.post(api(origin, "/api/logout")).bearer_auth(token).send().await;
        }
    }
}
