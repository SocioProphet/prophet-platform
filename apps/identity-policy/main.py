from fastapi import FastAPI

app = FastAPI(title='identity-policy')

@app.get('/health')
def health() -> dict:
    return {'service': 'identity-policy', 'status': 'ok'}

@app.get('/ready')
def ready() -> dict:
    return {'service': 'identity-policy', 'ready': True}
