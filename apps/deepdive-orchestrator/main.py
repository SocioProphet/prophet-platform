from fastapi import FastAPI, Response
from pathlib import Path
import importlib.util


def _load_local(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


contracts = _load_local('contracts.py')
receipt_emit = _load_local('receipt_emit.py')
DeepDiveRunRequest = contracts.DeepDiveRunRequest
DeepDiveFinding = contracts.DeepDiveFinding
DeepDiveRunResponse = contracts.DeepDiveRunResponse
maybe_emit_receipt = receipt_emit.maybe_emit_receipt

app = FastAPI(title='deepdive-orchestrator')


def _attach_refs(response: Response, emission: dict | None) -> None:
    if not emission:
        return
    response.headers['X-Payload-Ref'] = emission['payload_ref']
    response.headers['X-Evidence-Receipt-Ref'] = emission['receipt_ref']


@app.get('/health')
def health() -> dict:
    return {'service': 'deepdive-orchestrator', 'status': 'ok'}


@app.get('/v1/deepdive/modes')
def modes() -> dict:
    return {
        'service': 'deepdive-orchestrator',
        'modes': [
            'repo_deepdive_report',
            'environment_deepdive_report',
            'artifact_release_deepdive_report',
            'room_controlplane_deepdive_report',
            'case_deepdive_report',
        ],
    }


@app.post('/v1/deepdive/run', response_model=DeepDiveRunResponse)
def run_deepdive(request: DeepDiveRunRequest, response: Response) -> object:
    result = DeepDiveRunResponse(
        service='deepdive-orchestrator',
        mode=request.mode,
        subject_ref=request.subject_ref,
        findings=[
            DeepDiveFinding(
                title=f'{request.mode} assessment prepared',
                severity='info',
                evidence_refs=[request.subject_ref],
            )
        ],
        trace_required=True,
        evidence_required=True,
    )
    emission = maybe_emit_receipt(
        event_type='deepdive.run',
        subject_ref=request.subject_ref,
        payload=result.model_dump(),
    )
    _attach_refs(response, emission)
    return result
