server_name: "${WORDOPS_PRIVATE_SERVER_NAME}"
public_baseurl: "${WORDOPS_PRIVATE_BASE_URL}/"
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
    user: "${WORDOPS_PRIVATE_DB_USER}"
    password: "${WORDOPS_PRIVATE_DB_PASSWORD}"
    database: "${WORDOPS_PRIVATE_DB_NAME}"
    host: postgres-private
    cp_min: 5
    cp_max: 10

log_config: /data/log.config
media_store_path: /data/media_store
signing_key_path: /data/${WORDOPS_PRIVATE_SERVER_NAME}.signing.key

registration_shared_secret: "change-private-registration-secret"
enable_registration: ${WORDOPS_PRIVATE_ENABLE_REGISTRATION}

report_stats: false
default_room_version: "12"
allow_public_rooms_without_auth: false
allow_public_rooms_over_federation: false
