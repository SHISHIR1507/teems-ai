# TikTok Posting Service

A clean, simple FastAPI service for posting videos to TikTok.

## Features

- ✅ Post videos to TikTok via REST API
- ✅ Store user TikTok access tokens
- ✅ Track posted content
- ✅ PostgreSQL database
- ✅ Pydantic validation
- ✅ Simple, clean code

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Database

Create a PostgreSQL database and run the schema:

```bash
psql -U your_username -d your_database -f schema.sql
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your PostgreSQL connection string
```

### 4. Run the Service

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Health Check
```
GET /
```

### Add TikTok Token
```http
POST /api/tokens/add
Content-Type: application/json

{
  "user_id": 1,
  "access_token": "your_tiktok_access_token"
}
```

### Post to TikTok
```http
POST /api/post
Content-Type: application/json

{
  "user_id": 1,
  "video_url": "https://example.com/video.mp4",
  "caption": "Check this out! 🔥",
  "hashtags": ["viral", "trending"]
}
```

### Get User Posts
```http
GET /api/posts/{user_id}
```

## Project Structure

```
tiktok_posting_service/
├── main.py              # FastAPI application
├── models.py            # Pydantic models
├── database.py          # PostgreSQL connection
├── tiktok_client.py     # TikTok API client
├── schema.sql           # Database schema
├── requirements.txt     # Dependencies
├── .env.example         # Environment template
├── init_db.py           # Database initialization
└── README.md            # This file
```
