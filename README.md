# PostBackend

Django REST Framework backend for the BlogSpace / Posts platform.

## Features
- Modular posts API with authentication (Session / Token)
- Markdown content support
- User reactions (likes, dislikes) with optimistic concurrency
- Hierarchical threaded comments
- Post activity tracking and administration insights
- Cross-Origin Resource Sharing (CORS) configured for React frontend

## Getting Started

### 1. Set up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Database Migrations
```bash
python manage.py migrate
```

### 3. Run Development Server
```bash
python manage.py runserver 8000
```

### 4. Run Tests
```bash
python manage.py test posts
```
