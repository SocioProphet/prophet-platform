# device-service — FOG & CITIZEN PLANE W8.7: the estate's southbound device plane.
# ONE southbound interface, N protocol drivers (EdgeX Foundry's lesson). Devices are
# declared by DeviceProfile and observed as DeviceReading (SourceOS-Linux/sourceos-spec
# v0.1.0, VENDORED and sha256-asserted at import), validated fail-closed against BOTH the
# schema and the profile the reading cites, written to the platform log as
# hellgraph-service graph writes (KKO-typed, quality-labelled), and sealed one receipt
# per batch on the estate spine via compute-gateway POST /v1/compute kind=materialize.
# Never a fifth receipt lineage.
#
# NO RADIO IN THIS IMAGE, deliberately. One driver ships — `virtual` — and its readings
# are SIMULATED, marked as such on the profile, on every reading's policy/risk labels, on
# the graph node, and on /healthz (`simulated_devices`). The real-BLE seam is
# src/device_service/ble.py: the GATT characteristic decoders are real and unit-tested
# against the Bluetooth SIG formats, BleGattDriver is complete against an injected
# transport, and no transport implementation ships. build_driver() REFUSES a ble-gatt
# profile rather than starting a service that polls nothing behind a green /healthz.
#
# python:3.11-slim mirrors apps/market-replay + apps/nugget-extractor. The dependency
# closure is market-replay's exactly — no apt layer, no native toolchain, no radio stack.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src ./src
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "device_service.server:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
