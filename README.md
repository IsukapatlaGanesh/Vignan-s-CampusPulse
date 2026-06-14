# ⚡ CampusPulse
### Campus Issue Reporting & Tracking Platform

A beginner-friendly full-stack web application built with **Python Flask + SQLite**.

---

## 📁 Project Structure

```
campuspulse/
│
├── app.py                     ← Main Flask app (routes, logic, DB init)
├── requirements.txt           ← Python dependencies
├── campuspulse.db             ← SQLite database (auto-created on first run)
│
├── templates/                 ← Jinja2 HTML templates
│   ├── base.html              ← Master layout (navbar, footer, flash messages)
│   ├── index.html             ← Homepage (hero, stats, recent issues)
│   ├── submit.html            ← Complaint submission form
│   ├── complaints.html        ← Browse all complaints with filters
│   ├── admin.html             ← Admin dashboard (change statuses)
│   ├── profile.html           ← User profile + achievements
│   ├── leaderboard.html       ← Student rankings
│   └── chat.html              ← AI chatbot UI (frontend only)
│
└── static/
    ├── css/
    │   └── style.css          ← All styles (dark theme, responsive)
    ├── js/
    │   └── main.js            ← Interactions (nav, upvotes, chat, file upload)
    └── uploads/               ← Uploaded complaint images (auto-created)
```

---

## 🚀 Getting Started

### 1. Install Python
Make sure you have Python 3.8+ installed. Check with:
```bash
python --version
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
python app.py
```

### 5. Open in your browser
```
http://127.0.0.1:5000
```

---

## 📄 Pages & URLs

| Page           | URL              | Description                          |
|----------------|------------------|--------------------------------------|
| Homepage       | `/`              | Hero, stats, recent issues           |
| Submit Issue   | `/submit`        | Complaint form with image upload     |
| All Issues     | `/complaints`    | Browse & filter all complaints       |
| Admin Panel    | `/admin`         | View all + update statuses           |
| Profile        | `/profile`       | User stats, achievements, history    |
| Leaderboard    | `/leaderboard`   | Top contributors                     |
| AI Chat        | `/chat`          | Chatbot UI (simulated responses)     |
| Upvote (API)   | `/api/upvote/<id>` | POST endpoint for upvoting         |

---

## 🗄️ Database Schema

**complaints table**
| Column      | Type    | Description              |
|-------------|---------|--------------------------|
| id          | INTEGER | Primary key              |
| title       | TEXT    | Issue title              |
| description | TEXT    | Full description         |
| category    | TEXT    | Infrastructure, Tech...  |
| status      | TEXT    | Pending/In Progress/Resolved |
| image_path  | TEXT    | Path to uploaded image   |
| author      | TEXT    | Reporter name            |
| upvotes     | INTEGER | Number of upvotes        |
| created_at  | TEXT    | Submission timestamp     |

**users table**
| Column    | Type    | Description        |
|-----------|---------|--------------------|
| id        | INTEGER | Primary key        |
| username  | TEXT    | Display name       |
| email     | TEXT    | Email address      |
| points    | INTEGER | Contribution score |
| badge     | TEXT    | Newcomer → Legend  |
| joined_at | TEXT    | Join date          |

---

## ✨ Features

- 🌙 **Dark theme** with modern UI
- 📝 **Complaint submission** with optional image upload
- 🔍 **Filter complaints** by category and status
- 👆 **Upvote system** with AJAX (no page reload)
- 🛡️ **Admin dashboard** — change status with a dropdown
- 🏆 **Leaderboard** with podium and rankings
- 🤖 **Simulated chatbot** with keyword-based responses
- 📱 **Fully responsive** — works on mobile & desktop
- ✅ **Seeded demo data** — works out of the box

---

## 🔧 Customisation Tips for Beginners

| What to change         | Where to look                |
|------------------------|------------------------------|
| Colours & fonts        | `static/css/style.css` → `:root` |
| Add a new page         | Create `templates/page.html`, add route in `app.py` |
| Change categories      | `submit.html` `<select>` + `complaints.html` filter list |
| Add more DB fields     | `init_db()` in `app.py`      |
| Real user login        | Add `flask-login` package    |
| Email notifications    | Add `flask-mail` package     |

---

## 📚 Tech Stack

| Layer      | Technology         |
|------------|--------------------|
| Backend    | Python 3 + Flask   |
| Database   | SQLite (via sqlite3)|
| Frontend   | HTML5 + CSS3 + JS  |
| Fonts      | Syne + DM Sans (Google Fonts) |
| Icons      | Phosphor Icons     |
| File upload| Werkzeug           |

---

## 🎓 Learning Objectives

By building this project you will learn:
- Flask routing (`@app.route`)
- Jinja2 templating (`{% extends %}`, `{% for %}`, `{{ var }}`)
- SQLite CRUD operations
- HTML form handling (GET/POST)
- File uploads with Flask
- Fetch API for AJAX requests
- CSS custom properties (variables)
- Responsive design with CSS Grid & media queries

---

Built with ❤️ for university students everywhere.
