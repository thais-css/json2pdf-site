import io
import os
import json
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime
import streamlit as st

from core.json_to_pdf import (
    generate_content_pdf,
    generate_index_pdf,
    merge_pdfs,
    find_client_name_in_tree,
)
from core.package_client import (
    zip_with_password,
    gen_password,
)

APP_ROOT = Path(__file__).resolve().parent
CFG_PATH = APP_ROOT / "config" / "config.json"

def load_config():
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_upload_to_temp(uploaded_file, workdir):
    zpath = Path(workdir) / "input.zip"
    with open(zpath, "wb") as f:
        f.write(uploaded_file.read())
    with zipfile.ZipFile(zpath, "r") as zf:
        zf.extractall(workdir)
    return workdir

def collect_paths(root):
    root = Path(root)
    json_files = list(root.rglob("*.json"))
    return json_files

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()

st.set_page_config(page_title="JSON to PDF, ZIP with password", page_icon="📄")
st.title("JSON to PDF [plus optional password protected ZIP]")

st.write("Upload um arquivo .zip com sua pasta de dados. O app extrai, gera PDFs, mescla e oferece download.")
st.write("Limite típico de upload no Streamlit Cloud, perto de 200 MB. Se possível, compacte sem fontes pesadas.")

cfg = load_config()

with st.form("upload_form"):
    up = st.file_uploader("Envie um .zip com seus dados", type=["zip"])
    make_zip = st.checkbox("Gerar ZIP com senha, contendo o PDF final", value=True)
    submit = st.form_submit_button("Processar")

if submit:
    if not up:
        st.error("Por favor, selecione um arquivo .zip")
        st.stop()

    with st.spinner("Processando, extraindo, gerando PDFs"):
        workdir = tempfile.mkdtemp(prefix="job_")
        extract_upload_to_temp(up, workdir)

        # descobrir nome do cliente, se existir em algum JSON
        client_name = find_client_name_in_tree(workdir) or "client"

        out_dir = Path(workdir) / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        content_pdf = out_dir / f"{client_name}_content.pdf"
        index_pdf   = out_dir / f"{client_name}_index.pdf"
        merged_pdf  = out_dir / f"{client_name}_merged.pdf"

        # gerar PDFs
        generate_content_pdf(base_folder=workdir, out_pdf_path=content_pdf, cfg=cfg)
        generate_index_pdf(index_data_path=None, out_pdf_path=index_pdf, cfg=cfg, base_folder=workdir)

        # mesclar
        merge_pdfs(content_pdf, index_pdf, merged_pdf)

        st.success("PDF gerado e mesclado com sucesso")

        # download do PDF final
        st.download_button(
            label="Baixar PDF final",
            data=read_bytes(merged_pdf),
            file_name=merged_pdf.name,
            mime="application/pdf",
        )

        if make_zip:
            st.divider()
            password = gen_password(14)
            zip_bytes = io.BytesIO()
            zip_name = f"{client_name}_data.zip"

            # aqui colocamos só o PDF mesclado dentro do ZIP, simples e leve
            zip_with_password(
                files=[(merged_pdf, merged_pdf.name)],
                zip_stream=zip_bytes,
                password=password,
            )
            zip_bytes.seek(0)

            st.write("Senha gerada para o ZIP, copie e guarde com segurança")
            st.code(password)

            st.download_button(
                label="Baixar ZIP com senha",
                data=zip_bytes.getvalue(),
                file_name=zip_name,
                mime="application/zip",
            )

        st.info("Os arquivos temporários serão apagados automaticamente quando a sessão encerrar.")

