package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
)

func main() {
	sock := getenv("TRITRPC_SOCK", "/tmp/socioprophet.sock")
	port := getenv("GATEWAY_PORT", "8080")
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		pong, err := ping(sock)
		if err != nil {
			log.Printf("PING error: %v", err)
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "pong": pong})
	})
	log.Printf("Gateway listening on :%s (→ %s)", port, sock)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func ping(sock string) (string, error) {
	c, err := net.Dial("unix", sock)
	if err != nil { return "", err }
	defer c.Close()
	if _, err = io.WriteString(c, "PING\n"); err != nil { return "", err }
	buf := make([]byte, 64)
	n, err := c.Read(buf)
	if err != nil { return "", err }
	return string(buf[:n]), nil
}

func getenv(k, d string) string {
	if v := os.Getenv(k); v != "" { return v }
	return d
}
