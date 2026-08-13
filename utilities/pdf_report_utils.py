import base64
from pathlib import Path


class PDFReportUtils:
    @staticmethod
    def generate(driver, name, directory="output/pdf"):
        pdf_dir = Path.cwd() / directory
        pdf_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name)
        file_path = pdf_dir / f"{safe_name}_report.pdf"
        result = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
        file_path.write_bytes(base64.b64decode(result["data"]))
        return str(file_path)
