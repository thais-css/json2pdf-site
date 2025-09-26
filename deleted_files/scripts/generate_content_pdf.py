import os
import json
from fpdf import FPDF, XPos, YPos
import tarfile
import shutil

def generate_safe_folder_name(name):
    # [Função generate_safe_folder_name - igual ao seu script original]
    accents = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u',
        'ç': 'c',
        'ñ': 'n'
    }

    safe_name = ''.join(accents.get(char.lower(), char) for char in name)
    safe_name = ''.join(char for char in safe_name if char.isalnum() or char in [' ', '_', '-'])
    safe_name = safe_name.replace(' ', '_')
    while '__' in safe_name:
        safe_name = safe_name.replace('__', '_')
    safe_name = safe_name.strip('_')
    return safe_name

def move_existing_folder(output_folder, safe_first_name):
    existing_folder = os.path.join(output_folder, f"{safe_first_name}_data")
    old_files_folder = os.path.join(output_folder, "Old Files")
    
    if os.path.exists(existing_folder):
        if not os.path.exists(old_files_folder):
            os.makedirs(old_files_folder, exist_ok=True)
        
        counter = 1
        new_location = os.path.join(old_files_folder, f"{safe_first_name}_data")
        while os.path.exists(new_location):
            new_location = os.path.join(old_files_folder, f"{safe_first_name}_data_{counter}")
            counter += 1
        
        shutil.move(existing_folder, new_location)
        print(f"Existing folder moved to: {new_location}")

def load_config():
    # [Função load_config - igual ao seu script original]
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(script_dir, "config", "config.json")
    try:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Error: Could not find config file at '{config_path}'.  Please ensure the file exists.")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Error: Could not decode JSON in config file at '{config_path}'.  The file may be corrupted.  Details: {e}", e.doc, e.pos)
    except Exception as e:
        raise Exception(f"Error: An unexpected error occurred while loading the config file at '{config_path}'. Details: {e}")

    for key, value in config.items():
        if isinstance(value, str):
            absolute_path = os.path.join(script_dir, value)
            if not os.path.exists(absolute_path):
                print(f"Warning: Path '{value}' in config.json does not exist at '{absolute_path}'. The script may not function correctly.")
            config[key] = absolute_path

    return config

class ContentPDF(FPDF): # Renomeamos a classe PDF para ContentPDF
    def __init__(self, config):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.config = config
        self.index_data = [] # Vamos usar para coletar dados do índice
        try:
            self.add_noto_sans_font() # Alterado para Noto Sans
        except Exception as e:
            print(f"Error: Failed to add Noto Sans font. This may be due to font file issues. Details: {e}")

    def add_noto_sans_font(self): # Alterado para Noto Sans
        # [Função para adicionar Noto Sans fonts]
        try:
            self.add_font("NotoSans", "", self.config["font_regular"]) # Alterado para NotoSans
            self.add_font("NotoSans", "B", self.config["font_bold"]) # Alterado para NotoSans Bold
            self.set_font("NotoSans", size=12) # Alterado para NotoSans
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Error: Could not find the specified Noto Sans font file.  Please check font_regular and font_bold paths in config.json. Details: {e}")
        except Exception as e:
            raise Exception(f"Error: An unexpected error occurred while adding the Noto Sans font.  Details: {e}")

    def footer(self):
        # [Função footer - igual ao seu script original]
        self.set_y(-15)
        self.set_font("NotoSans", size=7) # Alterado para NotoSans
        self.cell(0, 10, str(self.page_no()), align="C")

    def add_subtitle(self, subtitle):
        # [Função add_subtitle - Modificada para coletar dados do índice]
        page_number = self.page_no()
        if subtitle == "Charms":
            subtitle = "SuperCrushes"
        self.index_data.append({'title': subtitle, 'page': page_number}) # Salva dados para o índice
        self.set_font("NotoSans", "B", 11) # Alterado para NotoSans Bold
        if self.get_y() > 260:
            self.add_page()
        self.cell(0, 10, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.ln(3)

    def add_logo(self):
        # [Função add_logo - igual ao seu script original]
        logo_path = self.config.get("logo_path", "")
        if os.path.exists(logo_path):
            self.image(logo_path, x=170, y=10, w=30)
        self.set_y(25)

    def header(self):
        # [Função header - igual ao seu script original]
        self.add_logo()

    def add_title(self, title):
        # [Função add_title - igual ao seu script original]
        self.set_font("NotoSans", "B", 16) # Alterado para NotoSans Bold
        self.ln(3)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(5)

    def add_text(self, text):
        # [Função add_text - igual ao seu script original]
        self.set_font("NotoSans", size=8) # Alterado para NotoSans
        self.multi_cell(0, 5, text, align="L")
        self.ln(1)


def find_data_folder(base_folder):
    # [Função find_data_folder - igual ao seu script original]
    try:
        for root, dirs, _ in os.walk(base_folder):
            if dirs:
                return os.path.join(root, dirs[0])
        raise FileNotFoundError("Error: No folder with subfolders found inside the specified base directory.")
    except FileNotFoundError:
        raise
    except Exception as e:
        raise Exception(f"Error: An unexpected error occurred while trying to find the data folder.  Details: {e}")

def read_json_files(folder_path):
    # [Função read_json_files - igual ao seu script original]
    folder_data = {}
    try:
        for root, _, files in os.walk(folder_path):
            relative_path = os.path.relpath(root, folder_path).replace("\\", "/")
            if relative_path == ".":
                continue
            folder_name = relative_path.split("/")[-1].capitalize()

            if folder_name == "Charms":
                folder_name = "SuperCrushes"

            if folder_name == "Media":
                folder_data[folder_name] = [{"text": "Please, check the folder Media."}]
                continue

            folder_data[folder_name] = []

            if folder_name == "Other":
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as other_file:
                            folder_data[folder_name].append({"text": other_file.read()})
                    except FileNotFoundError:
                        print(f"Warning: Could not find file '{file_path}'. It will be skipped.")
                    except Exception as e:
                        print(f"Warning: Could not read file '{file_path}'. It will be skipped. Details: {e}")
                continue

            json_files = [file for file in files if file.endswith(".json")]
            if not json_files:
                folder_data[folder_name].append({"folder_status": "No content."})
            else:
                for file in json_files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as json_file:
                            try:
                                data = json.load(json_file)
                                folder_data[folder_name].append(data if data else {"folder_status": "No content."})
                            except json.JSONDecodeError as e:
                                print(f"Warning: Could not decode JSON in file '{file_path}'.  File will be skipped. Details: {e}")
                                folder_data[folder_name].append({"folder_status": "No content."})
                            except Exception as e:
                                print(f"Warning: An unexpected error occurred while reading JSON file '{file_path}'.  File will be skipped. Details: {e}")
                                folder_data[folder_name].append({"folder_status": "Error reading file."})
                    except FileNotFoundError:
                        print(f"Warning: Could not find file '{file_path}'. It will be skipped.")
                    except Exception as e:
                        print(f"Warning: Could not open or read file '{file_path}'. It will be skipped. Details: {e}")
        return {k: v for k, v in sorted(folder_data.items())}
    except Exception as e:
        raise Exception(f"Error: An unexpected error occurred while reading JSON files. Details: {e}")

def extract_title_from_backoffice(folder_data):
    try:
        backoffice_data = folder_data.get("Backoffice", [])
        for item in backoffice_data:
            if isinstance(item, dict) and "client" in item and "first_name" in item["client"]:
                # Get the original first_name 
                original_first_name = item["client"]["first_name"]
                
                # Capitalize only the first letter, make the rest lowercase
                first_name = original_first_name[0].upper() + original_first_name[1:].lower()
                
                # Create title with properly formatted name
                title = f"{first_name}' data" if first_name.endswith("s") else f"{first_name}'s data"
                return title, first_name
        return "Consolidated Data", "default_name"
    except Exception as e:
        print(f"Warning: An unexpected error occurred while extracting the title. Using default title. Details: {e}")
        return "Consolidated Data", "default_name"
    
def extract_media_to_folder(media_folder, output_folder):
    # [Função extract_media_to_folder - igual ao seu script original]
    final_media_folder = os.path.join(output_folder, "Media")
    os.makedirs(final_media_folder, exist_ok=True)
    archive_found = False

    try:
        for root, _, files in os.walk(media_folder):
            for file in files:
                if file.endswith(".tar.gz"):
                    archive_found = True
                    tar_path = os.path.join(root, file)
                    print(f"📂 Found TAR.GZ archive: {tar_path}, extracting to {final_media_folder}")
                    try:
                        with tarfile.open(tar_path, "r:gz") as tar:
                            tar.extractall(path=final_media_folder)
                    except tarfile.ReadError as e:
                        print(f"Warning: Could not open or extract TAR.GZ archive '{tar_path}'. The file might be corrupted. Details: {e}")
                    except Exception as e:
                        print(f"Warning: An unexpected error occurred while extracting TAR.GZ archive '{tar_path}'. Details: {e}")
                    print(f"✅ Files extracted to: {final_media_folder}")

        if not archive_found:
            print("⚠️ No .tar.gz files found in the Media folder.")
    except Exception as e:
        print(f"Warning: An unexpected error occurred during media extraction. Details: {e}")


def generate_content_pdf_file(config, folder_data, output_pdf_path): # Renomeamos a função generate_pdf para generate_content_pdf_file
    """Generates the PDF with content only."""
    try:
        title, first_name = extract_title_from_backoffice(folder_data)

        pdf = ContentPDF(config) # Usamos a classe ContentPDF
        pdf.add_page()
        pdf.add_title(title)

        for folder, content in folder_data.items():
            pdf.add_subtitle(folder)
            for data in content:
                if "text" in data:
                    pdf.add_text(data["text"])
                elif "folder_status" in data:
                    pdf.add_text(data["folder_status"])
                else:
                    pdf.add_text(json.dumps(data, indent=4, ensure_ascii=False))
            pdf.ln(5)

        pdf.output(output_pdf_path)
        print(f"Content PDF generated successfully: {output_pdf_path}")
        return pdf.index_data # Retorna os dados do índice para o próximo script
    except Exception as e:
        print(f"Error: An unexpected error occurred during Content PDF generation. Details: {e}")
        return None

def main():
    try:
        config = load_config()
        base_folder = config["base_folder"] # Pega base_folder da config
        folder_path = find_data_folder(base_folder)
        folder_data = read_json_files(folder_path)

        title, first_name = extract_title_from_backoffice(folder_data)
        safe_first_name = generate_safe_folder_name(first_name)
        output_folder = os.path.join(os.path.dirname(config["output_pdf"]), f"{safe_first_name}_data")
        os.makedirs(output_folder, exist_ok=True)
        output_content_pdf_path = os.path.join(output_folder, f"{safe_first_name}_content.pdf") # PDF de conteúdo
        config["output_pdf"] = output_content_pdf_path # Atualiza config para usar no merge depois

        index_data = generate_content_pdf_file(config, folder_data, output_content_pdf_path) # Gera PDF de conteúdo e pega dados do índice
        if index_data:
            # Salva os dados do índice em um arquivo temporário para o próximo script usar
            index_data_path = os.path.join(output_folder, "index_data.json")
            with open(index_data_path, 'w') as f:
                json.dump(index_data, f)
            extract_media_to_folder(base_folder, output_folder) # Extrai media para a pasta final
        else:
            print("Content PDF generation failed. Index PDF will not be generated.")


    except Exception as e:
        print(f"Fatal error in content PDF generation: The program could not complete successfully. Details: {e}")

if __name__ == "__main__":
    main()