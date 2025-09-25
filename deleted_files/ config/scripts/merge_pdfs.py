import os
import json
import fitz  # PyMuPDF para todo o processo

def load_config():
    """Carrega a configuração sem usar caminhos absolutos"""
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Diretório do script atual
    config_path = os.path.join(script_dir, "..", "config", "config.json")  # Caminho relativo

    try:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Erro: Arquivo de configuração não encontrado em '{config_path}'.")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Erro ao decodificar JSON em config.json. Detalhes: {e}", e.doc, e.pos)
    except Exception as e:
        raise Exception(f"Erro inesperado ao carregar o config.json. Detalhes: {e}")

    return config

def find_user_folder(output_folder):
    """Encontra a pasta do usuário dentro de 'output/' (exemplo: 'Maria_data')"""
    for folder in os.listdir(output_folder):
        if folder.endswith("_data") and os.path.isdir(os.path.join(output_folder, folder)):
            return os.path.join(output_folder, folder)
    return None  # Se não encontrar, retorna None

def merge_pdfs_with_links(index_pdf_path, content_pdf_path, output_pdf_path, index_data):
    """Merges PDFs and adds links using only PyMuPDF, supporting multiple index pages"""
    try:
        # Open source documents
        index_doc = fitz.open(index_pdf_path)
        content_doc = fitz.open(content_pdf_path)
        
        # Create a new document for the final result
        result_doc = fitz.open()
        
        # Add index pages
        result_doc.insert_pdf(index_doc)
        
        # Add content pages
        result_doc.insert_pdf(content_doc)
        
        # Add links in the index - checking ALL index pages
        for index_page in range(index_doc.page_count):
            for item in index_data:
                section_title = item['title']
                # Adjust target page: original page + number of index pages
                target_page = item['page'] + index_doc.page_count - 1
                
                # Search for title text in current index page
                text_instances = result_doc[index_page].search_for(section_title)
                
                if text_instances:
                    for rect in text_instances:
                        # Create a link to the corresponding content page
                        result_doc[index_page].insert_link({
                            "kind": fitz.LINK_GOTO,
                            "from": rect,
                            "to": fitz.Point(0, 0),  # Top of page
                            "page": target_page
                        })
        
        # Add bookmarks
        toc = []  # Table of Contents (TOC)
        toc.append([1, "Index", 0])  # Level 1, title, page 0
        
        for item in index_data:
            # [Level, Title, Page]
            toc.append([2, item['title'], item['page'] + index_doc.page_count - 1])
        
        # Set TOC in document
        result_doc.set_toc(toc)
        
        # Save final document
        result_doc.save(output_pdf_path)
        print(f"✅ PDFs merged with links and bookmarks: {output_pdf_path}")
        
        # Close documents
        index_doc.close()
        content_doc.close()
        result_doc.close()
        
    except Exception as e:
        print(f"❌ Error merging PDFs with links. Details: {e}")
        raise

def delete_intermediate_files(files):
    """Remove arquivos intermediários"""
    for file in files:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"🗑️  Arquivo deletado: {file}")
            except Exception as e:
                print(f"⚠️ Erro ao deletar {file}: {e}")

def main():
    try:
        config = load_config()
        script_dir = os.path.dirname(os.path.abspath(__file__))  # Diretório do script atual
        output_base_folder = os.path.join(script_dir, "..", "output")  # Caminho relativo para output/

        # Encontra a pasta do usuário dentro de "output"
        user_folder = find_user_folder(output_base_folder)
        if not user_folder:
            print("❌ Erro: Nenhuma pasta de usuário encontrada dentro de 'output/'.")
            return

        # Extrai o nome do usuário da pasta (exemplo: 'Maria_data' -> 'Maria')
        first_name = os.path.basename(user_folder).replace("_data", "")

        # Caminhos corretos dentro da pasta do usuário
        output_index_pdf_path = os.path.join(user_folder, "index.pdf")
        output_content_pdf_path = os.path.join(user_folder, f"{first_name}_content.pdf")
        output_final_pdf_path = os.path.join(user_folder, f"{first_name}_data.pdf")  # Nome correto do PDF final
        index_data_path = os.path.join(user_folder, "index_data.json")

        # Verificar se os dados do índice existem
        if not os.path.exists(index_data_path):
            print("⚠️ Aviso: index_data.json não encontrado. O índice pode não ser clicável.")
            index_data = []
        else:
            with open(index_data_path, "r") as f:
                index_data = json.load(f)

        # Mescla os PDFs e adiciona links em uma única operação
        if index_data:
            merge_pdfs_with_links(output_index_pdf_path, output_content_pdf_path, 
                                  output_final_pdf_path, index_data)
        else:
            print("⚠️ Sem dados de índice, mesclando PDFs sem criar links...")
            # Fazemos uma mesclagem simples sem links
            doc1 = fitz.open(output_index_pdf_path)
            doc2 = fitz.open(output_content_pdf_path)
            result = fitz.open()
            result.insert_pdf(doc1)
            result.insert_pdf(doc2)
            result.save(output_final_pdf_path)
            doc1.close()
            doc2.close()
            result.close()

        # Remover arquivos intermediários
        delete_intermediate_files([output_index_pdf_path, output_content_pdf_path, index_data_path])

    except Exception as e:
        print(f"❌ Erro fatal no processo de fusão dos PDFs. Detalhes: {e}")

if __name__ == "__main__":
    main()