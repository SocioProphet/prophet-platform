package binding

import (
    "crypto/rand"
    "encoding/binary"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net"
    "os"
    "strings"

    "github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge/tritrpcv1"
    "golang.org/x/crypto/chacha20poly1305"
)

const (
    HealthService       = "platform.health.v1"
    HealthPingReq       = "Health.Ping.REQ"
    HealthPingRes       = "Health.Ping.RES"
    ValidateChangeService = "platform.validate_change.v2"
    ValidateChangeReq     = "ValidateChange.Environment.REQ"
    ValidateChangeRes     = "ValidateChange.Environment.RES"
    NonceSize           = chacha20poly1305.NonceSizeX
    recordHeaderSize    = 4 + NonceSize
    MaxFrameBytes       = 1 << 20
)

var (
    ErrShortRecord     = errors.New("tritrpcbridge: short record")
    ErrFrameTooLarge   = errors.New("tritrpcbridge: frame too large")
    ErrInvalidKeyHex   = errors.New("tritrpcbridge: invalid TRITRPC_KEY_HEX")
    ErrMissingSharedKey = errors.New("tritrpcbridge: missing shared key (set TRITRPC_KEY_HEX or opt into TRITRPC_ALLOW_INSECURE_DEV_KEY=1)")
)

type HealthPingRequest struct {
    TsUnixMs int64 `json:"ts_unix_ms"`
}

type HealthPingResponse struct {
    Ok      bool   `json:"ok"`
    Pong    string `json:"pong"`
    Service string `json:"service"`
}

func ParseKeyHex(keyHex string) ([32]byte, error) {
    var key [32]byte
    raw, err := hex.DecodeString(strings.TrimSpace(keyHex))
    if err != nil || len(raw) != len(key) {
        return key, ErrInvalidKeyHex
    }
    copy(key[:], raw)
    return key, nil
}

func DefaultDevKey() [32]byte {
    var key [32]byte
    for i := range key {
        key[i] = byte(i)
    }
    return key
}

func ResolveSharedKey(keyHex string, allowInsecureDev bool) ([32]byte, error) {
    if strings.TrimSpace(keyHex) != "" {
        return ParseKeyHex(keyHex)
    }
    if allowInsecureDev {
        return DefaultDevKey(), nil
    }
    return [32]byte{}, ErrMissingSharedKey
}

func MarshalJSONFrame(service, method string, payload any, key [32]byte) (nonce [24]byte, frame []byte, err error) {
    payloadBytes, err := json.Marshal(payload)
    if err != nil {
        return nonce, nil, err
    }
    if _, err = rand.Read(nonce[:]); err != nil {
        return nonce, nil, err
    }
    frame, _, err = tritrpcv1.EnvelopeWithTag(service, method, payloadBytes, nil, key, nonce)
    return nonce, frame, err
}

func VerifyEnvelope(frame []byte, nonce [24]byte, key [32]byte) (*tritrpcv1.Envelope, error) {
    env, err := tritrpcv1.DecodeEnvelope(frame)
    if err != nil {
        return nil, err
    }
    aad, err := tritrpcv1.AADBeforeTag(frame, env)
    if err != nil {
        return nil, err
    }
    if !env.AeadOn {
        return nil, errors.New("tritrpcbridge: AEAD must be enabled")
    }
    aead, err := chacha20poly1305.NewX(key[:])
    if err != nil {
        return nil, err
    }
    if _, err := aead.Open(nil, nonce[:], env.Tag, aad); err != nil {
        return nil, fmt.Errorf("tritrpcbridge: tag verification failed: %w", err)
    }
    return env, nil
}

func DecodeJSONPayload(env *tritrpcv1.Envelope, out any) error {
    return json.Unmarshal(env.Payload, out)
}

func WriteRecord(w io.Writer, nonce [24]byte, frame []byte) error {
    if len(frame) > MaxFrameBytes {
        return ErrFrameTooLarge
    }
    hdr := make([]byte, recordHeaderSize)
    binary.BigEndian.PutUint32(hdr[:4], uint32(len(frame)))
    copy(hdr[4:], nonce[:])
    if _, err := w.Write(hdr); err != nil {
        return err
    }
    _, err := w.Write(frame)
    return err
}

func ReadRecord(r io.Reader) (nonce [24]byte, frame []byte, err error) {
    hdr := make([]byte, recordHeaderSize)
    if _, err = io.ReadFull(r, hdr); err != nil {
        return nonce, nil, err
    }
    size := binary.BigEndian.Uint32(hdr[:4])
    if size == 0 {
        return nonce, nil, ErrShortRecord
    }
    if size > MaxFrameBytes {
        return nonce, nil, ErrFrameTooLarge
    }
    copy(nonce[:], hdr[4:])
    frame = make([]byte, int(size))
    _, err = io.ReadFull(r, frame)
    return nonce, frame, err
}

func ParseEndpoint(raw string, fallbackUnixPath string) (network, address string, err error) {
    raw = strings.TrimSpace(raw)
    if raw == "" {
        if fallbackUnixPath == "" {
            return "", "", errors.New("tritrpcbridge: empty endpoint")
        }
        return "unix", fallbackUnixPath, nil
    }
    switch {
    case strings.HasPrefix(raw, "unix://"):
        return "unix", strings.TrimPrefix(raw, "unix://"), nil
    case strings.HasPrefix(raw, "tcp://"):
        return "tcp", strings.TrimPrefix(raw, "tcp://"), nil
    case strings.HasPrefix(raw, "/"):
        return "unix", raw, nil
    default:
        return "tcp", raw, nil
    }
}

func Listen(raw string, fallbackUnixPath string) (net.Listener, string, error) {
    network, address, err := ParseEndpoint(raw, fallbackUnixPath)
    if err != nil {
        return nil, "", err
    }
    if network == "unix" {
        _ = osRemove(address)
    }
    ln, err := net.Listen(network, address)
    if err != nil {
        return nil, "", err
    }
    return ln, fmt.Sprintf("%s://%s", network, address), nil
}

func Dial(raw string, fallbackUnixPath string) (net.Conn, string, error) {
    network, address, err := ParseEndpoint(raw, fallbackUnixPath)
    if err != nil {
        return nil, "", err
    }
    c, err := net.Dial(network, address)
    if err != nil {
        return nil, "", err
    }
    return c, fmt.Sprintf("%s://%s", network, address), nil
}

var osRemove = os.Remove
