from fastapi import FastAPI

app = FastAPI(title='deepdive-orchestrator')

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
