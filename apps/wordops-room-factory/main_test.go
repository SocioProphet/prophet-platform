package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// fakeSynapse asserts the createRoom body enforces the taxonomy and returns a room_id.
func fakeSynapse(t *testing.T, gotToken *string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/_matrix/client/v3/createRoom" {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		*gotToken = r.Header.Get("Authorization")
		var spec map[string]any
		_ = json.NewDecoder(r.Body).Decode(&spec)

		// federation OFF
		cc, _ := spec["creation_content"].(map[string]any)
		if cc == nil || cc["m.federate"] != false {
			t.Errorf("federation must be disabled, got creation_content=%v", cc)
		}
		// encryption + invite join rule present in initial_state
		wantState := map[string]bool{"m.room.encryption": false, "m.room.join_rules": false}
		st, _ := spec["initial_state"].([]any)
		for _, e := range st {
			m, _ := e.(map[string]any)
			if _, ok := wantState[m["type"].(string)]; ok {
				wantState[m["type"].(string)] = true
			}
			if m["type"] == "m.room.join_rules" {
				c, _ := m["content"].(map[string]any)
				if c["join_rule"] != "invite" {
					t.Errorf("join_rule must be invite, got %v", c["join_rule"])
				}
			}
		}
		for typ, seen := range wantState {
			if !seen {
				t.Errorf("initial_state missing %s", typ)
			}
		}
		if spec["visibility"] != "private" {
			t.Errorf("visibility must be private, got %v", spec["visibility"])
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]any{"room_id": "!abc123:ops.socioprophet.ai"})
	}))
}

func TestCreateIncidentRoomEnforcesTaxonomy(t *testing.T) {
	var gotToken string
	hs := fakeSynapse(t, &gotToken)
	defer hs.Close()
	f := &factory{hsURL: hs.URL, token: "syt_factory_token", client: hs.Client()}

	body, _ := json.Marshal(createReq{Type: "incident", Ref: "INC-42", Invitees: []string{"@ic:ops.socioprophet.ai"}})
	rr := httptest.NewRecorder()
	f.mux().ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/rooms", bytes.NewReader(body)))
	if rr.Code != http.StatusCreated {
		t.Fatalf("want 201, got %d: %s", rr.Code, rr.Body.String())
	}
	var out map[string]any
	_ = json.Unmarshal(rr.Body.Bytes(), &out)
	if out["room_id"] != "!abc123:ops.socioprophet.ai" || out["alias"] != "incident-inc-42" {
		t.Fatalf("unexpected response: %v", out)
	}
	if out["encrypted"] != true || out["federated"] != false {
		t.Fatalf("response must advertise encrypted + non-federated: %v", out)
	}
	if gotToken != "Bearer syt_factory_token" {
		t.Fatalf("service-account token not forwarded: %q", gotToken)
	}
}

func TestBadTypeRejected(t *testing.T) {
	f := &factory{hsURL: "http://unused", token: "x", client: http.DefaultClient}
	body, _ := json.Marshal(createReq{Type: "public-lobby", Ref: "X"})
	rr := httptest.NewRecorder()
	f.mux().ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/rooms", bytes.NewReader(body)))
	if rr.Code != http.StatusUnprocessableEntity {
		t.Fatalf("want 422 for bad type, got %d", rr.Code)
	}
}

func TestRoomSpecTaxonomyIsFixed(t *testing.T) {
	// Even if a caller tried to smuggle federation on, roomSpec fixes it.
	spec, alias, err := roomSpec(createReq{Type: "case", Ref: "CASE 9!"})
	if err != nil {
		t.Fatal(err)
	}
	if alias != "case-case-9-" {
		t.Fatalf("alias sanitize wrong: %q", alias)
	}
	cc := spec["creation_content"].(map[string]any)
	if cc["m.federate"] != false {
		t.Fatalf("federation must be forced off")
	}
}
