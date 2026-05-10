from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.routes import router as rag_router
from app.examples import get_random_examples

app = FastAPI(
    title="MovieGraph API",
    description="API for exploring movie data and recommendations powered by a graph database.",
    version="1.1.0",
)

app.include_router(rag_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/index.html")


@app.get("/api/examples", include_in_schema=False)
def examples():
    return get_random_examples()


app.mount("/ui", StaticFiles(directory="ui"), name="ui")


def main():
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
