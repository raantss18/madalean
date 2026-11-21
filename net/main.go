// madalean-net — Madalean's embedded Tailscale node (ARCHITECTURE §18).
//
// One static binary (CGO_ENABLED=0) started by the Madalean server (madalean/runtime/net.py). It joins the user's
// tailnet as its own node (default hostname "madalean", state in --state-dir inside MADALEAN_HOME), serves HTTPS on
// :443 of the tailnet address with the certificate Tailscale issues for <hostname>.<tailnet>.ts.net (ListenTLS), and
// reverse-proxies every request (WebSocket upgrades included) to the server's REMOTE listener (default
// 127.0.0.1:11501), which still requires a device token for everything. Plain HTTP on :80 of the tailnet address only
// redirects to HTTPS.
//
// No log upload: TS_NO_LOGS_NO_SUPPORT is forced and logtail is disabled (no telemetry).
//
// Never Funnel: this program never calls ListenFunnel and never changes serve/funnel configuration — the node is
// reachable from the user's own tailnet only. It does not touch the host's tailscaled (if one runs, both coexist).
//
// Status: one JSON object per line on stdout whenever the state changes ({"event":"status",...}); the same object is
// served on a local unix socket (--status-socket, mode 0600): `GET /status`. `madalean-net status --status-socket S`
// prints it. The process exits when its parent dies (PR_SET_PDEATHSIG + parent polling) or on SIGTERM/SIGINT.
package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"runtime/debug"
	"strings"
	"sync"
	"syscall"
	"time"

	"golang.org/x/sys/unix"
	"tailscale.com/logtail"
	"tailscale.com/tsnet"
)

// Version of madalean-net itself (the Tailscale library version is reported separately).
const Version = "0.1.0"

// tsVersion is the version of the tailscale.com module compiled in (from the build info).
func tsVersion() string {
	if bi, ok := debug.ReadBuildInfo(); ok {
		for _, d := range bi.Deps {
			if d.Path == "tailscale.com" {
				return strings.TrimPrefix(d.Version, "v")
			}
		}
	}
	return "unknown"
}

// Status is what the Madalean server shows in the UI (login URL when the node must be authorised).
type Status struct {
	Event        string   `json:"event"`
	State        string   `json:"state"` // starting | needs_login | needs_machine_auth | running | stopped | error
	BackendState string   `json:"backend_state,omitempty"`
	AuthURL      string   `json:"auth_url,omitempty"`
	Hostname     string   `json:"hostname"`
	DNSName      string   `json:"dns_name,omitempty"` // madalean.<tailnet>.ts.net
	Tailnet      string   `json:"tailnet,omitempty"`
	IPs          []string `json:"ips,omitempty"`
	URL          string   `json:"url,omitempty"` // https://<dns_name>/
	CertOK       bool     `json:"cert_ok"`
	CertError    string   `json:"cert_error,omitempty"`
	ListenError  string   `json:"listen_error,omitempty"`
	Error        string   `json:"error,omitempty"`
	Target       string   `json:"target"`
	Version      string   `json:"version"`
	TSVersion    string   `json:"tailscale_version"`
	PID          int      `json:"pid"`
	Time         int64    `json:"t"`
}

type state struct {
	mu  sync.Mutex
	st  Status
	out io.Writer
}

func (s *state) update(f func(*Status)) {
	s.mu.Lock()
	defer s.mu.Unlock()
	prev := s.st
	prev.Time = 0
	f(&s.st)
	next := s.st
	next.Time = 0
	a, _ := json.Marshal(prev)
	b, _ := json.Marshal(next)
	if string(a) == string(b) && s.st.Time != 0 {
		return
	}
	s.st.Time = time.Now().Unix()
	line, _ := json.Marshal(s.st)
	fmt.Fprintln(s.out, string(line))
}

func (s *state) get() Status {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.st
}

// cappedLog writes tsnet's (verbose) log to a file and truncates it when it grows past max bytes.
type cappedLog struct {
	mu  sync.Mutex
	f   *os.File
	n   int64
	max int64
}

func (c *cappedLog) Logf(format string, args ...any) {
	if c == nil || c.f == nil {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	line := time.Now().Format(time.RFC3339) + " " + fmt.Sprintf(format, args...)
	if !strings.HasSuffix(line, "\n") {
		line += "\n"
	}
	if c.n+int64(len(line)) > c.max {
		_ = c.f.Truncate(0)
		_, _ = c.f.Seek(0, 0)
		c.n = 0
	}
	k, _ := c.f.WriteString(line)
	c.n += int64(k)
}

// newProxy forwards to the remote listener, keeping the original Host (the server checks Origin against it) and
// setting X-Forwarded-{For,Host,Proto}. Client-supplied X-Forwarded-* headers are dropped by Rewrite.
func newProxy(target *url.URL) *httputil.ReverseProxy {
	return &httputil.ReverseProxy{
		Rewrite: func(r *httputil.ProxyRequest) {
			r.SetURL(target)
			r.Out.Host = r.In.Host
			r.SetXForwarded()
			r.Out.Header.Set("X-Forwarded-Proto", "https")
			r.Out.Header.Set("X-Forwarded-Host", r.In.Host)
		},
		FlushInterval: -1, // stream (server-sent tokens, large exports) without buffering
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_, _ = w.Write([]byte(`{"error":"madalean_unreachable"}`))
		},
	}
}

func securityHeaders(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Strict-Transport-Security", "max-age=31536000")
		h.ServeHTTP(w, r)
	})
}

func redirectHTTPS(w http.ResponseWriter, r *http.Request) {
	host := r.Host
	if h, _, err := net.SplitHostPort(host); err == nil {
		host = h
	}
	http.Redirect(w, r, "https://"+host+r.URL.RequestURI(), http.StatusMovedPermanently)
}

// watchParent: exit when the parent (the Madalean server) dies, even after `kill -9` of the parent.
func watchParent(parent int, stop func(string)) {
	_ = unix.Prctl(unix.PR_SET_PDEATHSIG, uintptr(syscall.SIGTERM), 0, 0, 0)
	if parent <= 0 {
		parent = os.Getppid()
	}
	if os.Getppid() != parent {
		stop("parent already gone")
		return
	}
	go func() {
		for {
			time.Sleep(time.Second)
			if os.Getppid() != parent {
				stop("parent died")
				return
			}
		}
	}()
}

func serveStatus(path string, s *state) (func(), error) {
	if path == "" {
		return func() {}, nil
	}
	_ = os.Remove(path)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, err
	}
	old := unix.Umask(0o177)
	ln, err := net.Listen("unix", path)
	unix.Umask(old)
	if err != nil {
		return nil, err
	}
	_ = os.Chmod(path, 0o600)
	mux := http.NewServeMux()
	mux.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(s.get())
	})
	srv := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go func() { _ = srv.Serve(ln) }()
	return func() { _ = srv.Close(); _ = os.Remove(path) }, nil
}

func statusClient(sock string) int {
	c := &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{
		DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
			var d net.Dialer
			return d.DialContext(ctx, "unix", sock)
		}}}
	resp, err := c.Get("http://madalean-net/status")
	if err != nil {
		fmt.Fprintln(os.Stderr, "madalean-net:", err)
		return 1
	}
	defer resp.Body.Close()
	_, _ = io.Copy(os.Stdout, resp.Body)
	return 0
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "version" {
		fmt.Printf("madalean-net %s (tailscale %s)\n", Version, tsVersion())
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "status" {
		fs := flag.NewFlagSet("status", flag.ExitOnError)
		sock := fs.String("status-socket", "", "unix socket of the running sidecar")
		_ = fs.Parse(os.Args[2:])
		os.Exit(statusClient(*sock))
	}
	var (
		stateDir   = flag.String("state-dir", "", "Tailscale state directory (inside MADALEAN_HOME)")
		hostname   = flag.String("hostname", "madalean", "node name on the tailnet")
		target     = flag.String("target", "127.0.0.1:11501", "Madalean remote listener (loopback only)")
		statusSock = flag.String("status-socket", "", "unix socket serving GET /status (0600)")
		logFile    = flag.String("log-file", "", "tsnet log file (capped at 4 MB); empty = discard")
		controlURL = flag.String("control-url", "", "coordination server (empty = Tailscale's; tests/headscale)")
		parentPID  = flag.Int("parent-pid", 0, "exit when this process is no longer our parent (0 = current parent)")
		httpsPort  = flag.Int("https-port", 443, "tailnet port for HTTPS")
		noHTTP     = flag.Bool("no-http-redirect", false, "do not listen on :80 for the HTTPS redirect")
		ephemeral  = flag.Bool("ephemeral", false, "register as an ephemeral node (tests)")
	)
	flag.Parse()
	// No telemetry (ARCHITECTURE §4): never upload Tailscale client logs to log.tailscale.com.
	_ = os.Setenv("TS_NO_LOGS_NO_SUPPORT", "true")
	logtail.Disable()
	if *stateDir == "" {
		log.Fatal("madalean-net: --state-dir is required")
	}
	th, tp, err := net.SplitHostPort(*target)
	if err != nil || tp == "" {
		log.Fatalf("madalean-net: bad --target %q", *target)
	}
	if ip := net.ParseIP(th); th != "localhost" && (ip == nil || !ip.IsLoopback()) {
		log.Fatalf("madalean-net: --target must be a loopback address, got %q", *target)
	}
	if err := os.MkdirAll(*stateDir, 0o700); err != nil {
		log.Fatal(err)
	}
	_ = os.Chmod(*stateDir, 0o700)

	st := &state{out: os.Stdout, st: Status{Event: "status", State: "starting", Hostname: *hostname,
		Target: *target, Version: Version, TSVersion: tsVersion(), PID: os.Getpid()}}
	st.update(func(s *Status) {})

	ctx, cancel := context.WithCancel(context.Background())
	var stopOnce sync.Once
	stop := func(why string) {
		stopOnce.Do(func() {
			st.update(func(s *Status) { s.State = "stopped"; s.Error = why })
			cancel()
		})
	}
	watchParent(*parentPID, stop)
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGTERM, syscall.SIGINT, syscall.SIGHUP)
	go func() { s := <-sigs; stop("signal " + s.String()) }()

	closeStatus, err := serveStatus(*statusSock, st)
	if err != nil {
		log.Fatalf("madalean-net: status socket: %v", err)
	}
	defer closeStatus()

	var tl *cappedLog
	if *logFile != "" {
		f, err := os.OpenFile(*logFile, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o600)
		if err == nil {
			tl = &cappedLog{f: f, max: 4 << 20}
			defer f.Close()
		}
	}
	srv := &tsnet.Server{
		Hostname:   *hostname,
		Dir:        *stateDir,
		ControlURL: *controlURL,
		Ephemeral:  *ephemeral,
		Logf:       tl.Logf,
		UserLogf:   tl.Logf,
		// AuthKey: read by tsnet from TS_AUTHKEY when set by the user; Madalean never sets it.
	}
	defer srv.Close()
	if err := srv.Start(); err != nil {
		st.update(func(s *Status) { s.State = "error"; s.Error = err.Error() })
		<-ctx.Done()
		return
	}
	lc, err := srv.LocalClient()
	if err != nil {
		st.update(func(s *Status) { s.State = "error"; s.Error = err.Error() })
		<-ctx.Done()
		return
	}

	turl := &url.URL{Scheme: "http", Host: *target}
	handler := securityHeaders(newProxy(turl))
	var listenOnce sync.Once
	startListeners := func(domain string) {
		listenOnce.Do(func() {
			ln, err := srv.ListenTLS("tcp", fmt.Sprintf(":%d", *httpsPort))
			if err != nil {
				st.update(func(s *Status) { s.ListenError = err.Error() })
				return
			}
			hs := &http.Server{Handler: handler, ReadHeaderTimeout: 20 * time.Second,
				TLSConfig: &tls.Config{MinVersion: tls.VersionTLS12}}
			go func() { _ = hs.Serve(ln) }()
			go func() { <-ctx.Done(); _ = hs.Close() }()
			if !*noHTTP {
				if l80, err := srv.Listen("tcp", ":80"); err == nil {
					rs := &http.Server{Handler: http.HandlerFunc(redirectHTTPS), ReadHeaderTimeout: 10 * time.Second}
					go func() { _ = rs.Serve(l80) }()
					go func() { <-ctx.Done(); _ = rs.Close() }()
				}
			}
			// Ask for the certificate once now, so the UI can say whether HTTPS works (tailnet setting
			// "HTTPS certificates" must be enabled by the tailnet admin).
			go func() {
				cctx, ccancel := context.WithTimeout(ctx, 90*time.Second)
				defer ccancel()
				_, _, err := lc.CertPair(cctx, domain)
				st.update(func(s *Status) {
					s.CertOK = err == nil
					if err != nil {
						s.CertError = err.Error()
					} else {
						s.CertError = ""
					}
				})
			}()
		})
	}

	tick := time.NewTicker(1500 * time.Millisecond)
	defer tick.Stop()
	for {
		sctx, scancel := context.WithTimeout(ctx, 10*time.Second)
		s, err := lc.StatusWithoutPeers(sctx)
		scancel()
		if err != nil && !errors.Is(err, context.Canceled) {
			st.update(func(x *Status) { x.Error = err.Error() })
		} else if s != nil {
			domain := ""
			if s.Self != nil {
				domain = strings.TrimSuffix(s.Self.DNSName, ".")
			}
			var ips []string
			for _, ip := range s.TailscaleIPs {
				ips = append(ips, ip.String())
			}
			stName := "starting"
			switch s.BackendState {
			case "NeedsLogin":
				stName = "needs_login"
			case "NeedsMachineAuth":
				stName = "needs_machine_auth"
			case "Running":
				stName = "running"
			case "Stopped":
				stName = "stopped"
			}
			tailnet := ""
			if s.CurrentTailnet != nil {
				tailnet = s.CurrentTailnet.Name
			}
			st.update(func(x *Status) {
				x.State, x.BackendState, x.AuthURL, x.Error = stName, s.BackendState, s.AuthURL, ""
				x.DNSName, x.Tailnet, x.IPs = domain, tailnet, ips
				if domain != "" {
					x.URL = "https://" + domain + "/"
					if *httpsPort != 443 {
						x.URL = fmt.Sprintf("https://%s:%d/", domain, *httpsPort)
					}
				}
			})
			if stName == "running" && domain != "" {
				startListeners(domain)
			}
		}
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
		}
	}
}
