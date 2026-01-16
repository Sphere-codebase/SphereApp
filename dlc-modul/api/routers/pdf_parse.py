import asyncio
import functools
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ValidationError

from app.parsers.aetna_pdf import parse_data

CLAIMS_FOLDER = Path("claims")
PARSE_FOLDER = Path("claims_parsed")

EXECUTOR = ProcessPoolExecutor()

router = APIRouter(prefix="/api/pdf", tags=["pdf-parse"])



class PatientInfo(BaseModel):
    account_number: str | None = None
    name: str | None = None
    date_of_birth: str | None = None


class CodeInfo(BaseModel):
    type: str
    code: str
    description: str | None = None


class AdjustmentInfo(BaseModel):
    amount: str
    type: str
    code: str
    description: str | None = None


class ClaimInfo(BaseModel):
    date: str
    cpt: str
    dx: list[str]
    reason_codes: list[str]
    billed_amount: str
    allowed_amount: str
    paid_amount: str
    ratio: float
    adjustments: list[AdjustmentInfo]


class PDFileInfo(BaseModel):
    user_info: PatientInfo
    codes: list[CodeInfo]
    info: list[ClaimInfo]


class PDFileResponse(BaseModel):
    pdf: PDFileInfo
    error_message: str | None = None


class PDFParseRequest(BaseModel):
    path: str


@router.post("/parse", response_model=PDFileResponse)
def parse_doc(request: PDFParseRequest, response: Response):
    # Use the absolute path provided in the request
    doc_path = Path(request.path)
    if not doc_path.exists():
         return Response(content=f"File not found: {doc_path}", status_code=status.HTTP_404_NOT_FOUND)

    # Output path (optional: logic to determine where to save parsed json)
    # For now, let's save it next to the original file or in a parsed folder
    if not PARSE_FOLDER.exists():
        PARSE_FOLDER.mkdir()
    
    # We will save the result to claims_parsed/filename.json
    output_path = PARSE_FOLDER / f"{doc_path.stem}.json"
    
    result_obj = parse_data(doc_path, output_path)
    try:
        PDFileInfo.model_validate(result_obj)
    except ValidationError as ex:
        return {"pdf": result_obj, "error_message": str(ex)}
    return {"pdf": result_obj}


async def parse_all_pdfs():
    """
    Generates separate processes for each file in the Claims folder
    """
    loop = asyncio.get_running_loop()

    tasks = []

    if not PARSE_FOLDER.exists():
        PARSE_FOLDER.mkdir()
    for path in CLAIMS_FOLDER.iterdir():
        if path.suffix.lower() == ".pdf":
            task = loop.run_in_executor(EXECUTOR, functools.partial(parse_data, path_from=path, path_to=PARSE_FOLDER / f"{path.stem}.json"))
            tasks.append(task)

    await asyncio.wait(tasks)
    print("Job finished")


@router.post("/parse_all", status_code=status.HTTP_204_NO_CONTENT)
async def parse_all():
    asyncio.create_task(parse_all_pdfs())
