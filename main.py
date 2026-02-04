from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import boardlib

app = FastAPI(title="Kilterboard API")

# CORS 설정 - 모든 origin 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Kilterboard API"}


@app.get("/search")
def search_problems(query: str):
    """
    BoardLib를 사용하여 킬터보드 문제 검색
    """
    results = boardlib.api.query(
        table_name="climbs",
        filters=[("name", "like", f"%{query}%")],
    )
    return {"query": query, "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
