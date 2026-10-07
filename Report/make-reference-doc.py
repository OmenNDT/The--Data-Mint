#!/usr/bin/env python3
"""
Dựng bản reference-doc sạch từ form mẫu để pandoc dùng khi xuất DOCX.

Form mẫu có hai điểm khiến pandoc tạo ra file hỏng:
  1. Nhúng font ở word/fonts/font1.odttf. Pandoc chép fontTable.xml và phần rels
     trỏ tới file font nhưng không chép chính file font, nên gói OOXML thiếu part.
  2. styleId của các kiểu bảng bị mã hoá thành "a0", "TableNormal0". Pandoc ghi
     tblStyle="Table" không khớp id nào, LibreOffice mất luôn cấu trúc bảng: khung
     rỗng còn chữ trong ô rơi xuống dưới dạng đoạn văn.

Script gỡ font nhúng và thêm một kiểu bảng có styleId "Table" kèm kẻ khung.

Cách dùng: python3 Report/make-reference-doc.py <form.docx> <reference-clean.docx>
"""
import re
import sys
import zipfile

# Pandoc luôn tham chiếu các styleId này. Form mẫu do người Việt soạn có styleId bị
# mã hoá ("a", "a0"...) nên pandoc không ánh xạ được, để thiếu thì LibreOffice mất
# cấu trúc bảng: khung rỗng, chữ trong ô rơi xuống thành đoạn văn.
PARAGRAPH_STYLE_IDS = [
    ("BodyText", "Body Text"),
    ("FirstParagraph", "First Paragraph"),
    ("Compact", "Compact"),
    ("ImageCaption", "Image Caption"),
    ("CaptionedFigure", "Captioned Figure"),
    ("Figure", "Figure"),
    ("SourceCode", "Source Code"),
]

PARAGRAPH_STYLE_TEMPLATE = (
    '<w:style w:type="paragraph" w:customStyle="1" w:styleId="{sid}">'
    '<w:name w:val="{name}"/>'
    '<w:basedOn w:val="Normal"/>'
    '<w:qFormat/>'
    "</w:style>"
)

TABLE_STYLE = """<w:style w:type="table" w:styleId="Table">
<w:name w:val="Table"/>
<w:basedOn w:val="TableNormal"/>
<w:uiPriority w:val="99"/>
<w:tblPr>
<w:tblBorders>
<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>
<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>
<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>
<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>
<w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>
<w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>
</w:tblBorders>
<w:tblCellMar>
<w:top w:type="dxa" w:w="57"/>
<w:left w:type="dxa" w:w="115"/>
<w:bottom w:type="dxa" w:w="57"/>
<w:right w:type="dxa" w:w="115"/>
</w:tblCellMar>
</w:tblPr>
</w:style>"""


def strip_embedded_fonts(name, data):
    """Gỡ khai báo font nhúng để pandoc không tham chiếu tới file font bị thiếu."""
    if name == "word/fontTable.xml":
        text = data.decode("utf-8")
        text = re.sub(r"<w:embed(Regular|Bold|Italic|BoldItalic)\b[^>]*/>", "", text)
        return text.encode("utf-8")
    if name == "word/_rels/fontTable.xml.rels":
        text = data.decode("utf-8")
        text = re.sub(r"<Relationship[^>]*font[^>]*/>", "", text)
        return text.encode("utf-8")
    return data


def add_missing_styles(data):
    """Thêm kiểu bảng và các kiểu đoạn mà pandoc tham chiếu nhưng form mẫu thiếu."""
    text = data.decode("utf-8")
    added = []
    for sid, name in PARAGRAPH_STYLE_IDS:
        if f'w:styleId="{sid}"' in text:
            continue
        text = text.replace(
            "</w:styles>",
            PARAGRAPH_STYLE_TEMPLATE.format(sid=sid, name=name) + "</w:styles>",
        )
        added.append(sid)
    if 'w:styleId="Table"' in text:
        print("Đã thêm kiểu:", ", ".join(added) if added else "không có")
        return text.encode("utf-8")
    # TableNormal phải tồn tại vì kiểu mới kế thừa từ nó
    if 'w:styleId="TableNormal"' not in text:
        style = TABLE_STYLE.replace('<w:basedOn w:val="TableNormal"/>', "")
    else:
        style = TABLE_STYLE
    text = text.replace("</w:styles>", style + "</w:styles>")
    print("Đã thêm kiểu:", ", ".join(added + ["Table"]))
    return text.encode("utf-8")


def main():
    src = sys.argv[1]
    dst = sys.argv[2]
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            data = strip_embedded_fonts(name, zin.read(name))
            if name == "word/styles.xml":
                data = add_missing_styles(data)
            zout.writestr(name, data)
    print(f"Đã dựng reference-doc sạch: {dst}")


if __name__ == "__main__":
    main()
