# Public Release Checklist

## Safe to commit

- Source code under `backend/`, `frontend/`, `scripts/`, `tools/`
- `README.md`
- `LICENSE`
- `.env.example`
- Documentation under `docs/`

## Do not commit

- `.env`
- `data/app.db`
- Real manga pages
- Real user data
- Extracted investigation cases
- Production secrets

## GitHub publish commands

```bash
git init
git add .
git commit -m "Initial MangaTrace Web MVP"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/manga-trace-web-mvp.git
git push -u origin main
```

## Local smoke test

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_demo.py
uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000/`.
