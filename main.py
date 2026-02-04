from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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


class SearchRequest(BaseModel):
    query: str


@app.get("/")
def read_root():
    return {"message": "Kilterboard API"}


@app.post("/search")
def search_problems(request: SearchRequest):
    """
    BoardLib를 사용하여 킬터보드 문제 검색
    """
    results = boardlib.api.query(
        table_name="climbs",
        filters=[("name", "like", f"%{request.query}%")],
    )
    return {"query": request.query, "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
