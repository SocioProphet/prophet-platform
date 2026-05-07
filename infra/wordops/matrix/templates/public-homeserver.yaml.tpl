server_name: "${WORDOPS_PUBLIC_SERVER_NAME}"
public_baseurl: "${WORDOPS_PUBLIC_BASE_URL}/"
serve_server_wellknown: true
pid_file: /data/homeserver.pid

listeners:
  - port: 8008
    tls: false
    type: http
    x_forwarded: true
    resources:
      - names: [client, federation]
        compress: false

database:
  name: psycopg2
  args:
    user: "${WORDOPS_PUBLIC_DB_USER}"
    password: "${WORDOPS_PUBLIC_DB_PASSWORD}"
    database: "${WORDOPS_PUBLIC_DB_NAME}"
    host: postgres-public
    cp_min: 5
    cp_max: 10

log_config: /data/log.config
media_store_path: /data/media_store
signing_key_path: /data/${WORDOPS_PUBLIC_SERVER_NAME}.signing.key

registration_shared_secret: "change-public-registration-secret"
enable_registration: ${WORDOPS_PUBLIC_ENABLE_REGISTRATION}

report_stats: false
default_room_version: "12"
allow_public_rooms_without_auth: false
allow_public_rooms_over_federation: false
