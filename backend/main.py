from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from parsers.pdf_parser import PDFParser
# from parsers.excel_parser import ExcelParser
# from parsers.docx_parser import DocxParser
# from parsers.html_parser import HTMLParser
from ics_generator import ICSGenerator
import shutil
import os
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation Error: {exc.errors()}")
    print(f"Body: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Create a temporary file to save the upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        events = []
        if file.filename.endswith('.pdf'):
            parser = PDFParser()
            events = parser.parse(tmp_path)
        # elif ... other formats
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
            
        return {"events": events}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

from pydantic import BaseModel
from typing import List, Optional

class EventModel(BaseModel):
    title: Optional[str] = "Untitled"
    date: Optional[str] = None
    type: Optional[str] = "event"

@app.post("/generate-ics")
async def generate_ics(request: Request):
    try:
        events = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    generator = ICSGenerator()
    ics_content = generator.generate(events)
    return {"ics_content": ics_content.decode('utf-8')}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
