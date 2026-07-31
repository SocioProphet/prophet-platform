// wordops-room-factory — creates governed Matrix rooms (Go, stdlib-only).
//
// Implements the room-factory named in the WordOps reference flow: a dedicated
// service account that opens PRIVATE case/incident rooms in the private Synapse
// estate with the taxonomy from docs/room-taxonomy.md — encryption ON, join by
// invite only, federation OFF. Rooms are collaboration context; the durable
// authorization record lives in the ledger/case-kernel, never in the room.
//
// Endpoints (bind 0.0.0.0:$PORT, default 8080):
//
//	GET  /healthz — liveness/readiness
//	POST /rooms   — create an incident/case room and invite participants
//
// Config: MATRIX_HS_URL (private homeserver base, e.g. https://ops.socioprophet.ai)
// and MATRIX_ACCESS_TOKEN (the room-factory service-account token).
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

type createReq struct {
	Type     string   `json:"type"`     // "incident" | "case"
	Ref      string   `json:"ref"`      // e.g. INC-123 / CASE-9
	Topic    string   `json:"topic"`    // optional
	Invitees []string `json:"invitees"` // Matrix user ids
}

// roomSpec is the Matrix CS-API createRoom body. The taxonomy (encryption, invite,
// no federation) is NOT caller-controlled — it is fixed by room type so a private
// case room can never be opened federated or unencrypted by a bad request.
func roomSpec(req createReq) (map[string]any, string, error) {
	if req.Type != "incident" && req.Type != "case" {
		return nil, "", fmt.Errorf("type must be incident|case")
	}
	if strings.TrimSpace(req.Ref) == "" {
		return nil, "", fmt.Errorf("ref is required")
	}
	alias := req.Type + "-" + sanitize(req.Ref)
	name := "#" + alias
	topic := req.Topic
	if topic == "" {
		topic = fmt.Sprintf("WordOps %s room for %s (private, encrypted, invite-only)", req.Type, req.Ref)
	}
	spec := map[string]any{
		"preset":          "private_chat",
		"visibility":      "private",
		"name":            name,
		"topic":           topic,
		"room_alias_name": alias,
		"invite":          req.Invitees,
		// federation OFF — a private case/incident room must never federate.
		"creation_content": map[string]any{"m.federate": false},
		"initial_state": []map[string]any{
			{"type": "m.room.encryption", "state_key": "", "content": map[string]any{"algorithm": "m.megolm.v1.aes-sha2"}},
			{"type": "m.room.join_rules", "state_key": "", "content": map[string]any{"join_rule": "invite"}},
			{"type": "m.room.history_visibility", "state_key": "", "content": map[string]any{"history_visibility": "invited"}},
			{"type": "m.room.guest_access", "state_key": "", "content": map[string]any{"guest_access": "forbidden"}},
		},
	}
	return spec, alias, nil
}

func sanitize(s string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(s) {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
		case r == '-' || r == '_' || r == '.':
			b.WriteRune(r)
		default:
			b.WriteRune('-')
		}
	}
	return b.String()
}

type factory struct {
	hsURL  string
	token  string
	client *http.Client
}

func (f *factory) createRoom(spec map[string]any) (string, error) {
	body, _ := json.Marshal(spec)
	req, _ := http.NewRequest(http.MethodPost, strings.TrimRight(f.hsURL, "/")+"/_matrix/client/v3/createRoom", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+f.token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := f.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	rb, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("homeserver createRoom returned %d: %s", resp.StatusCode, string(rb))
	}
	var out struct {
		RoomID string `json:"room_id"`
	}
	if err := json.Unmarshal(rb, &out); err != nil || out.RoomID == "" {
		return "", fmt.Errorf("homeserver did not return a room_id")
	}
	return out.RoomID, nil
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func (f *factory) handleRooms(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", "POST")
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "method not allowed"})
		return
	}
	var req createReq
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid JSON: " + err.Error()})
		return
	}
	spec, alias, err := roomSpec(req)
	if err != nil {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]any{"error": err.Error()})
		return
	}
	roomID, err := f.createRoom(spec)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"room_id": roomID, "alias": alias, "type": req.Type,
		"encrypted": true, "federated": false, "join_rule": "invite",
		"invited": req.Invitees, "created_at": time.Now().UTC().Format(time.RFC3339),
	})
}

func (f *factory) mux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "wordops-room-factory"})
	})
	mux.HandleFunc("/rooms", f.handleRooms)
	return mux
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func main() {
	f := &factory{
		hsURL:  env("MATRIX_HS_URL", "http://synapse-private.socioprophet.svc.cluster.local:8008"),
		token:  os.Getenv("MATRIX_ACCESS_TOKEN"),
		client: &http.Client{Timeout: 10 * time.Second},
	}
	if f.token == "" {
		log.Printf("WARNING: MATRIX_ACCESS_TOKEN is empty — createRoom will be rejected by the homeserver")
	}
	port := env("PORT", "8080")
	log.Printf("wordops-room-factory serving on :%s (hs=%s)", port, f.hsURL)
	if err := http.ListenAndServe("0.0.0.0:"+port, f.mux()); err != nil {
		log.Fatal(err)
	}
}
