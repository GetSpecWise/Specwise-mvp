def read_pdf(f) -> str:
    import io
    data = f.read()
    bio = io.BytesIO(data)
    text = ""

    # 1) pypdf (fast, works if text-based)
    try:
        if pypdf:
            bio.seek(0)
            r = pypdf.PdfReader(bio)
            pages = [p.extract_text() or "" for p in r.pages]
            text = "\n".join(pages).strip()
            if text:
                return text
    except Exception:
        pass

    # 2) pdfplumber (better on tricky text PDFs)
    try:
        import pdfplumber
        bio.seek(0)
        pages=[]
        with pdfplumber.open(bio) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        text = "\n".join(pages).strip()
        if text:
            return text
    except Exception:
        pass

    # 3) OCR fallback (for scanned PDFs)
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        images = convert_from_bytes(data, fmt="png", dpi=200)
        ocr_texts = [pytesseract.image_to_string(img) for img in images]
        text = "\n".join(ocr_texts).strip()
        return text
    except Exception as e:
        return ""
