import io
import os
import re
import json
import zipfile
import shutil
import tempfile
import subprocess
from pathlib import Path
import streamlit as st

from core.package_client import gen_password, zip_with_password

APP_ROOT = Path(__file__).resolve().parent
DF_SRC = APP_ROOT / "deleted_files"      # pasta com seus scripts e config
SCRIPTS_DIR = DF_SRC / "scripts"

def extract_upload_to_temp(uploaded_file):
    workdir = Path(tempfile.mkdtemp(prefix="job_"))
    inzip = workdir / "input.zip"
    with open(inzip, "wb") as f:
        f.write(uploaded_file.read())
    with zipfile.ZipFile(inzip, "r") as zf:
        zf.extractall(workdir)
    return workdir

def detect_structured_export(root):
    # verdadeiro se existir index.html em algum nível
    return any(root.rglob("index.html"))

def find_client_name_from_index_html(root):
    for p in root.rglob("index.html"):
        try:
            html = p.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            if m:
                name = re.sub(r"\s+", "", m.group(1).strip())
                if name:
                    return name
            m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
            if m:
                name = re.sub(r"\s+", "", m.group(1).strip())
                if name:
                    return name
        except Exception:
            continue
    return None

def find_client_name_in_json_tree(root):
    for p in root.rglob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, dict):
                first = data.get("client", {}).get("first_name")
                if isinstance(first, str) and first.strip():
                    return "".join(first.split())
        except Exception:
            continue
    return None

def copy_tree(src, dst):
    src = Path(src)
    dst = Path(dst)
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if p.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
        else:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(p, dst / rel)
            except Exception:
                pass

def run_deleted_files_pipeline(raw_root):
    """
    Executa seus 3 scripts sem alterar a lógica.
    Estratégia:
    1, cria uma cópia temporária da pasta deleted_files
    2, coloca o conteúdo bruto extraído dentro de temp_deleted_files/data
    3, roda os 3 scripts via subprocess, com cwd na pasta temp_deleted_files
    4, coleta o PDF final e a pasta de mídia gerada pelos scripts
    Retorna paths do merged.pdf e da pasta de mídia se existir
    """
    tmp_df = Path(tempfile.mkdtemp(prefix="df_"))
    # copiar sua pasta deleted_files inteira para o temporário
    shutil.copytree(DF_SRC, tmp_df / "deleted_files", dirs_exist_ok=True)
    run_root = tmp_df / "deleted_files"

    # criar data e mover o bruto para lá
    data_dir = run_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    copy_tree(raw_root, data_dir)

    # rodar scripts
    def _run(pyfile):
        cmd = [os.environ.get("PYTHON", "python"), str(SCRIPTS_DIR / pyfile)]
        p = subprocess.run(cmd, cwd=run_root, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"{pyfile} falhou\nstdout\n{p.stdout}\nstderr\n{p.stderr}")

    _run("generate_content_pdf.py")
    _run("generate_index_pdf.py")
    _run("merge_pdfs.py")

    output_dir = run_root / "output"
    merged = None
    # procurar um PDF final no output. se houver nome fixo no config, você já sabe o nome
    pdfs = list(output_dir.glob("*.pdf"))
    if pdfs:
        # priorizar merged
        merged_candidates = [p for p in pdfs if "merged" in p.name.lower() or "final" in p.name.lower()]
        merged = merged_candidates[0] if merged_candidates else pdfs[0]

    # pasta de mídia. procurar images primeiro
    media_dir = None
    for candidate in ["images", "Media/images", "media/images"]:
        c = output_dir / candidate
        if c.exists() and c.is_dir():
            media_dir = c
            break

    return merged, media_dir, output_dir, run_root

def build_stage_for_packaging(base_root, merged_pdf, media_dir):
    """
    Monta uma pasta package com o PDF e a pasta images, se houver.
    """
    out_parent = Path(tempfile.mkdtemp(prefix="stage_"))
    stage = out_parent / "package"
    stage.mkdir(parents=True, exist_ok=True)

    if merged_pdf:
        shutil.copy2(merged_pdf, stage / merged_pdf.name)

    if media_dir and media_dir.exists():
        dest_media = stage / "images"
        shutil.copytree(media_dir, dest_media, dirs_exist_ok=True)

    return stage

def zip_stage_with_password(stage_dir, client_name):
    password = gen_password(14)
    zip_bytes = io.BytesIO()
    zip_name = f"{client_name}_data.zip"

    files = []
    for p in Path(stage_dir).rglob("*"):
        if p.is_file():
            arcname = p.relative_to(stage_dir).as_posix()
            files.append((p, arcname))

    zip_with_password(files=files, zip_stream=zip_bytes, password=password)
    zip_bytes.seek(0)
    return zip_name, password, zip_bytes

st.set_page_config(page_title="Deleted Files + Processar Dados", page_icon="📦")
st.title("Processador de export. Detecção automática")

st.write("Envie um .zip. O app detecta se é export estruturado [com index.html] ou export bruto.")
st.write("Se for bruto, roda Deleted Files, gera o PDF e a pasta de mídia, depois empacota com senha [Processar Dados].")
st.write("Se for estruturado, só empacota com senha [Processar Dados].")

up = st.file_uploader("Envie um .zip", type=["zip"])
if st.button("Processar"):

    if not up:
        st.error("Selecione um .zip")
        st.stop()

    with st.spinner("Processando"):
        # extrair upload
        workdir = extract_upload_to_temp(up)
        root = workdir

        if detect_structured_export(root):
            # caso estruturado, só empacotar com senha
            client = find_client_name_from_index_html(root) or find_client_name_in_json_tree(root) or "client"
            # montar stage com tudo como está
            stage = Path(tempfile.mkdtemp(prefix="stage_")) / "package"
            copy_tree(root, stage)
            zip_name, password, zip_bytes = zip_stage_with_password(stage, client)

            st.success("Export estruturado detectado. Pacote protegido criado")
            st.write("Senha do ZIP, copie e envie ao usuário")
            st.code(password)
            st.download_button("Baixar ZIP", data=zip_bytes.getvalue(), file_name=zip_name, mime="application/zip")

        else:
            # caso bruto, roda Deleted Files e depois empacota
            client = find_client_name_in_json_tree(root) or "client"

            try:
                merged_pdf, media_dir, out_dir, run_root = run_deleted_files_pipeline(root)
            except Exception as e:
                st.error(f"Erro ao executar fluxo Deleted Files. Detalhes, {e}")
                st.stop()

            if not merged_pdf or not merged_pdf.exists():
                st.error("Não foi possível localizar o PDF final gerado pelos scripts")
                st.stop()

            # oferecer download do PDF
            st.success("PDF gerado pelo Deleted Files")
            st.download_button(
                "Baixar PDF final",
                data=merged_pdf.read_bytes(),
                file_name=merged_pdf.name,
                mime="application/pdf",
            )

            # montar package para Processar Dados, PDF + mídia
            stage = build_stage_for_packaging(root, merged_pdf, media_dir)
            zip_name, password, zip_bytes = zip_stage_with_password(stage, client)

            st.divider()
            st.write("ZIP com senha criado [Processar Dados]")
            st.write("Senha do ZIP, copie e envie ao usuário")
            st.code(password)
            st.download_button(
                "Baixar ZIP com PDF e mídia",
                data=zip_bytes.getvalue(),
                file_name=zip_name,
                mime="application/zip",
            )

    st.caption("Arquivos temporários são limpos quando a sessão termina")
