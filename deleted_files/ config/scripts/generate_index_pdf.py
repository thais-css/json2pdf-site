import os
import json
from fpdf import FPDF, XPos, YPos

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

class IndexPDF(FPDF): # Class for the index PDF
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.set_auto_page_break(auto=True, margin=15)  # Adding auto page break like in ContentPDF
        try:
            self.add_noto_sans_font() # Changed to NotoSans
        except Exception as e:
            print(f"Error: Failed to add Noto Sans font for index PDF. Details: {e}")

    def add_noto_sans_font(self): # Changed to NotoSans
        # [Function to add Noto Sans fonts]
        try:
            self.add_font("NotoSans", "", self.config["font_regular"]) # Changed to NotoSans
            self.add_font("NotoSans", "B", self.config["font_bold"]) # Changed to NotoSans Bold
            self.set_font("NotoSans", size=12) # Changed to NotoSans
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Error: Could not find font file for index PDF. Check config.json. Details: {e}")
        except Exception as e:
            raise Exception(f"Error: An unexpected error occurred adding Noto Sans font for index PDF. Details: {e}")

    def add_logo(self):
        # Adding logo function similar to ContentPDF
        logo_path = self.config.get("logo_path", "")
        if os.path.exists(logo_path):
            self.image(logo_path, x=170, y=10, w=30)
        self.set_y(25)

    def header(self):
        # Adding header function to display the logo
        self.add_logo()

    def footer(self):
        # Adding footer similar to ContentPDF
        self.set_y(-15)
        self.set_font("NotoSans", size=7)
        self.cell(0, 10, str(self.page_no()), align="C")

    def create_index_page(self):
        """Creates the first page, reserved for the table of contents."""
        self.add_page()
        self.set_font("NotoSans", "B", 14) # Changed to NotoSans Bold
        self.cell(0, 10, "Index", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(10)

    def fill_index(self, index_data):
        """Fills the index page with sections and their page numbers."""
        self.set_y(30)
        self.set_font("NotoSans", size=9) # Changed to NotoSans

        for section_info in index_data:
            section = section_info['title']
            page = section_info['page']

            if section == "Charms":
                section = "SuperCrushes"

            section_width = self.get_string_width(section)
            page_text = str(page)
            page_width = self.get_string_width(page_text)

            # Adding extra spaces
            extra_space_after_section = "  "  # 2 spaces after folder name
            extra_space_before_page_number = "  "  # 2 spaces before page number

            section_with_space = section + extra_space_after_section
            page_text_with_space = extra_space_before_page_number + page_text

            # Adjusting available width for dots
            available_width = self.w - self.l_margin - self.r_margin - self.get_string_width(section_with_space) - self.get_string_width(page_text_with_space) - 4
            dots = "." * int(available_width / self.get_string_width("."))

            # Writing to the index
            self.cell(self.get_string_width(section_with_space), 8, section_with_space, align="L")
            self.cell(available_width, 8, dots, align="C")
            self.cell(self.get_string_width(page_text_with_space), 8, page_text_with_space, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(3)
            
def generate_index_pdf_file(config, index_data, output_pdf_path): # Função para gerar o PDF de índice
    """Generates the Index PDF."""
    try:
        pdf = IndexPDF(config) # Usa a classe IndexPDF
        pdf.create_index_page()
        pdf.fill_index(index_data) # Preenche o índice com os dados passados

        pdf.output(output_pdf_path)
        print(f"Index PDF generated successfully: {output_pdf_path}")
    except Exception as e:
        print(f"Error: An unexpected error occurred during Index PDF generation. Details: {e}")

def main():
    try:
        config = load_config()
        output_base_folder = os.path.dirname(config["output_pdf"])  # Pega a pasta 'output'
        
        # Encontrar a pasta do usuário (a que termina com "_data")
        user_folder = None
        for folder in os.listdir(output_base_folder):
            if folder.endswith("_data") and os.path.isdir(os.path.join(output_base_folder, folder)):
                user_folder = os.path.join(output_base_folder, folder)
                break  # Assume que só há um usuário por vez

        if not user_folder:
            print("Error: No user data folder found inside output.")
            return

        index_data_path = os.path.join(user_folder, "index_data.json")
        output_index_pdf_path = os.path.join(user_folder, "index.pdf")  # Salvar dentro da pasta correta

        try:
            with open(index_data_path, 'r') as f:
                index_data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Index data file '{index_data_path}' not found. Cannot generate Index PDF.")
            return
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in index data file '{index_data_path}'. Cannot generate Index PDF.")
            return

        generate_index_pdf_file(config, index_data, output_index_pdf_path)  # Gerar index.pdf na pasta correta

    except Exception as e:
        print(f"Fatal error in index PDF generation: The program could not complete successfully. Details: {e}")


if __name__ == "__main__":
    main()
