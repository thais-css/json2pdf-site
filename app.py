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
DF_SRC = APP_ROOT / "deleted_files"      # sua pasta com scripts e config do Deleted Files
SCRIPTS_DIR = DF_SRC / "scripts"


# ===================== helpers básicas =====================

def extract_upload_to_temp(uploaded_file):
    workdir = Path(tempfile.mkdtemp(prefix="job_"))
    inzip = workdir / "input.zip"
    with open(inzip, "wb") as f:
        f.write(uploaded_file.read())
    with zipfile.ZipFile(inzip, "r") as zf:
        zf.extractall(workdir)
    return workdir

def detect_structured_export(root: Path) -> bool:
    # verdadeiro se existir index.html em algum nível
    return any(root.rglob("index.html"))

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


# ===================== detecção de nome, estruturado =====================

def find_first_folder_data_name(root: Path):
    # procura por pasta *_data no topo
    for p in root.iterdir():
        if p.is_dir() and p.name.endswith("_data"):
            return p.name[:-5]  # remove "_data"
    # procura recursivo
    for p in root.rglob("*"):
        if p.is_dir() and p.name.endswith("_data"):
            return p.name[:-5]
    return None

def find_client_name_from_backoffice_json(root: Path):
    # acha */all-data/backoffice, pega o primeiro .json e lê .client.first_name
    backoffice = None
    for p in root.rglob("*"):
        if p.is_dir() and str(p).replace("\\", "/").endswith("all-data/backoffice"):
            backoffice = p
            break
    if not backoffice:
        return None

    json_file = None
    for j in backoffice.rglob("*.json"):
        json_file = j
        break
    if not json_file:
        return None

    try:
        data = json.loads(json_file.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, dict):
            first = data.get("client", {}).get("first_name")
            if isinstance(first, str) and first.strip():
                return "".join(first.split())
    except Exception:
        return None
    return None

def find_client_name_from_index_html(root: Path):
    # tenta extrair do <title> ou <h1>
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

def resolve_client_name_structured(root: Path, prefer_manual: bool = True):
    # 1 pasta *_data, 2 backoffice JSON, 3 index.html, 4 input manual
    name = find_first_folder_data_name(root)
    if name:
        return name
    name = find_client_name_from_backoffice_json(root)
    if name:
        return name
    name = find_client_name_from_index_html(root)
    if name:
        return name
    if prefer_manual:
        return st.text_input("Nome do cliente não detectado automaticamente, digite aqui", "client")
    return "client"


# ===================== detecção de nome, bruto =====================

def find_client_name_in_json_tree(root: Path):
    # procura por qualquer *.json com client.first_name
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


# ===================== pipeline Deleted Files, sem alterar seus scripts =====================

def run_deleted_files_pipeline(raw_root: Path):
    """
    Executa seus 3 scripts sem alterar lógica.
    1 copia deleted_files para temp
    2 coloca o conteúdo bruto em temp/deleted_files/data
    3 roda generate_content_pdf.py, generate_index_pdf.py, merge_pdfs.py via subprocess
    4 retorna merged.pdf e pasta de mídia se existir
    """
    tmp_df = Path(tempfile.mkdtemp(prefix="df_"))
    shutil.copytree(DF_SRC, tmp_df / "deleted_files", dirs_exist_ok=True)
    run_root = tmp_df / "deleted_files"

    data_dir = run_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    copy_tree(raw_root, data_dir)

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
    pdfs = list(output_dir.glob("*.pdf"))
    if pdfs:
        merged_candidates = [p for p in pdfs if "merged" in p.name.lower() or "final" in p.name.lower()]
        merged = merged_candidates[0] if merged_candidates else pdfs[0]

    media_dir = None
    # tenta localizar imagens na saída do seu pipeline
    for candidate in ["images", "Media/images", "media/images"]:
        c = output_dir / candidate
        if c.exists() and c.is_dir():
            media_dir = c
            break

    return merged, media_dir, output_dir, run_root


# ===================== montagem de pacote para Processar Dados =====================

def build_stage_for_packaging(merged_pdf: Path, media_dir: Path | None):
    """
    Cria uma pasta package contendo o PDF final e a pasta images se houver.
    """
    out_parent = Path(tempfile.mkdtemp(prefix="stage_"))
    stage = out_parent / "package"
    stage.mkdir(parents=True, exist_ok=True)

    if merged_pdf and merged_pdf.exists():
        shutil.copy2(merged_pdf, stage / merged_pdf.name)

    if media_dir and media_dir.exists():
        dest_media = stage / "images"
        shutil.copytree(media_dir, dest_media, dirs_exist_ok=True)

    return stage


# ===================== UI =====================

st.set_page_config(page_title="Deleted Files + Processar Dados", page_icon="📦")
st.title("Processador com detecção automática")

st.write("Envie um .zip. Se tiver index.html, trata como export estruturado e só empacota com senha. Se não tiver, trata como export bruto, roda Deleted Files para gerar PDF e mídia, e depois empacota com senha.")

up = st.file_uploader("Envie um .zip", type=["zip"])
if st.button("Processar"):

    if not up:
        st.error("Selecione um .zip")
        st.stop()

    with st.spinner("Processando"):
        workdir = extract_upload_to_temp(up)
        root = workdir

        if detect_structured_export(root):
            # fluxo estruturado, só Processar Dados
            client = resolve_client_name_structured(root)

            # copiar tudo como está para stage_raw
            stage_parent = Path(tempfile.mkdtemp(prefix="stage_"))
            stage_raw = stage_parent / "package_raw"
            stage_raw.mkdir(parents=True, exist_ok=True)
            copy_tree(root, stage_raw)

            # envolver em FIRSTNAME_data
            named_root = stage_parent / f"{client}_data"
            shutil.move(str(stage_raw), str(named_root))

            zip_name, password, zip_bytes = zip_stage_with_password(named_root, client)

            st.success("Export estruturado detectado. Pacote protegido criado.")
            st.write("Senha do ZIP, copie e envie ao usuário.")
            st.code(password)
            st.download_button("Baixar ZIP", data=zip_bytes.getvalue(), file_name=zip_name, mime="application/zip")

        else:
            # fluxo bruto, Deleted Files depois Processar Dados
            client = find_client_name_in_json_tree(root) or st.text_input("Nome do cliente não detectado automaticamente, digite aqui", "client")

            # roda seus scripts sem alterar lógica
            try:
                merged_pdf, media_dir, out_dir, run_root = run_deleted_files_pipeline(root)
            except Exception as e:
                st.error(f"Erro ao executar Deleted Files. Detalhes, {e}")
                st.stop()

            if not merged_pdf or not merged_pdf.exists():
                st.error("Não foi possível localizar o PDF final gerado.")
                st.stop()

            st.success("PDF gerado com sucesso pelo Deleted Files.")
            st.download_button(
                "Baixar PDF final",
                data=merged_pdf.read_bytes(),
                file_name=merged_pdf.name,
                mime="application/pdf",
            )

            # monta pacote para Processar Dados
            stage = build_stage_for_packaging(merged_pdf, media_dir)

            # envolver em FIRSTNAME_data antes de zipar
            stage_parent = Path(tempfile.mkdtemp(prefix="stage_"))
            named_root = stage_parent / f"{client}_data"
            shutil.copytree(stage, named_root, dirs_exist_ok=True)

            zip_name, password, zip_bytes = zip_stage_with_password(named_root, client)

            st.write("ZIP com senha criado.")
            st.write("Senha do ZIP, copie e envie ao usuário.")
            st.code(password)
            st.download_button(
                "Baixar ZIP com PDF e mídia",
                data=zip_bytes.getvalue(),
                file_name=zip_name,
                mime="application/zip",
            )

    st.caption("Arquivos temporários são removidos quando a sessão termina.")
