package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
)

func TestProxyHeaders(t *testing.T) {
	var got http.Header
	var host string
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got, host = r.Header.Clone(), r.Host
		_, _ = io.WriteString(w, "ok")
	}))
	defer up.Close()
	u, _ := url.Parse(up.URL)
	front := httptest.NewServer(newProxy(u))
	defer front.Close()
	req, _ := http.NewRequest("GET", front.URL+"/api/hello", nil)
	req.Host = "madalean.example.ts.net"
	req.Header.Set("X-Forwarded-Host", "evil.example")
	req.Header.Set("X-Forwarded-Proto", "http")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if host != "madalean.example.ts.net" {
		t.Errorf("Host not preserved: %q", host)
	}
	if got.Get("X-Forwarded-Host") != "madalean.example.ts.net" || got.Get("X-Forwarded-Proto") != "https" {
		t.Errorf("forwarded headers: %v", got)
	}
	if strings.Contains(strings.Join(got.Values("X-Forwarded-Host"), ","), "evil") {
		t.Errorf("client X-Forwarded-Host leaked")
	}
}

func TestProxyWebSocketUpgrade(t *testing.T) {
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Upgrade") != "websocket" {
			http.Error(w, "no upgrade", 400)
			return
		}
		hj, _ := w.(http.Hijacker)
		c, rw, _ := hj.Hijack()
		defer c.Close()
		_, _ = rw.WriteString("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
		_ = rw.Flush()
		line, _ := rw.ReadString('\n')
		_, _ = rw.WriteString("echo:" + line)
		_ = rw.Flush()
	}))
	defer up.Close()
	u, _ := url.Parse(up.URL)
	front := httptest.NewServer(newProxy(u))
	defer front.Close()
	c, err := net.Dial("tcp", strings.TrimPrefix(front.URL, "http://"))
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	_, _ = io.WriteString(c, "GET /api/ws HTTP/1.1\r\nHost: madalean.x.ts.net\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n")
	br := bufio.NewReader(c)
	resp, err := http.ReadResponse(br, nil)
	if err != nil || resp.StatusCode != 101 {
		t.Fatalf("upgrade failed: %v %v", err, resp)
	}
	_, _ = io.WriteString(c, "hi\n")
	line, _ := br.ReadString('\n')
	if line != "echo:hi\n" {
		t.Fatalf("tunnel: %q", line)
	}
}

func TestStatusLinesOnlyOnChange(t *testing.T) {
	var buf bytes.Buffer
	s := &state{out: &buf, st: Status{Event: "status", State: "starting"}}
	s.update(func(*Status) {})
	s.update(func(*Status) {})
	s.update(func(x *Status) { x.State = "needs_login"; x.AuthURL = "https://login.tailscale.com/a/x" })
	lines := strings.Split(strings.TrimSpace(buf.String()), "\n")
	if len(lines) != 2 {
		t.Fatalf("want 2 lines, got %d: %q", len(lines), buf.String())
	}
	var st Status
	if err := json.Unmarshal([]byte(lines[1]), &st); err != nil || st.AuthURL == "" {
		t.Fatalf("bad line %q", lines[1])
	}
}

func TestNoFunnelInSource(t *testing.T) {
	b, _ := os.ReadFile("main.go")
	for _, bad := range []string{"ListenFunnel(", "FunnelOnly", "SetServeConfig"} {
		if bytes.Contains(b, []byte(bad)) {
			t.Fatalf("forbidden call %s", bad)
		}
	}
}
