# PunjabiTutor Backend – Phase 1

## Setup

1. Clone the repo
2. Create a `.env` file (copy from `.env.example`) and fill your `GEMINI_API_KEY` and `MONGODB_URL`
3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
4. Seed the database with initial data
   ```bash
   python -m app.seed.seed_db
   ```
5. Run the server
```bash
uvicorn app.main:app --reload --port 8000
# On Windows PowerShell, use semicolons instead of && if chaining commands:
# pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000
```
(Note: Run from the punjabi-tutor-backend/ directory. Ensure virtual environment is activated if using one.)
6. Visit `http://localhost:8000/docs` to test endpoints.

## Admin Panel

Access the admin panel at `/admin` to manage lessons and characters:

**Authentication:**
- Enter your `GEMINI_API_KEY` in the admin key field
- All admin operations require this key in the `X-Admin-Key` header

**Features:**
- **Character Management**: View and select characters
- **Lesson Management**:
  - Add new lessons at specific positions (inserts and shifts existing lessons)
  - Edit lesson titles and step content
  - Delete lessons
  - **Drag & Drop Reordering**: Reorder lessons by dragging them
  - Edit lesson steps with different types (info, multiple-choice, text-input, feedback, completion)

**API Endpoints:**
- `GET /admin` - Admin panel interface
- `GET/POST/PUT/DELETE /admin/characters` - Character CRUD
- `GET/POST/PUT/DELETE /admin/lessons` - Lesson CRUD
- `POST /admin/lessons/{character_id}/insert` - Insert lesson at position
- `POST /admin/lessons/{character_id}/reorder` - Reorder lessons

## Deployment

This app is configured for deployment on Railway with MongoDB. Railway automatically provides the `MONGODB_URL` environment variable.

## API Endpoints

- `GET /health` — check service health  
- `GET /characters` — list all characters  
- `GET /characters/{character_id}` — detail of a character  
- `POST /chat/{character_id}` — send a message to a character  
  ```json
  {
    "user_id": "user123",
    "message": "Hello, what do you have?",
    "language": "roman"
  }
  ```  
  Response:  
  ```json
  {
    "character_id": "shopkeeper",
    "expression": "neutral",
    "reply": {
      "english": "...",
      "roman": "...",
      "gurmukhi": "..."
    }
  }
  ```

## Next Steps

- Integrate translation for Roman Punjabi & Gurmukhi  
- Add message logging to DB  
- Add rate limiting / token quota tracking  
- Add more characters, personality fine-tuning  
- Move to production deployment
