# Kilterboard API 트러블슈팅 히스토리

## 개요
이 문서는 Kilterboard API 프로젝트 개발 과정에서 발생한 문제들과 그 해결 과정을 상세히 기록한 것입니다.

---

## 문제 1: `boardlib.api.query()` AttributeError

### 발생 시점
- 날짜: 2026-02-05
- 상황: 초기 구현 후 Render 배포 시

### 에러 메시지
```
AttributeError: module 'boardlib' has no attribute 'api'
```

### 초기 코드
```python
# main.py
import boardlib

@app.get("/search")
def search_problems(query: str):
    results = boardlib.api.query(
        table_name="climbs",
        filters=[("name", "like", f"%{query}%")],
    )
    return {"query": query, "results": results}
```

### 원인 분석
1. **BoardLib의 실제 구조**: BoardLib은 CLI 도구로 설계됨
   - `boardlib database <board> <path>` - 데이터베이스 다운로드
   - `boardlib logbook <board>` - 로그북 다운로드
   - Python 라이브러리 API는 제공하지 않음

2. **문서 확인 결과**:
   ```bash
   $ boardlib --help
   Usage: boardlib [OPTIONS] COMMAND [ARGS]...
   Commands:
     database  Download the climb database
     logbook   Download your logbook entries
     images    Download images
   ```

### 해결 방안 논의

#### 옵션 A: Kilterboard API 직접 호출
```python
import httpx

sync_payload = {
    "client": {...},
    "GET": {"query": {"tables": ["climbs"]}}
}
response = await client.post("https://api.kilterboardapp.com/v1/sync", ...)
```
- **장점**: 추가 DB 파일 불필요
- **단점**: 복잡한 sync API 구조, 인증 필요

#### 옵션 B: SQLite DB 직접 쿼리 (채택)
```python
import sqlite3

conn = sqlite3.connect("kilter.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM climbs WHERE name LIKE ?", (f"%{query}%",))
```
- **장점**: 간단한 SQL 쿼리, 빠름
- **단점**: 173MB DB 파일 필요, 주기적 업데이트 필요

### 최종 구현

#### main.py (SQLite 기반)
```python
from fastapi import FastAPI, HTTPException
import sqlite3
from pathlib import Path

DB_PATH = Path("./kilter.db")

@app.get("/search")
def search_problems(query: str, limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.uuid, c.name, c.angle, c.setter_username,
               cs.display_difficulty, dg.boulder_name
        FROM climbs c
        LEFT JOIN climb_stats cs ON c.uuid = cs.climb_uuid
        LEFT JOIN difficulty_grades dg ON CAST(cs.display_difficulty AS INT) = dg.difficulty
        WHERE c.name LIKE ?
        ORDER BY c.created_at DESC
        LIMIT ?
    """, (f"%{query}%", limit))
    rows = cursor.fetchall()
    conn.close()
    return {"query": query, "results": [dict(row) for row in rows]}
```

#### 데이터베이스 구조 분석
```bash
$ sqlite3 kilter.db ".tables"
climbs           climb_stats      difficulty_grades placements       ...

$ sqlite3 kilter.db "PRAGMA table_info(climbs)"
uuid            TEXT
name            TEXT
angle           INT
setter_username TEXT
created_at      TEXT
layout_id       INT
frames          TEXT
```

---

## 문제 2: Render 배포 시 Database not found (503 Error)

### 발생 시점
- 날짜: 2026-02-05
- 상황: Render에 첫 배포 후

### 증상
```
/health  → 200 OK
/search?query=bounce → 503 Service Unavailable
```

### 응답 메시지
```json
{
  "detail": "Database not found. Please run: boardlib database kilter ./kilter.db --username <your_username>"
}
```

### 원인 분석

#### 시도 1: buildCommand에서 DB 다운로드
```yaml
# render.yaml (v1)
buildCommand: pip install -r requirements.txt && \
  echo "${KILTER_PASSWORD}" | boardlib database kilter ./kilter.db --username ${KILTER_USERNAME}
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**문제**: 빌드 환경에서 다운로드한 파일이 런타임 환경에서 사라짐
- Render의 빌드와 런타임은 분리된 환경
- 빌드 시 생성된 파일은 런타임으로 전달되지 않을 수 있음

#### 디버깅 추가
```python
# main.py - /health 엔드포인트에 디버그 정보 추가
@app.get("/health")
def health_check():
    return {
        "database_exists": DB_PATH.exists(),
        "debug": {
            "cwd": os.getcwd(),  # "/opt/render/project/src"
            "files_in_cwd": os.listdir(cwd)
            # ["requirements.txt", ".git", "main.py", ...]
            # "kilter.db"가 없음!
        }
    }
```

**확인된 사실**:
- 현재 디렉토리: `/opt/render/project/src`
- `kilter.db` 파일이 존재하지 않음

### 해결 방안

#### 시도 2: setup_db.sh 스크립트
```bash
#!/bin/bash
# setup_db.sh
echo "$KILTER_PASSWORD" | boardlib database kilter ./kilter.db --username "$KILTER_USERNAME"
```

```yaml
# render.yaml (v2)
buildCommand: chmod +x setup_db.sh && pip install -r requirements.txt && ./setup_db.sh
```

**문제**: 여전히 DB 파일이 런타임에서 사라짐

#### 최종 해결: start.sh로 시작 시 DB 다운로드

**핵심 아이디어**: 런타임 시작 시점에 DB 확인 후 다운로드

```bash
#!/bin/bash
# start.sh
set -e

echo "Starting Kilterboard API..."

# 데이터베이스가 없으면 다운로드
if [ ! -f "./kilter.db" ]; then
    echo "Database not found. Downloading..."
    echo "$KILTER_PASSWORD" | boardlib database kilter ./kilter.db --username "$KILTER_USERNAME"
    echo "Database downloaded!"
    ls -lh kilter.db
else
    echo "Database exists: $(ls -lh kilter.db)"
fi

echo "Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT
```

```yaml
# render.yaml (v3 - 최종)
services:
  - type: web
    name: kilterboard-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: chmod +x start.sh && ./start.sh
```

### 결과
- ✅ 서버 시작 시 DB 확인
- ✅ 없으면 자동 다운로드
- ✅ `/search` 엔드포인트 정상 작동

---

## 문제 3: 비밀번호 입력 자동화

### 문제
BoardLib의 `database` 명령어는 대화형으로 비밀번호를 입력받음:
```bash
$ boardlib database kilter ./kilter.db --username nmhn0111
Password: [입력 대기]
```

### 해결
파이프(`|`)를 사용하여 stdin으로 비밀번호 전달:
```bash
echo "$KILTER_PASSWORD" | boardlib database kilter ./kilter.db --username "$KILTER_USERNAME"
```

---

## 최종 아키텍처

### 파일 구조
```
kilterboard-api/
├── main.py              # FastAPI 서버 (SQLite 직접 쿼리)
├── requirements.txt     # Python 의존성
├── render.yaml          # Render 배포 설정
├── start.sh             # 시작 스크립트 (DB 다운로드 포함)
├── setup_db.sh          # DB 다운로드 스크립트 (비사용)
├── .gitignore           # Git 무시 파일 (kilter.db 포함)
└── archive/
    ├── project_status_20260205.md
    └── troubleshooting_history.md
```

### 데이터 플로우
```
1. Render 배포 시작
2. requirements.txt로 의존성 설치
3. start.sh 실행
   ├─ kilter.db 존재 확인
   ├─ 없으면 boardlib로 다운로드 (~173MB)
   └─ uvicorn으로 FastAPI 서버 시작
4. HTTP 요청 수신
   ├─ /health → DB 상태 반환
   ├─ /search → SQLite 쿼리로 검색
   └─ /climb/{uuid} → 상세 정보 반환
```

### API 엔드포인트
| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/` | GET | API 환영 메시지 |
| `/health` | GET | DB 상태 확인 |
| `/search` | GET | 이름으로 문제 검색 |
| `/climb/{uuid}` | GET | UUID로 문제 상세 조회 |

---

## 교훈

1. **라이브러리 문서 먼저 확인**: `boardlib`가 Python API를 제공하는지 가정하지 말았어야 함
2. **클라우드 환경의 이해**: 빌드와 런타임 환경의 차이를 이해해야 함
3. **디버깅 정보의 중요성**: `/health` 엔드포인트에 디버그 정보를 추가해서 문제를 빨리 찾음
4. **점진적 해결**: 한 번에 해결하려 하지 말고, 작은 단계로 나누어 시도

---

## 참고 자료

- [BoardLib GitHub](https://github.com/lemeryfertitta/BoardLib)
- [BoardLib PyPI](https://pypi.org/project/boardlib/)
- [Kilterboard API 리버스 엔지니어링](https://bazun.me/blog/kiterboard)
- [Render Blueprint 사양](https://render.com/docs/blueprint-spec)

---
*작성일: 2026-02-05*
*마지막 업데이트: 2026-02-05*
