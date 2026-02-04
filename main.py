from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

app = FastAPI(title="Kilterboard API")

# CORS 설정 - 모든 origin 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLite 데이터베이스 경로
DB_PATH = Path("./kilter.db")


def get_db_connection() -> sqlite3.Connection:
    """SQLite 데이터베이스 연결获取"""
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database not found. Please run: boardlib database kilter ./kilter.db --username <your_username>"
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def read_root():
    return {"message": "Kilterboard API"}


@app.get("/search")
def search_problems(query: str, limit: int = 50):
    """
    SQLite 데이터베이스에서 문제 검색

    Args:
        query: 검색어 (이름)
        limit: 최대 결과 개수 (기본값: 50)
    """
    if not query or len(query.strip()) == 0:
        return {"query": query, "results": [], "count": 0}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # climbs 테이블에서 이름으로 검색 (climb_stats와 조인)
        search_pattern = f"%{query}%"
        cursor.execute(
            """
            SELECT
                c.uuid,
                c.name,
                c.angle,
                c.setter_username,
                c.created_at,
                cs.display_difficulty,
                cs.benchmark_difficulty,
                cs.ascensionist_count,
                dg.boulder_name,
                dg.route_name
            FROM climbs c
            LEFT JOIN climb_stats cs ON c.uuid = cs.climb_uuid
            LEFT JOIN difficulty_grades dg ON CAST(cs.display_difficulty AS INT) = dg.difficulty
            WHERE c.name LIKE ?
            ORDER BY c.created_at DESC
            LIMIT ?
            """,
            (search_pattern, limit)
        )

        rows = cursor.fetchall()
        conn.close()

        results = [
            {
                "uuid": row["uuid"],
                "name": row["name"],
                "angle": row["angle"],
                "setter": row["setter_username"],
                "created_at": row["created_at"],
                "display_difficulty": row["display_difficulty"],
                "benchmark_difficulty": row["benchmark_difficulty"],
                "ascensionist_count": row["ascensionist_count"],
                "boulder_grade": row["boulder_name"],
                "route_grade": row["route_name"],
            }
            for row in rows
        ]

        return {"query": query, "results": results, "count": len(results)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


@app.get("/climb/{climb_uuid}")
def get_climb(climb_uuid: str):
    """
    UUID로 특정 문제 조회
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                c.uuid,
                c.name,
                c.description,
                c.angle,
                c.setter_username,
                c.created_at,
                c.layout_id,
                c.frames,
                cs.display_difficulty,
                cs.benchmark_difficulty,
                cs.ascensionist_count,
                cs.quality_average,
                dg.boulder_name,
                dg.route_name
            FROM climbs c
            LEFT JOIN climb_stats cs ON c.uuid = cs.climb_uuid
            LEFT JOIN difficulty_grades dg ON CAST(cs.display_difficulty AS INT) = dg.difficulty
            WHERE c.uuid = ?
            """,
            (climb_uuid,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            raise HTTPException(status_code=404, detail="Climb not found")

        return {
            "uuid": row["uuid"],
            "name": row["name"],
            "description": row["description"],
            "angle": row["angle"],
            "setter": row["setter_username"],
            "created_at": row["created_at"],
            "layout_id": row["layout_id"],
            "frames": row["frames"],
            "display_difficulty": row["display_difficulty"],
            "benchmark_difficulty": row["benchmark_difficulty"],
            "ascensionist_count": row["ascensionist_count"],
            "quality_average": row["quality_average"],
            "boulder_grade": row["boulder_name"],
            "route_grade": row["route_name"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


@app.get("/health")
def health_check():
    """데이터베이스 상태 확인"""
    db_exists = DB_PATH.exists()
    db_size = DB_PATH.stat().st_size if db_exists else 0

    total_climbs = 0
    if db_exists:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM climbs")
            total_climbs = cursor.fetchone()[0]
            conn.close()
        except:
            pass

    return {
        "status": "healthy" if db_exists else "unhealthy",
        "database_exists": db_exists,
        "database_path": str(DB_PATH),
        "database_size_mb": round(db_size / (1024 * 1024), 2),
        "total_climbs": total_climbs
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
