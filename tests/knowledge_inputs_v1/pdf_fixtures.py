"""Synthetic PDFs only, generated in memory. Never read user documents.

The hand-written xref fixture preserves K4-PREFLIGHT-01 byte-for-byte;
other fixtures use a real PDF writer, including compressed/encrypted streams.
"""
import io

from pypdf import PdfWriter
from pypdf.generic import (DecodedStreamObject, DictionaryObject, NameObject,
                           NumberObject)


CORRUPT_HEADER = b"%PDF-1.7\nThis is not a PDF object graph (Synthetic non-document literal)."


def two_page_preflight_pdf():
    first = b"BT /F1 12 Tf 20 720 Td (Synthetic first-page A) Tj 0 -20 Td (Synthetic first-page B) Tj ET"
    second = b"BT /F1 12 Tf 20 720 Td (Synthetic second-page C) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 /MediaBox [0 0 612 792] >>",
        b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 7 0 R >> >> >>",
        b"<< /Length " + str(len(first)).encode() + b" >>\nstream\n" + first + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>",
        b"<< /Length " + str(len(second)).encode() + b" >>\nstream\n" + second + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data, offsets = b"%PDF-1.7\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_at = len(data)
    data += b"xref\n0 8\n0000000000 65535 f \n"
    for offset in offsets:
        data += ("%010d 00000 n \n" % offset).encode()
    data += b"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n" + str(xref_at).encode() + b"\n%%EOF\n"
    return data


def pdf_bytes(pages=(('Synthetic PDF',),), *, compressed=False,
              password=None, unused_image=False, image_form=False):
    """Each page is a tuple of text lines, () (blank), or 'image'."""
    writer = PdfWriter()
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    font_ref = writer._add_object(font)
    for lines in pages:
        page = writer.add_blank_page(width=612, height=792)
        resources = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font_ref})})
        page[NameObject('/Resources')] = resources
        if lines == 'image' or unused_image:
            image = DecodedStreamObject()
            image.set_data(b'\x00\x80\xff')
            image.update({NameObject('/Type'): NameObject('/XObject'),
                NameObject('/Subtype'): NameObject('/Image'), NameObject('/Width'): NumberObject(1),
                NameObject('/Height'): NumberObject(1), NameObject('/BitsPerComponent'): NumberObject(8),
                NameObject('/ColorSpace'): NameObject('/DeviceRGB')})
            image_ref = writer._add_object(image)
            resources[NameObject('/XObject')] = DictionaryObject({NameObject('/Im1'): image_ref})
            if image_form:
                from pypdf.generic import ArrayObject
                form = DecodedStreamObject()
                form.set_data(b'q 100 0 0 100 0 0 cm /Im1 Do Q')
                form.update({NameObject('/Type'): NameObject('/XObject'),
                    NameObject('/Subtype'): NameObject('/Form'),
                    NameObject('/BBox'): ArrayObject([NumberObject(n) for n in (0, 0, 100, 100)]),
                    NameObject('/Resources'): DictionaryObject({NameObject('/XObject'):
                        DictionaryObject({NameObject('/Im1'): image_ref})})})
                resources[NameObject('/XObject')] = DictionaryObject({NameObject('/Fm1'): writer._add_object(form)})
        if lines == 'image':
            content = b'q 100 0 0 100 20 620 cm ' + (b'/Fm1' if image_form else b'/Im1') + b' Do Q'
        else:
            content = b'BT /F1 12 Tf 20 720 Td '
            for index, line in enumerate(lines):
                escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                content += (b'0 -20 Td ' if index else b'') + b'(' + escaped.encode('ascii') + b') Tj '
            content += b'ET'
        stream = DecodedStreamObject(); stream.set_data(content)
        page[NameObject('/Contents')] = writer._add_object(stream.flate_encode() if compressed else stream)
    if password is not None:
        # Synthetic test credentials only; RC4 needs no optional crypto library.
        writer.encrypt(password, algorithm='RC4-128')
    output = io.BytesIO(); writer.write(output); writer.close()
    return output.getvalue()
