from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    """
    Parses a claim PDF and returns structured data.
    Ported from monolith's app/parsers/pdf/pdf_parse.py
    """
    result_obj: dict[str, Any] = {"user_info": {}, "codes": [], "info": []}
    info_step = -1

    if not pdf_path.exists():
        return result_obj

    with pdfplumber.open(pdf_path) as pdf:
        # Extract patient info from first few lines
        lines = pdf.pages[0].extract_text_simple().split("\n")[:20]
        name_taken = False
        in_codes = False
        for line in lines:
            words = line.split()
            if not words:
                continue
            if " ".join(words[0:3]) == "Patient Account Number":
                result_obj["user_info"]["account_number"] = words[3]
            elif words[0] == "Patient" and words[1] != "Information" and not name_taken:
                gender_list = [index for index, item in enumerate(words) if item == "Gender"]
                if gender_list:
                    result_obj["user_info"]["name"] = " ".join(words[1 : gender_list[0]])
                else:
                    result_obj["user_info"]["name"] = " ".join(words[1:])
                name_taken = True
            elif words[0] == "DOB":
                result_obj["user_info"]["date_of_birth"] = words[1]

        # Extract tables for claim codes and lines
        for p in pdf.pages:
            for t in p.extract_tables():
                for r in t:
                    if not r or not r[0]:
                        continue

                    check_header = r[0].split("\n")[0].strip()
                    try:
                        res = bool(datetime.strptime(check_header, "%m/%d/%Y"))
                    except ValueError:
                        res = False

                    if in_codes and check_header != "Type":
                        result_obj["codes"].append(
                            {
                                "type": r[0],
                                "code": r[1],
                                "description": r[2].replace("\n", " "),
                            }
                        )
                    elif res:
                        info_step += 1
                        result_obj["info"].append(
                            {
                                "date": check_header,
                                "cpt": r[2],
                                "dx": r[3].split("\n"),
                                "reason_codes": r[6].split("\n"),
                                "billed_amount": r[7],
                                "allowed_amount": r[8],
                                "paid_amount": r[12],
                                "ratio": round(
                                    float(r[8].replace("$", "").replace(",", ""))
                                    / float(r[7].replace("$", "").replace(",", "")),
                                    2,
                                ),
                                "adjustments": [],
                            }
                        )
                    elif check_header == "Adjustments":
                        adj_header_prefix = "Adjustments\nAmount Type Code Quantity Description\n"
                        if r[0].startswith(adj_header_prefix):
                            adj_values = r[0].removeprefix(adj_header_prefix).split()
                        else:
                            adj_values = r[0].split()

                        payment_indexes = [
                            index for index, value in enumerate(adj_values) if value.startswith("$")
                        ]
                        for i in range(len(payment_indexes)):
                            step_index = payment_indexes[i]
                            # Safeguard against short arrays
                            if step_index + 3 >= len(adj_values):
                                continue

                            append_obj = {
                                "amount": adj_values[step_index],
                                "type": " ".join(adj_values[step_index + 1 : step_index + 3]),
                                "code": adj_values[step_index + 3],
                                "description": "",
                            }
                            if i == len(payment_indexes) - 1:
                                append_obj["description"] = " ".join(
                                    adj_values[step_index + 4 :]
                                ).replace("\n", " ")
                            else:
                                append_obj["description"] = " ".join(
                                    adj_values[step_index + 4 : payment_indexes[i + 1]]
                                ).replace("\n", " ")

                            if info_step >= 0:
                                result_obj["info"][info_step]["adjustments"].append(append_obj)

                    elif check_header.startswith("$") and len(r) == 5:
                        if info_step >= 0:
                            exist_adj = [
                                item
                                for item in result_obj["info"][info_step]["adjustments"]
                                if item["code"] == r[2]
                            ]
                            if len(exist_adj) == 0:
                                result_obj["info"][info_step]["adjustments"].append(
                                    {
                                        "amount": r[0],
                                        "type": r[1],
                                        "code": r[2],
                                        "description": r[4].replace("\n", " "),
                                    }
                                )
                    elif check_header == "Type" and r[1] == "Code" and r[2] == "Description":
                        in_codes = True

    return result_obj
