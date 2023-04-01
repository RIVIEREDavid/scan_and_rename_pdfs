from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
import pytesseract
from pdf2image.pdf2image import convert_from_path
import re
from datetime import datetime
import fnmatch
import typer


# déclaration des constantes
SOURCE_FILE = Path(__file__).resolve()
SOURCE_DIR = SOURCE_FILE.parent
WORKING_DIR = SOURCE_DIR / "WORKING_DIR"
WORKING_DIR.mkdir(exist_ok=True, parents=True)

# créaation de la liste contenant tous les fichiers à traiter
pdf_list = [file for file in WORKING_DIR.iterdir() if (file.is_file() and file.suffix.lower() == ".pdf")]

#Expression régulière permettant de détecter le n° de commande/programme/ENQA
regex_PO = re.compile(r"(4|5)50\d{7}")


def check_pdf_type(pdf_file):
    """Check if the pdf file is scanned or native

    Args:
        pdf_file (file): file to analyse, whether

    Returns:
        Bool: True if file is scanned, False if native
    """
    pdf_checker = PdfReader(pdf_file)
    page_text = pdf_checker.pages[0].extract_text()
    if page_text == "":
        # return "Fichier scanné"
        return True
    else:
        # return "Fichier natif"
        return False
    

def get_date(pdf_file):
    """Get creation date of the file

    Args:
        pdf_file (pdf file): file from which date is pulled out

    Returns:
        date_str: returns the date to str format
    """
    creation_date_raw = datetime.fromtimestamp(pdf_file.stat().st_mtime)
    creation_date = creation_date_raw.strftime("%Y%m%d")
    return creation_date


def get_pages(pdf_file):
    """Get the number of pages of the file

    Args:
        pdf_file (pdf_file): the file to analyze

    Returns:
        int: the number of pages in the file
    """
    reader = PdfReader(pdf_file)
    return len(reader.pages)

'''Premier tour de boucle: on récupère la date de création (ou plutôt modification) et on va renommer (en mettant la date format YYYYMMDD en début de fichier suivi de "_") tous les fichiers selon 2 cas de figure:
1. Si le fichier est scanné et contient 1 seule page --> on renomme le fichier
2. Si le fichier est scanné et contient plusieurs pages --> on splitte le fichier et on renomme les fichiers correspondants aux différentes pages, puis on efface le fichier original.
3. Si le fichier est natif --> on renomme
'''
for file in pdf_list:

    date = get_date(file) #on récupère la date de création
    pdf_reader = PdfReader(file) #création du reader pdf
    pages_count = len(pdf_reader.pages) #récupération du nombre de pages, afin de déterminer si on doit splitter ou non.

    # si on a un fichier scanné
    if check_pdf_type(file):
        # si le nombre de pages == 1 : pas besoin de splliter le document, on renomme juste dans un premier temps avec la date
        if get_pages(file) == 1:
            new_file_name = f'{date}_{file.stem}_{file.suffix}'
            #on crée un nouveau fichier avec ce nouveau nom
            new_file_path = WORKING_DIR.joinpath(new_file_name)
            file.rename(new_file_path)
        # si le nombre de pages > 1, il faut splitter et ensuite renommer chaque page avec la date de création.
        else:
            with open(file, 'rb') as input_file:
                pdf_reader = PdfReader(file)
                for num_page in range(len(pdf_reader.pages)):
                    #pour chaque page on créée un writer pdf
                    pdf_writer = PdfWriter()
                    #on ajoute la page au writer
                    pdf_writer.add_page(pdf_reader.pages[num_page])
                    #on créée un nouveau nom
                    new_file_name = f'{date}_{file.stem}_{num_page + 1}{file.suffix}'
                    #on crée un nouveau fichier avec ce nouveau nom
                    new_file_path = WORKING_DIR.joinpath(new_file_name)
                    with open(new_file_path, 'wb') as output_file:
                        pdf_writer.write(output_file)
            file.unlink()
    # si on a un fichier natif
    else:
        new_file_name = f'{date}_{file.stem}{file.suffix}'
        new_file_path = WORKING_DIR.joinpath(new_file_name)
        file.rename(new_file_path)

'''Deuxième tour de boucle: on crée une nouvelle liste avec tous les noms de fichiers issus du premier tour de boucle. 2 cas de figures:
1. Si le fichier est scanné --> on va exécute le script ocr et on détecte si la regex est présente dans l'image convertie en texte. On renomme ensuite le fichier en gardant la date et en utilisant ce numéro trouvé + l'incrément 
2. Si le fichier est natif --> on détecte si la regex est présente dans le texte du .pdf converti en str. On renomme esnuite le fichier en gardant la date et en utilisant ce numéro trouvé + l'incrément 
'''
    
# on refait une nouvelle liste avec les nouveaux fichiers issus du split, et on va ensuite lancer le script ocr pour décrypter le contenu de l'image
pdf_list_after_splitting = [file for file in WORKING_DIR.iterdir() if (file.is_file() and file.suffix.lower() == ".pdf")]

new_list = [] #nouvelle liste servant à gérer les doublons des noms de fichiers

for file in pdf_list_after_splitting:
    #si fichier pdf scanné:
    if check_pdf_type(file) == True: 
        pages = convert_from_path(file, 500)
        for pageNum, imgBlob in enumerate(pages):
            text = pytesseract.image_to_string(imgBlob, lang='eng')
            PO_list = sorted([i.group(0) for i in re.finditer(regex_PO, text)])
            PO_list_str = "_".join(set(PO_list))
        if PO_list_str == "":
            new_file_name = f"{file.stem[:8]}_ERREUR_COMMANDE"
        else:
            new_file_name = f"{file.stem[:8]}_{PO_list_str}"
        new_list.append(new_file_name)
        # on va compter à chaque fois qu'on ajoute le nom de fichier à la liste afin de récupérer un numéro qui sera unique, et servira donc de numérotation en cas de doublons, afin d'éviter les erreurs de renommage.
        existing_files = [i for i in fnmatch.filter(new_list, new_file_name)]
        final_filename = f"{new_file_name}_{len(existing_files)}{file.suffix}"
        new_file_path = WORKING_DIR.joinpath(final_filename)
        file.rename(new_file_path)
        if "ERREUR_COMMANDE" in new_file_name:
            typer.secho(f"Fichier {file.name} n'a pas pu être renommé --> N° de commande introuvable", fg=typer.colors.RED)
        else:
            typer.secho(f"Fichier {file.name} a été renommé avec succès", fg=typer.colors.GREEN)
    #si fichier pdf natif:
    elif check_pdf_type(file) == False:
        reader = PdfReader(file)
        list_pages = reader.pages
        full_pdf_text = ''
        for page in list_pages:
            text = page.extract_text()
            full_pdf_text += text
        PO_list = sorted([i.group(0) for i in re.finditer(regex_PO, full_pdf_text)])
        PO_list_str = "_".join(set(PO_list))
        # if not re.finditer(regex_PO, full_pdf_text):
        #     new_file_name = f"{file.stem[:8]}_ERREUR_COMMANDE"
        if PO_list_str == "":
            new_file_name = f"{file.stem[:8]}_ERREUR_COMMANDE"
        else:
            new_file_name = f"{file.stem[:8]}_{PO_list_str}"
        new_list.append(new_file_name)
        # on va compter à chaque fois qu'on ajoute le nom de fichier à la liste afin de récupérer un numéro qui sera unique, et servira donc de numérotation en cas de doublons, afin d'éviter les erreurs de renommage.
        existing_files = [i for i in fnmatch.filter(new_list, new_file_name)]
        final_filename = f"{new_file_name}_{len(existing_files)}{file.suffix}"
        new_file_path = WORKING_DIR.joinpath(final_filename)
        file.rename(new_file_path)  
        if "ERREUR_COMMANDE" in new_file_name:
            typer.secho(f"Fichier {file.name} n'a pas pu être renommé --> N° de commande introuvable", fg=typer.colors.RED)
        else:
            typer.secho(f"Fichier {file.name} a été renommé avec succès", fg=typer.colors.GREEN)


'''JE RAJOUTE DU TEXTE POUR CREER UNE SECONDE VERSION DU FICHIER
'''
