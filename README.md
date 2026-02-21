# Syllabus-Sync 🗓️

**Privacy-first web application that extracts events, assignments, and deadlines from academic syllabi and converts them into importable calendar files (.ics).**

> A group project for the module 'Getting started with Generative AI'


## 🎯 Overview

Syllabus-Sync is a stateless, privacy-focused web application designed to help students and educators transform academic schedule documents into structured calendar events. Upload your syllabus as a PDF (or other supported formats), and Syllabus-Sync will:

- **Extract** all relevant dates, assignment titles, exams, and events using AI-powered parsing
- **Preview** extracted events in an editable table
- **Export** events as an `.ics` calendar file compatible with Google Calendar, Apple Calendar, Outlook, and more

### Key Features

✅ **Privacy-First Design**
- No user accounts required
- No persistent data storage
- All processing happens on-demand
- Files are deleted immediately after processing

✅ **AI-Powered Extraction**
- Uses Google Vertex AI Gemini models for intelligent document parsing
- Automatically infers event types (assignment, exam, lecture, project)
- Handles missing years and ambiguous date formats

✅ **User-Friendly Interface**
- Drag-and-drop file upload
- Inline editing of extracted events
- Real-time preview
- One-click calendar export

✅ **Multi-Format Support**
- PDF ✅
- Excel (.xlsx) ✅
- Word (.docx) ✅
- HTML ✅

---

## 🏗️ Architecture

### Tech Stack

**Frontend:**
- [Next.js 16](https://nextjs.org/) - React framework with server-side rendering
- [TypeScript](https://www.typescriptlang.org/) - Type-safe JavaScript
- [Tailwind CSS 4](https://tailwindcss.com/) - Utility-first CSS framework
### Architecture (snapshot)

**Frontend:** Next.js 16 (TypeScript), Tailwind, Axios, FileSaver; CSP + security headers enabled.

**Backend:** FastAPI with sync upload, async upload + SSE stream, ICS generation; parsers for PDF/XLSX/XLS/DOCX/HTML (AI + heuristic), ICS generator; structured logs, inline metrics, rate/token limits, magic-byte + MIME validation, size cap, optional AV hook placeholder.

**Data Flow:** upload → temp file → validation (size/MIME/magic) → parser → events JSON → temp cleanup; async path enqueues job and streams status via SSE; ICS endpoint accepts `ICSRequest` (`events`, `timezone`) and returns `text/calendar`.
- [Axios](https://axios-http.com/) - HTTP client for API requests
- [Lucide React](https://lucide.dev/) - Icon library
- [FileSaver.js](https://github.com/eligrey/FileSaver.js/) - Client-side file downloads

**Backend:**
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Google Vertex AI](https://cloud.google.com/vertex-ai) - Gemini 1.5 Flash for document parsing
- [PDFPlumber](https://github.com/jsvine/pdfplumber) - PDF text extraction
- [iCalendar](https://icalendar.readthedocs.io/) - ICS calendar file generation
- [Uvicorn](https://www.uvicorn.org/) - ASGI server

### Architecture Diagram

```
┌─────────────────┐
│   Browser       │
│  (Next.js App)  │
└────────┬────────┘
         │
         │ HTTP/REST
         ▼
┌─────────────────┐        ┌──────────────────┐
│  FastAPI        │───────▶│  Vertex AI       │
│  Backend        │        │  (Gemini 1.5)    │
│                 │◀───────│                  │
└────────┬────────┘        └──────────────────┘
         │
         │ File I/O (temp)
         ▼
   ┌─────────┐
   │ /tmp    │  ← Files deleted immediately
   └─────────┘     after processing
```

### Data Flow

1. **Upload**: User uploads a syllabus file (PDF/XLSX/DOCX/HTML)
2. **Temporary Storage**: File saved to temp directory with unique name
3. **Parsing**: Backend sends file to appropriate parser (PDF parser uses Vertex AI)
4. **Extraction**: AI model extracts structured event data (title, date, type, description)
5. **Response**: Parsed events returned as JSON to frontend
6. **Cleanup**: Temporary file deleted immediately
7. **Preview & Edit**: User reviews and edits events in interactive table
8. **Export**: User clicks "Export to Calendar" → Backend generates `.ics` file → Downloaded to user's device

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** (v18 or higher)
- **Python** (v3.9 or higher)
- **Google Cloud Project** with Vertex AI API enabled
- **Google Cloud credentials** (for AI parsing)

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/annageiser/Syllabus-Sync.git
cd Syllabus-Sync
```

#### 2. Backend Setup

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

cd backend
pip install -r requirements.txt

# Set up Google Cloud credentials (optional if using API key)
export GOOGLE_CLOUD_PROJECT="your-project-id"
# OR authenticate with gcloud CLI:
gcloud auth application-default login
```

#### 3. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install
```

### Running the Application (dev)

Backend (Terminal 1):
```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (Terminal 2):
```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Access: http://localhost:3000
### Running the Application

#### Start Backend (Terminal 1)

```bash
source .venv/bin/activate
python main.py
```

Backend will run on `http://localhost:8000`

#### Start Frontend (Terminal 2)

```bash
cd frontend
npm run dev
```

Frontend will run on `http://localhost:3000`

#### Access the App

Open your browser and navigate to:
```
http://localhost:3000
```

### One-Command Dev Helper

From the repo root, run `./dev.sh` to kill any lingering servers on ports 3000/8000 and start both backend and frontend in watch mode.

---

## 📖 Usage
### Basic Workflow

1. **Upload Syllabus**
   - Drag and drop your syllabus PDF onto the upload area, or click "Browse Files"
   - Supported formats: PDF, XLSX, DOCX, HTML

2. **Review Extracted Events**
   - View all extracted events in the interactive table
   - Each event shows:
     - **Title**: Assignment/exam/lecture name
     - **Date**: Due date or event date
     - **Type**: Category (assignment, exam, lecture, event)

3. **Edit Events (Optional)**
   - Click any field to edit inline
   - Change dates, titles, or event types
   - Delete unwanted events

4. **Export to Calendar**
   - Click "Export to Calendar (.ics)" button
   - Download `syllabus-events.ics` file
   - Import into your calendar app:
     - **Google Calendar**: Settings → Import & Export → Import
     - **Apple Calendar**: File → Import

---

## 🔧 Configuration

### Environment Variables

**Backend** (Optional):
```bash
# Google Cloud Project ID (auto-detected if using gcloud CLI)
export GOOGLE_CLOUD_PROJECT="your-project-id"

# Vertex AI location (default: us-central1)
export VERTEX_AI_LOCATION="us-central1"
```

### Google Cloud Setup
1. Create a Google Cloud Project
2. Enable Vertex AI API
3. Authenticate:
   ```bash
   gcloud auth application-default login
   ```
   OR set `GOOGLE_CLOUD_PROJECT` environment variable and use service account credentials.

---

## 🛡️ Privacy & Security

### Privacy Commitments

- ✅ **No user accounts** - No registration, login, or user tracking
- ✅ **No persistent storage** - Files are deleted immediately after processing
- ✅ **No external integrations** - No automatic uploads to calendar services
- ✅ **Client-side downloads** - .ics files generated on-demand and downloaded directly to your device
- ✅ **Temporary processing only** - All uploaded files stored in `/tmp` and removed after parsing

### Data Handling

- Uploaded files are sent to Google Vertex AI for parsing
- Files are processed ephemerally and not stored by Google

---

## 🗺️ Roadmap

### Current Status (v0.2)

- ✅ PDF parsing with Vertex AI Gemini 1.5 Flash
- ✅ Event extraction (title, date, type)
- ✅ Interactive event preview/editing
- ✅ ICS calendar export
- ✅ Next.js frontend with Tailwind CSS
- ✅ FastAPI backend
- ✅ Multi-format parsing: PDF, Excel, Word, HTML

### Planned Features (v0.3+)
- 🚧 **Enhanced event details**: Time extraction, location, course codes
- 🚧 **Reminders & alarms**: Configurable reminder offsets
- 🚧 **Weighting/priority**: Extract assignment weights and set calendar priority
- 🚧 **Batch processing**: Upload multiple syllabi at once
- 🚧 **Recurring events**: Detect weekly lectures/sections
- 🚧 **Calendar merge**: Combine multiple syllabi into one .ics file
- 🚧 **Improved AI prompts**: Better date parsing and event categorization
- 🚧 **Accessibility improvements**: ARIA labels, keyboard navigation
- 🚧 **Mobile responsiveness**: Optimized for mobile devices

---

## 🧑‍💻 Development

### Project Structure

```
Syllabus-Sync/
├── backend/
│   ├── main.py                 # FastAPI app & endpoints
│   ├── ics_generator.py        # ICS file generator
│   ├── parsers/
│   │   └── pdf_parser.py       # PDF parsing with Vertex AI
│   ├── requirements.txt        # Python dependencies
│   └── .venv/                  # Virtual environment
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Main page component
│   │   ├── layout.tsx          # App layout
│   │   └── globals.css         # Global styles
│   ├── components/
│   │   ├── FileUploader.tsx    # Drag-and-drop upload
│   │   └── EventTable.tsx      # Event preview table
│   ├── package.json            # Node dependencies
│   └── tsconfig.json           # TypeScript config
│
├── example input data/         # Sample syllabi for testing
└── README.md                   # This file
```

### Adding a New Parser

To add support for a new file format (e.g., Excel):

1. Create `backend/parsers/excel_parser.py`:
   ```python
   class ExcelParser:
       def parse(self, file_path):
           # Extract events from Excel file
           # Return list of dicts: [{"title": ..., "date": ..., "type": ...}]
           pass
   ```

2. Update `backend/main.py`:
   ```python
   from parsers.excel_parser import ExcelParser
   
   @app.post("/upload")
   async def upload_file(file: UploadFile = File(...)):
       # ...existing code...
       elif file.filename.endswith('.xlsx'):
           parser = ExcelParser()
           events = parser.parse(tmp_path)
   ```

3. Update `frontend/components/FileUploader.tsx`:
   ```tsx
   accept=".pdf,.xlsx,.docx,.html"

### Running Tests

```bash
# Backend tests (TODO)
cd backend
pytest

# Frontend tests (TODO)
cd frontend
npm test
```


```bash
# Frontend production build
cd frontend
npm run build

# Backend production (use production ASGI server)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---


This is a student group project. Contributions, issues, and feature requests are welcome!

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is developed as part of the "Getting started with Generative AI" module.

---

## 🙏 Acknowledgments

- **Google Vertex AI** for powerful document understanding
- **Next.js** for the amazing React framework
- **FastAPI** for the elegant Python API framework
- Course instructors and team members

---

## 📞 Support

For issues or questions:
- Open an issue on GitHub
- Contact the development team

---

**Built with ❤️ by students learning Generative AI**
