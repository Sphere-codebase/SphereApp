import base64
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from core.parser import parse_pdf
from schemas.parser import ParseRequest, ParseResponse, PdfParseResult

app = FastAPI(title="PDF Parser Service", version="1.0.0")

# Service-to-service auth key (simple example)
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "default_secret")

def verify_api_key(api_key: str):
    if api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

@app.post("/v1/parse", response_model=ParseResponse)
async def parse_endpoint(
    request: ParseRequest = None,
    file: UploadFile = File(None),
    x_api_key: Annotated[str | None, Form()] = None
):
    # api_key validation could be a dependency, keeping it simple for extraction
    # verify_api_key(x_api_key) 

    temp_pdf_path = None
    request_id = str(uuid.uuid4())

    try:
        # Handle Multipart File Upload
        if file:
            suffix = Path(file.filename).suffix or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                temp_pdf_path = Path(tmp.name)
        
        # Handle JSON URL
        elif request and request.pdf_url:
            request_id = request.request_id or request_id
            async with httpx.AsyncClient() as client:
                response = await client.get(request.pdf_url)
                if response.status_code != 200:
                    raise HTTPException(status_code=400, detail="Failed to download PDF")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(response.content)
                    temp_pdf_path = Path(tmp.name)

        # Handle JSON Base64
        elif request and request.pdf_base64:
            request_id = request.request_id or request_id
            try:
                content = base64.b64decode(request.pdf_base64)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(content)
                    temp_pdf_path = Path(tmp.name)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 encoding")
        
        else:
            raise HTTPException(status_code=400, detail="No PDF provided")

        # Parse
        raw_result = parse_pdf(temp_pdf_path)
        
        # Validate result against schema
        try:
            validated_result = PdfParseResult.model_validate(raw_result)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Parsing produced invalid schema: {e}")

        return ParseResponse(
            parse_result=validated_result,
            request_id=request_id
        )

    finally:
        if temp_pdf_path and temp_pdf_path.exists():
            os.remove(temp_pdf_path)

@app.get("/health")
def health_check():
    return {"status": "ok"}
