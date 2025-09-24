import os
import json
from pathlib import Path
from fpdf import FPDF
import fitz  # PyMuPDF

def _ensure_fonts(pdf, cfg):
    """Tenta carregar Noto se existir, senão usa Helvetica básica."""
    font_regular = cfg.get("font_regular")
    font_bold = cfg.get("font_bold")

    try:
        if font_regular and Path(font_regular).exists():
            pdf.add_font("NotoSans", "", font_regular)
            pdf.set_font("NotoSans", "", 11)
            if font_bold and Path(font_bold).exists():
                pdf.add_font("NotoSans", "B", font_bold)
        else:
            pdf.set_font("helvetica", "", 11)
    except Exception:
        pdf.set_font("helvetica", "", 11)

def _new_page(pdf, title=None):
    pdf.add_page()
    if title:
        try:
            pdf.set_font("NotoSans", "B", 14)
        except Exception:
            pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, title, ln=1)

def _list_json_files(base_folder):
    return list(Path(base_folder).rglob("*.json"))

def _safe_text(s, max_len=800):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False)
    s = s.replace("\r", " ").replace("\n", " ")
    if len(s) > max_len:
        s = s[:max_len] + " ..."
    return s

def find_client_name_in_tree(base_folder):
    """Procura por uma chave client.first_name em qualquer JSON, retorna string ou None."""
    for jpath in _list_json_files(base_folder):
        try:
            data = json.loads(Path(jpath).read_text(encoding="utf-8", errors="ignore"))
            # tentar caminhos comuns
            first_name = (
                data.get("client", {}).get("first_name")
                if isinstance(data, dict) else None
            )
            if first_name and isinstance(first_name, str) and first_name.strip():
                return "".join(first_name.split())
        except Exception:
            continue
    return None

def generate_content_pdf(base_folder, out_pdf_path, cfg):
    """Versão simples, lista arquivos JSON e mostra algumas chaves, pronta para trocar pelo seu layout."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    _ensure_fonts(pdf, cfg)

    _new_page(pdf, "Content")
    pdf.set_font_size(10)

    json_files = _list_json_files(base_folder)
    if not json_files:
        pdf.multi_cell(0, 5, "No JSON files found under the uploaded zip")
    else:
        pdf.multi_cell(0, 5, f"Found {len(json_files)} JSON files")
        pdf.ln(5)

    for idx, jpath in enumerate(json_files, start=1):
        pdf.set_font_size(11)
        pdf.multi_cell(0, 6, f"[{idx}] {jpath.relative_to(base_folder)}")
        pdf.set_font_size(9)
        try:
            data = json.loads(Path(jpath).read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, dict):
                keys = list(data.keys())[:12]
                pdf.multi_cell(0, 5, "Keys preview: " + ", ".join(keys))
            else:
                pdf.multi_cell(0, 5, "JSON is not an object at the top level")
        except Exception as e:
            pdf.multi_cell(0, 5, f"Error reading JSON, {e}")
        pdf.ln(2)

    out_pdf_path = Path(out_pdf_path)
    out_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_pdf_path))

def generate_index_pdf(index_data_path, out_pdf_path, cfg, base_folder=None):
    """Índice simples, enumerando arquivos JSON. Pode ligar com index_data se você já tiver esse arquivo."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    _ensure_fonts(pdf, cfg)

    _new_page(pdf, "Index")
    pdf.set_font_size(10)

    if index_data_path and Path(index_data_path).exists():
        try:
            data = json.loads(Path(index_data_path).read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else []
        except Exception:
            items = []
    else:
        # fallback, lista JSONs do diretório
        items = [str(p.relative_to(base_folder)) for p in _list_json_files(base_folder or ".")]

    if not items:
        pdf.multi_cell(0, 5, "No index data available")
    else:
        for i, it in enumerate(items, start=1):
            pdf.multi_cell(0, 5, f"{i}. {it}")

    out_pdf_path = Path(out_pdf_path)
    out_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_pdf_path))

def merge_pdfs(content_pdf, index_pdf, out_pdf):
    content_pdf = Path(content_pdf)
    index_pdf = Path(index_pdf)
    out_pdf = Path(out_pdf)

    with fitz.open() as merged:
        if index_pdf.exists():
            with fitz.open(str(index_pdf)) as idx_doc:
                merged.insert_pdf(idx_doc)
        if content_pdf.exists():
            with fitz.open(str(content_pdf)) as c_doc:
                merged.insert_pdf(c_doc)
        merged.save(str(out_pdf))

