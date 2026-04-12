from fastapi import FastAPI

app = FastAPI(title='dashboard-bff')

@app.get('/health')
def health() -> dict:
    return {'service': 'dashboard-bff', 'status': 'ok'}

@app.get('/v1/overview')
def overview() -> dict:
    return {
        'service': 'dashboard-bff',
        'views': ['overview', 'deepdive', 'cases'],
    }
