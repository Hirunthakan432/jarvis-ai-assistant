"""Explicit local file import. Model tools cannot import arbitrary filesystem paths."""
from pathlib import Path


def import_document(path, memory):
    file = Path(path).expanduser().resolve(strict=True)
    if not file.is_file() or file.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('Choose a regular file smaller than 10 MB.')
    if file.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(file)
        if reader.is_encrypted or len(reader.pages) > 150:
            raise ValueError('Use an unencrypted PDF with at most 150 pages.')
        pages = []
        size = 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            size += len(text)
            if size > 300000:
                raise ValueError('Extracted document exceeds 300,000 characters.')
            pages.append(f'[Page {number}]\n{text}')
        text = '\n'.join(pages)
        if size == 0:
            raise ValueError('No usable text. Scanned PDFs need OCR before import.')
    elif file.suffix.lower() in {'.txt', '.md', '.csv', '.py', '.ino'}:
        text = file.read_text(encoding='utf-8')
    else:
        raise ValueError('Supported files: PDF, TXT, MD, CSV, PY and INO.')
    if not text.strip() or len(text) > 300000:
        raise ValueError('Document must contain 1–300,000 characters of text.')
    key = memory.add_document(file.name, text)
    return f'Imported #{key}: {file.name}. Ask a question or request a quiz; matching passages will be sent to your AI provider.'


def image_data(path):
    import base64
    from io import BytesIO
    from PIL import Image, ImageOps
    file = Path(path).expanduser().resolve(strict=True)
    if file.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('Choose an image smaller than 10 MB.')
    with Image.open(file) as source:
        if source.width * source.height > 20000000:
            raise ValueError('Image exceeds 20 megapixels.')
        picture = ImageOps.exif_transpose(source).convert('RGB')
        picture.thumbnail((1600, 1600))
        output = BytesIO()
        picture.save(output, format='JPEG', quality=85)
    return base64.b64encode(output.getvalue()).decode('ascii')
