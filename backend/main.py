from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import shutil
import os
import tempfile

from parsers.pdf_parser import PDFParser
from parsers.excel_parser import ExcelParser
from parsers.docx_parser import DocxParser
from parsers.html_parser import HTMLParser
from ics_generator import ICSGenerator
from config import config

app = FastAPI(
    title="Syllabus-Sync API",
    description="Privacy-first API for extracting events from academic syllabi and generating calendar files.",
    version="0.1.0"
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed information."""
    if config.DEBUG:
        print(f"Validation Error: {exc.errors()}")
        print(f"Body: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )

# CORS configuration using config module
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload and parse a syllabus file to extract events.
    
    Supports multiple file formats:
    - PDF (.pdf)
    - Excel (.xlsx, .xls)
    - Word (.docx)
    - HTML (.html, .htm)
    
    Args:
        file: The syllabus file
        
    Returns:
        JSON object with extracted events list, each containing:
        - module: Course/module name
        - title: Event title
        - date: Event date (YYYY-MM-DD)
        - type: Event type (lecture, assignment, exam, etc.)
        - description: Additional details
        
    Raises:
        HTTPException 400: Unsupported file format or no filename
        HTTPException 500: Processing error or Google Cloud configuration issue
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Create a temporary file to save the upload
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        events = []
        
        # Route to appropriate parser based on file extension
        try:
            parser = None
            if file_extension == '.pdf':
                parser = PDFParser()
                events = parser.parse(tmp_path)
            elif file_extension in ['.xlsx', '.xls']:
                parser = ExcelParser()
                events = parser.parse(tmp_path)
            elif file_extension == '.docx':
                parser = DocxParser()
                events = parser.parse(tmp_path)
            elif file_extension in ['.html', '.htm']:
                parser = HTMLParser()
                events = parser.parse(tmp_path)
            else:
                supported_formats = ['.pdf', '.xlsx', '.xls', '.docx', '.html', '.htm']
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file format: {file_extension}. Supported formats: {', '.join(supported_formats)}"
                )
            
            source = parser.source if parser else "Unknown"
        except RuntimeError as e:
            # Configuration/setup error (e.g., Vertex AI)
            raise HTTPException(
                status_code=500, 
                detail=f"Google Cloud configuration error: {str(e)}"
            )
        
        if config.DEBUG:
            print(f"Extracted {len(events)} events from {file.filename} using {source}")
            
        return {"events": events, "extraction_source": source}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        if config.DEBUG:
            import traceback
            traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing file: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if config.TEMP_FILE_CLEANUP and os.path.exists(tmp_path):
            os.remove(tmp_path)
            if config.DEBUG:
                print(f"Cleaned up temporary file: {tmp_path}")



class EventModel(BaseModel):
    """Model for an event to be converted to ICS format."""
    title: Optional[str] = "Untitled"
    date: Optional[str] = None
    type: Optional[str] = "event"
    description: Optional[str] = ""

@app.post("/generate-ics")
async def generate_ics(request: Request):
    """
    Generate an ICS calendar file from a list of events.
    
    Args:
        request: JSON request body containing list of events
        
    Returns:
        JSON object with ics_content as a string
        
    Raises:
        HTTPException 400: Invalid JSON or empty events list
        HTTPException 500: ICS generation error
    """
    try:
        events = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid JSON in request body: {str(e)}"
        )
    
    if not events or not isinstance(events, list):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a non-empty list of events"
        )
    
    try:
        generator = ICSGenerator()
        ics_content = generator.generate(events)
        
        if config.DEBUG:
            print(f"Generated ICS file with {len(events)} events")
        
        return {"ics_content": ics_content.decode('utf-8')}
    except Exception as e:
        if config.DEBUG:
            import traceback
            traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating ICS file: {str(e)}"
        )



if __name__ == "__main__":
    import uvicorn
    
    # Print configuration on startup
    if config.DEBUG:
        config.log_config()
    
    print(f"Starting Syllabus-Sync backend on {config.BACKEND_HOST}:{config.BACKEND_PORT}")
    print(f"API documentation available at: http://{config.BACKEND_HOST}:{config.BACKEND_PORT}/docs")
    
    uvicorn.run(
        "main:app", 
        host=config.BACKEND_HOST, 
        port=config.BACKEND_PORT, 
        reload=True
    )

