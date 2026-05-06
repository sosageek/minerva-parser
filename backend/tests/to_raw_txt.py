import sys

def rendi_raw_file(nome_file_input):
    nome_file_output = f"{nome_file_input}_raw.txt"

    try:
        with open(nome_file_input, 'r', encoding='utf-8') as f:
            contenuto = f.read()
        
        # Trasformiamo i caratteri speciali nelle loro sequenze di escape letterali
        # .encode('unicode_escape') crea i byte con i backslash, 
        # .decode('utf-8') li riporta a stringa leggibile
        contenuto_raw = contenuto.encode('unicode_escape').decode('utf-8')
        
        if nome_file_output:
            with open(nome_file_output, 'w', encoding='utf-8') as f_out:
                f_out.write(contenuto_raw)
            print(f"File salvato con successo: {nome_file_output}")
        else:
            print(contenuto_raw)
            
    except FileNotFoundError:
        print(f"Errore: Il file '{nome_file_input}' non esiste.")
    except Exception as e:
        print(f"Si è verificato un errore: {e}")

# Esempio di utilizzo
if __name__ == "__main__":
    # Sostituisci 'testo.txt' con il nome del tuo file
    rendi_raw_file('/Users/gabrielelobello/Projects/progetto/backend/tests/testo.txt')